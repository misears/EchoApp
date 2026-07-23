"""Phase 5A regression checklist runner.

Covers:
- Count-in transition to recording state
- Stop during count-in behavior
- Device error-path handling and stream lifecycle safety
"""

from dataclasses import dataclass
from typing import Callable, Dict, List
from unittest.mock import patch

import numpy as np

from app_paths import ensure_dirs
from recording_controller import RecordingController


@dataclass
class RegressionCheckResult:
    name: str
    passed: bool
    details: str


class _MockStream:
    def __init__(self, *args, **kwargs):
        self.started = False
        self.stopped = False
        self.closed = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def close(self) -> None:
        self.closed = True


def _run_check(name: str, fn: Callable[[], None]) -> RegressionCheckResult:
    try:
        fn()
        return RegressionCheckResult(name=name, passed=True, details="PASS")
    except Exception as exc:  # pragma: no cover - regression harness catches failures
        return RegressionCheckResult(name=name, passed=False, details=str(exc))


def _check_count_in_transition() -> None:
    controller = RecordingController("p5a_reg_countin", "Regression Count-In")
    assert controller.arm_track(0), "Failed to arm track 0"
    controller.set_count_in_bars(1)

    started = controller.start_recording()
    assert started, f"start_recording failed: {controller.status.last_error}"
    assert controller.status.count_in_active, "Expected count-in to become active"
    assert not controller.status.is_recording, "Recording should not start before count-in ends"

    while controller.status.count_in_active:
        pending = controller._pending_count_in
        assert pending is not None, "Pending count-in buffer unexpectedly missing"
        remaining = pending.shape[1] - controller._count_in_cursor
        frames = max(1, min(256, remaining))
        indata = np.zeros((frames, 2), dtype=np.float32)
        outdata = np.zeros((frames, 2), dtype=np.float32)
        controller._audio_callback(indata, outdata, frames, None, None)

    assert controller.status.is_recording, "Recording did not begin after count-in completion"
    assert 0 in controller.active_take_ids, "Expected active take id for armed track"

    controller.stop_recording(duration_seconds=0.1)


def _check_stop_during_count_in() -> None:
    controller = RecordingController("p5a_reg_stop_countin", "Regression Stop Count-In")
    assert controller.arm_track(0), "Failed to arm track 0"
    controller.set_count_in_bars(2)

    started = controller.start_recording()
    assert started, f"start_recording failed: {controller.status.last_error}"
    assert controller.status.count_in_active, "Expected count-in to be active"

    controller.stop_recording(duration_seconds=0.0)

    assert not controller.status.count_in_active, "Count-in should be cleared after stop"
    assert not controller.status.is_recording, "Recording state should be false after stop"
    assert not controller.active_take_ids, "No active takes should exist when stopped during count-in"
    assert len(controller.session.get_all_takes_for_track(0)) == 0, "No takes should be created when stopping during count-in"


def _check_device_error_and_stream_lifecycle() -> None:
    controller = RecordingController("p5a_reg_device", "Regression Device")

    with patch("recording_controller.sd.Stream", side_effect=RuntimeError("mock stream failure")):
        ok = controller.start_stream(input_device=9999, output_device=9999)
        assert not ok, "start_stream should fail when stream creation raises"
        assert "mock stream failure" in controller.status.last_error, "Expected propagated stream error text"

    with patch("recording_controller.sd.Stream", _MockStream):
        ok = controller.start_stream(input_device=0, output_device=0)
        assert ok, "start_stream should succeed with mock stream"
        first_stream = controller.stream
        assert first_stream is not None, "Expected active stream instance"

        ok_again = controller.start_stream(input_device=1, output_device=1)
        assert ok_again, "Repeated start_stream should return True while stream is active"
        assert controller.stream is first_stream, "Existing stream should be reused during repeated start_stream"

        controller.stop_stream()
        assert controller.stream is None, "stop_stream should clear active stream reference"


def run_phase5a_regression_checks() -> Dict[str, object]:
    """Run all Phase 5A regression checks and return structured results."""
    ensure_dirs()

    checks = [
        ("count-in-transition", _check_count_in_transition),
        ("stop-during-count-in", _check_stop_during_count_in),
        ("device-error-path", _check_device_error_and_stream_lifecycle),
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
        f"P5A Regression Results: {report.get('passed', 0)} passed, {report.get('failed', 0)} failed",
    ]
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(f"- {result.name}: {status}")
        if not result.passed:
            lines.append(f"  {result.details}")
    return "\n".join(lines)


def main() -> int:
    report = run_phase5a_regression_checks()
    print(format_regression_summary(report))
    return 0 if report.get("failed", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
