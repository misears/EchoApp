"""Phase 5B regression checklist runner.

Covers:
- Loop cycle take rollover integrity
- Punch in/out timing and auto-stop behavior
- Active take switching semantics
- Comp region persistence safety
- Recovery snapshot validation/restore path
- Device preflight safety checks
- Baseline Phase 5A compatibility
- Interrupted-recording detection (restore prompt simulation)
- Session take-pointer integrity after restore
- Discard recovery clean startup path
- Clip and silence warnings non-blocking performance
"""

import time
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
from typing import Callable, Dict, List
from unittest.mock import patch

import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app_paths import ensure_dirs
from audio_device import AudioDevice, AudioDeviceManager
from audio_engine import Track as TrackEngine
try:
    from .p5a_regression_runner import run_phase5a_regression_checks
except ImportError:
    from p5a_regression_runner import run_phase5a_regression_checks
from recording_controller import RecordingController
from recording_recovery import RecoverySnapshotManager
from recording_session import RecordingSession
import stems_engine


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


def _check_interruption_snapshot_detection() -> None:
    """Write a snapshot marked as interrupted and verify the restore-prompt path detects it."""
    with TemporaryDirectory() as tmp_dir:
        manager = RecoverySnapshotManager(root_dir=Path(tmp_dir))
        session = RecordingSession("p5b_reg_interrupt", "Regression Interrupt")
        session.ensure_track(0)
        session.start_new_take(0)
        session.finish_take(0, duration_seconds=0.5, level_stats={"peak": -3.0, "clipping": 0.0})

        payload = {"session": session.export_snapshot_payload()}
        ok = manager.write_snapshot(
            session_id=session.session_id,
            project_name=session.project_name,
            payload=payload,
            reason="simulated_interruption",
            interrupted=True,
        )
        assert ok, "Failed to write interrupted snapshot"

        loaded = manager.load_snapshot(session.session_id)
        assert loaded is not None, "Expected snapshot to be loadable after interruption"
        assert loaded.get("interrupted") is True, "Snapshot should be flagged as interrupted"

        valid, reason = manager.validate_snapshot(
            loaded, session.session_id, session.project_name, max_age_hours=24
        )
        assert valid, f"Interrupted snapshot should still pass validation: {reason}"


def _check_restore_session_take_pointers() -> None:
    """Restore a session from snapshot and verify take pointers and comp regions are intact."""
    with TemporaryDirectory() as tmp_dir:
        manager = RecoverySnapshotManager(root_dir=Path(tmp_dir))
        original = RecordingSession("p5b_reg_restore_ptrs", "Regression Restore Pointers")
        original.ensure_track(0)
        original.ensure_track(1)

        for _ in range(3):
            original.start_new_take(0)
            original.finish_take(0, duration_seconds=0.3, level_stats={"peak": -6.0, "clipping": 0.0})
        for _ in range(2):
            original.start_new_take(1)
            original.finish_take(1, duration_seconds=0.3, level_stats={"peak": -6.0, "clipping": 0.0})

        # Set a specific active take so the pointer can be verified after restore.
        original.set_active_take(0, 2)

        # Add a comp region.
        original.create_comp_region(0, 0, 512, 1)

        payload = {"session": original.export_snapshot_payload()}
        manager.write_snapshot(
            session_id=original.session_id,
            project_name=original.project_name,
            payload=payload,
            reason="restore_pointer_test",
            interrupted=True,
        )

        loaded_snapshot = manager.load_snapshot(original.session_id)
        assert loaded_snapshot is not None

        restored = RecordingSession(original.session_id, original.project_name)
        ok = restored.restore_from_snapshot_payload(loaded_snapshot["payload"]["session"])
        assert ok, "Restore should succeed"

        # Verify take counts per track.
        assert len(restored.get_all_takes_for_track(0)) == 3, "Track 0 should have 3 takes after restore"
        assert len(restored.get_all_takes_for_track(1)) == 2, "Track 1 should have 2 takes after restore"

        # Verify take pointer continuity: next take number should resume from where we left off.
        assert restored.current_take_number.get(0, 0) == 4, "Track 0 next take should be 4"
        assert restored.current_take_number.get(1, 0) == 3, "Track 1 next take should be 3"

        # Verify comp region survived.
        regions = restored.get_comp_regions_for_track(0)
        assert len(regions) == 1, "Comp region should survive restore"


def _check_discard_recovery_clean_startup() -> None:
    """Write a snapshot then discard it; verify load returns None (clean startup path)."""
    with TemporaryDirectory() as tmp_dir:
        manager = RecoverySnapshotManager(root_dir=Path(tmp_dir))
        session = RecordingSession("p5b_reg_discard", "Regression Discard")
        session.ensure_track(0)
        session.start_new_take(0)
        session.finish_take(0, duration_seconds=0.25, level_stats={"peak": -6.0, "clipping": 0.0})

        payload = {"session": session.export_snapshot_payload()}
        manager.write_snapshot(
            session_id=session.session_id,
            project_name=session.project_name,
            payload=payload,
            reason="discard_test",
            interrupted=True,
        )

        # Confirm the snapshot exists before discard.
        assert manager.load_snapshot(session.session_id) is not None, "Snapshot should exist before discard"

        # Discard (simulates user choosing 'Discard' on the restore prompt).
        discarded = manager.clear_snapshot(session.session_id)
        assert discarded, "clear_snapshot should return True"

        # Clean startup: load should now return None.
        assert manager.load_snapshot(session.session_id) is None, "Snapshot should be gone after discard"


