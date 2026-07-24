"""Phase 5B regression checklist runner.

Covers:
- Loop cycle take rollover integrity
- Punch in/out timing and auto-stop behavior
- Active take switching semantics
- Comp region persistence safety
- Recovery snapshot validation/restore path
- Device preflight safety checks
- Baseline Phase 5A compatibility
"""

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable, Dict, List

import numpy as np

from app_paths import ensure_dirs
from audio_device import AudioDevice, AudioDeviceManager
from p5a_regression_runner import run_phase5a_regression_checks
from recording_controller import RecordingController
from recording_recovery import RecoverySnapshotManager
from recording_session import RecordingSession


@dataclass
class RegressionCheckResult:
    name: str
    passed: bool
    details: str


def _run_check(name: str, fn: Callable[[], None]) -> RegressionCheckResult:
    try:
        fn()
        return RegressionCheckResult(name=name, passed=True, details="PASS")
    except Exception as exc:  # pragma: no cover
        return RegressionCheckResult(name=name, passed=False, details=str(exc))


def _pump_audio(controller: RecordingController, frames: int, blocks: int) -> None:
    for _ in range(max(1, int(blocks))):
        indata = np.zeros((frames, 2), dtype=np.float32)
        outdata = np.zeros((frames, 2), dtype=np.float32)
        controller._audio_callback(indata, outdata, frames, None, None)


def _check_loop_cycles_generate_unique_takes() -> None:
    controller = RecordingController("p5b_reg_loop", "Regression Loop")
    assert controller.arm_track(0), "Failed to arm track 0"
    controller.set_count_in_bars(0)
    controller.set_loop_enabled(True)
    assert controller.set_loop_range_samples(0, 2048), "Loop range setup failed"

    started = controller.start_recording()
    assert started, f"start_recording failed: {controller.status.last_error}"

    # Run enough blocks to cross 4 loop boundaries.
    for _ in range(120):
        _pump_audio(controller, frames=256, blocks=1)
        if controller.get_transport_diagnostics().get("loop_cycles_completed", 0) >= 4:
            break

    diagnostics = controller.get_transport_diagnostics()
    assert diagnostics.get("loop_cycles_completed", 0) >= 4, "Expected at least 4 loop cycles"

    controller.stop_recording(duration_seconds=0.0, force=True)
    takes = controller.session.get_all_takes_for_track(0)
    take_numbers = {int(t.take_number) for t in takes}
    assert len(takes) >= 4, "Expected at least 4 takes from loop cycles"
    assert len(take_numbers) == len(takes), "Expected unique take numbers across loop cycles"


def _check_punch_boundaries_auto_stop() -> None:
    controller = RecordingController("p5b_reg_punch", "Regression Punch")
    assert controller.arm_track(0), "Failed to arm track 0"
    controller.set_count_in_bars(0)
    controller.set_punch_enabled(True)
    assert controller.set_punch_range_samples(512, 2048), "Punch range setup failed"
    assert controller.set_pre_post_roll_samples(0, 0), "Pre/post roll setup failed"

    started = controller.start_recording()
    assert started, f"start_recording failed: {controller.status.last_error}"

    for _ in range(64):
        _pump_audio(controller, frames=128, blocks=1)
        if controller.consume_auto_stop_event():
            break

    diagnostics = controller.get_transport_diagnostics()
    assert diagnostics.get("punch_start_hits", 0) >= 1, "Expected punch start hit"
    assert diagnostics.get("punch_stop_hits", 0) >= 1, "Expected punch stop hit"
    assert diagnostics.get("auto_stop_events", 0) >= 1, "Expected auto-stop event"


def _check_active_take_switching() -> None:
    session = RecordingSession("p5b_reg_active_take", "Regression Active Take")
    session.ensure_track(0)

    first = session.start_new_take(0)
    session.finish_take(0, duration_seconds=0.25, level_stats={"peak": -6.0, "clipping": 0.0})
    second = session.start_new_take(0)
    session.finish_take(0, duration_seconds=0.25, level_stats={"peak": -4.0, "clipping": 0.0})

    assert session.set_active_take(0, first.take_number), "Failed to set first take active"
    assert session.get_active_takes()[0].take_number == first.take_number, "Active take mismatch after first switch"

    assert session.set_active_take(0, second.take_number), "Failed to set second take active"
    assert session.get_active_takes()[0].take_number == second.take_number, "Active take mismatch after second switch"