def _check_clip_silence_warnings_non_blocking() -> None:
    """Feed clipping and silent audio through TrackEngine; verify diagnostics without callback latency."""
    SAMPLE_RATE = 44100
    CHANNELS = 2
    BLOCK_FRAMES = 256

    engine = TrackEngine(track_id=0, name="reg_diag_track", channels=CHANNELS, sample_rate=SAMPLE_RATE)

    # --- Clip event check ---
    clipping_audio = np.full((BLOCK_FRAMES, CHANNELS), 1.5, dtype=np.float32)
    t0 = time.monotonic()
    engine.record(clipping_audio)
    elapsed_clip = time.monotonic() - t0

    clip_diag = engine.get_recording_diagnostics()
    assert clip_diag["clip_events"] >= 1, "Expected at least one clip event after clipping input"
    assert elapsed_clip < 0.05, f"Clip detection took too long: {elapsed_clip:.4f}s (threshold: 0.05s)"

    # --- Silence warning check ---
    # Reset then feed SILENCE_WARN_SECONDS worth of silent blocks.
    engine.reset_recording_diagnostics()
    silence_audio = np.zeros((BLOCK_FRAMES, CHANNELS), dtype=np.float32)
    silence_blocks = int(SAMPLE_RATE / BLOCK_FRAMES) + 2  # slightly more than 1 second
    t0 = time.monotonic()
    for _ in range(silence_blocks):
        engine.record(silence_audio)
    elapsed_silence = time.monotonic() - t0

    silence_diag = engine.get_recording_diagnostics()
    assert silence_diag["silence_warning_active"], "Expected silence_warning_active after sustained silent input"
    assert silence_diag["silence_events"] >= 1, "Expected at least one silence event"
    assert elapsed_silence < 1.0, f"Silence detection loop took too long: {elapsed_silence:.4f}s (threshold: 1.0s)"


def _check_stem_progress_reporting_and_model_selection() -> None:
    with TemporaryDirectory() as tmp_dir:
        temp_root = Path(tmp_dir)
        input_path = temp_root / "mix.wav"
        input_path.write_bytes(b"fake-audio")

        output_dir = temp_root / "stem_output"
        model_output = output_dir / "htdemucs_ft" / input_path.stem
        model_output.mkdir(parents=True, exist_ok=True)
        for stem_name in ("vocals", "drums"):
            (model_output / f"{stem_name}.wav").write_bytes(b"fake-stem")

        captured_commands: List[List[str]] = []
        captured_messages: List[str] = []

        class _MockStdout:
            def __init__(self, lines: List[str]):
                self._lines = list(lines)
                self._index = 0
                self.exhausted = False

            def readline(self) -> str:
                if self._index >= len(self._lines):
                    self.exhausted = True
                    return ""
                line = self._lines[self._index]
                self._index += 1
                return line

            def close(self) -> None:
                self.exhausted = True

        class _MockProcess:
            def __init__(self, cmd: List[str], **_kwargs):
                captured_commands.append(list(cmd))
                self.stdout = _MockStdout(
                    [
                        "Selected model is htdemucs_ft\n",
                        "Separated tracks will be stored in stem_output\n",
                    ]
                )
                self.returncode = None

            def poll(self):
                if self.stdout.exhausted:
                    self.returncode = 0
                    return 0
                return None

            def wait(self, timeout=None):
                self.stdout.exhausted = True
                self.returncode = 0
                return 0

            def terminate(self) -> None:
                self.stdout.exhausted = True
                self.returncode = 1

            def kill(self) -> None:
                self.stdout.exhausted = True
                self.returncode = 1

        with (
            patch("stems_engine._prepare_demucs_input", return_value=(input_path, 12000)),
            patch("stems_engine.subprocess.Popen", side_effect=_MockProcess),
            patch("stems_engine.time.sleep", return_value=None),
        ):
            stems = stems_engine.separate_stems(
                str(input_path),
                output_dir,
                demucs_executable="demucs",
                demucs_model="htdemucs_ft",
                progress_callback=captured_messages.append,
            )

        assert captured_commands, "Expected a Demucs command to be launched"
        command = captured_commands[0]
        assert "-n" in command, "Demucs command should include the selected model flag"
        model_flag_index = command.index("-n")
        assert command[model_flag_index + 1] == "htdemucs_ft", "Selected Demucs model should be forwarded"
        assert captured_messages[0] == "Starting Demucs separation (htdemucs_ft)...", "Expected startup status"
        assert "Collecting separated stem files..." in captured_messages, "Expected collection status"
        assert captured_messages[-1] == "Demucs finished. 2 stems ready.", "Expected completion status"
        assert set(stems.keys()) == {"vocals", "drums"}, "Expected the moved stems to be returned"


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
        ("interruption-snapshot-detection", _check_interruption_snapshot_detection),
        ("restore-session-take-pointers", _check_restore_session_take_pointers),
        ("discard-recovery-clean-startup", _check_discard_recovery_clean_startup),
        ("clip-silence-warnings-non-blocking", _check_clip_silence_warnings_non_blocking),
        ("stem-progress-reporting-model-selection", _check_stem_progress_reporting_and_model_selection),
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