def _check_comp_map_persistence() -> None:
    session_id = "p5b_reg_comp"
    session = RecordingSession(session_id, "Regression Comp")
    session.ensure_track(0)

    for _ in range(3):
        take = session.start_new_take(0)
        session.finish_take(
            0,
            duration_seconds=0.4,
            level_stats={"peak": -6.0, "clipping": 0.0, "clip_events": 0},
            clip_events=0,
        )
        assert take is not None

    assert session.create_comp_region(0, 0, 300, 1) is not None
    assert session.create_comp_region(0, 300, 600, 2) is not None
    assert session.create_comp_region(0, 600, 900, 3) is not None

    assert session.assign_comp_region_take(0, 1, 2)
    assert session.assign_comp_region_take(0, 2, 3)

    assert session.save_session_metadata(), "Failed to save session metadata"
    loaded = RecordingSession.load_session_metadata(session_id)
    assert loaded is not None, "Failed to reload session metadata"

    regions = loaded.get_comp_regions_for_track(0)
    assert len(regions) >= 3, "Expected persisted comp regions"
    assert loaded.get_take(0, 1) is not None and loaded.get_take(0, 2) is not None and loaded.get_take(0, 3) is not None, (
        "Source takes should remain non-destructively available"
    )


def _check_recovery_snapshot_history_and_restore() -> None:
    with TemporaryDirectory() as tmp_dir:
        manager = RecoverySnapshotManager(root_dir=Path(tmp_dir))

        session = RecordingSession("p5b_reg_recovery", "Regression Recovery")
        session.ensure_track(0)
        session.start_new_take(0)
        session.finish_take(0, duration_seconds=0.5, level_stats={"peak": -3.0, "clipping": 0.0})

        payload = {"session": session.export_snapshot_payload()}
        assert manager.write_snapshot(
            session_id=session.session_id,
            project_name=session.project_name,
            payload=payload,
            reason="regression",
            interrupted=True,
        ), "Failed to write snapshot"

        latest = manager.load_snapshot(session.session_id)
        assert latest is not None, "Failed to read latest snapshot"
        valid, reason = manager.validate_snapshot(latest, session.session_id, session.project_name, max_age_hours=24)
        assert valid, f"Snapshot should validate: {reason}"

        history_files = manager.list_snapshot_history(session.session_id)
        assert history_files, "Expected at least one recovery history snapshot"

        history_snapshot = manager.load_snapshot_from_path(history_files[0])
        assert history_snapshot is not None, "Failed to load history snapshot"

        restored = RecordingSession("p5b_reg_recovery", "Regression Recovery")
        ok = restored.restore_from_snapshot_payload(history_snapshot["payload"]["session"])
        assert ok, "Failed to restore session payload from history snapshot"


def _check_device_preflight_safety() -> None:
    manager = AudioDeviceManager()
    manager.devices = [
        AudioDevice(
            device_id=0,
            name="Mock Input",
            max_input_channels=1,
            max_output_channels=0,
            default_sample_rate=44100.0,
            default_latency_ms=5.0,
            is_default_input=True,
            is_default_output=False,
            api="Mock",
        ),
        AudioDevice(
            device_id=1,
            name="Mock Output",
            max_input_channels=0,
            max_output_channels=1,
            default_sample_rate=44100.0,
            default_latency_ms=5.0,
            is_default_input=False,
            is_default_output=True,
            api="Mock",
        ),
    ]
    manager.selected_input_device = 0
    manager.selected_output_device = 1

    compatible, message = manager.check_channel_compatibility(required_input_channels=2, required_output_channels=2)
    assert not compatible, "Expected incompatibility for one-channel mock devices"
    assert "supports only" in message, "Expected compatibility hint text"

    preflight = manager.get_preflight_summary(required_input_channels=2, required_output_channels=2)
    assert not bool(preflight.get("channel_compatible", True)), "Preflight should report channel incompatibility"
    warnings = preflight.get("warnings", [])
    assert isinstance(warnings, list) and warnings, "Preflight should include warnings"


def _check_phase5a_baseline_still_passes() -> None:
    report = run_phase5a_regression_checks()
    assert int(report.get("failed", 0)) == 0, "Phase 5A baseline checks must continue passing"


def run_phase5b_regression_checks() -> Dict[str, object]:
    ensure_dirs()

    checks = [
        ("loop-4-cycles-unique-takes", _check_loop_cycles_generate_unique_takes),
        ("punch-auto-stop-boundaries", _check_punch_boundaries_auto_stop),
        ("active-take-switching", _check_active_take_switching),
        ("comp-map-persistence", _check_comp_map_persistence),
        ("recovery-history-restore", _check_recovery_snapshot_history_and_restore),
        ("device-preflight-safety", _check_device_preflight_safety),
        ("phase5a-baseline", _check_phase5a_baseline_still_passes),
    ]

    results: List[RegressionCheckResult] = [_run_check(name, fn) for name, fn in checks]
    passed = sum(1 for result in results if result.passed)
    failed = len(results) - passed

    return {
        "passed": passed,
        "failed": failed,
        "results": results,
    }


def format_regression_summary(report: Dict[str, object]) -> str:
    results = report.get("results", [])
    lines = [
        f"P5B Regression Results: {report.get('passed', 0)} passed, {report.get('failed', 0)} failed",
    ]
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(f"- {result.name}: {status}")
        if not result.passed:
            lines.append(f"  {result.details}")
    return "\n".join(lines)


def main() -> int:
    report = run_phase5b_regression_checks()
    print(format_regression_summary(report))
    return 0 if int(report.get("failed", 0)) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
