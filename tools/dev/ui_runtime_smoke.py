import json
import os
import sys
import traceback
import wave
from pathlib import Path
import types

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _make_silent_wav(path: Path, duration_seconds: float = 0.25, sample_rate: int = 44100) -> None:
    frame_count = int(duration_seconds * sample_rate)
    silence = b"\x00\x00" * frame_count  # 16-bit mono silence
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(silence)


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if os.name == "nt":
        os.environ.setdefault("QT_QPA_FONTDIR", str(Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"))

    # Ensure preview playback paths stay non-interactive in headless smoke mode.
    if "sounddevice" not in sys.modules:
        sd_stub = types.SimpleNamespace(
            stop=lambda: None,
            play=lambda *args, **kwargs: None,
            query_devices=lambda *args, **kwargs: [],
            query_hostapis=lambda *args, **kwargs: [],
            default=types.SimpleNamespace(device=(None, None)),
        )
        sys.modules["sounddevice"] = sd_stub

    from PySide6.QtCore import qInstallMessageHandler
    from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog
    import subprocess as _subprocess

    noisy_line = "This plugin does not support propagateSizeHints()"
    previous_qt_handler = None

    def _qt_message_filter(_msg_type, _context, message):
        if str(message).strip() == noisy_line:
            return
        if previous_qt_handler is not None:
            previous_qt_handler(_msg_type, _context, message)
        else:
            sys.__stderr__.write(f"{message}\n")

    previous_qt_handler = qInstallMessageHandler(_qt_message_filter)

    from echo_pro_app import EchoProWindow

    app = QApplication.instance() or QApplication([])

    results = {
        "flow_results": [],
        "dialogs": [],
        "exceptions": [],
    }

    original_question = QMessageBox.question
    original_warning = QMessageBox.warning
    original_critical = QMessageBox.critical
    original_information = QMessageBox.information
    original_get_open_file_name = QFileDialog.getOpenFileName
    original_popen = _subprocess.Popen

    def _record_dialog(kind: str, title: str, message: str) -> None:
        results["dialogs"].append({"kind": kind, "title": str(title), "message": str(message)})

    def fake_question(parent, title, text, buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No):
        _record_dialog("question", title, text)
        return QMessageBox.StandardButton.No

    def fake_warning(parent, title, text):
        _record_dialog("warning", title, text)
        return QMessageBox.StandardButton.Ok

    def fake_critical(parent, title, text):
        _record_dialog("critical", title, text)
        return QMessageBox.StandardButton.Ok

    def fake_information(parent, title, text):
        _record_dialog("information", title, text)
        return QMessageBox.StandardButton.Ok

    def fake_popen(*args, **kwargs):
        joined = " ".join(str(a) for a in args)
        if "install_echo_pro.bat" in joined:
            results["dialogs"].append({"kind": "popen", "title": "subprocess", "message": str(args)})

            class _DummyProc:
                pid = 0

            return _DummyProc()
        return original_popen(*args, **kwargs)

    QMessageBox.question = fake_question
    QMessageBox.warning = fake_warning
    QMessageBox.critical = fake_critical
    QMessageBox.information = fake_information
    _subprocess.Popen = fake_popen

    smoke_wav = Path("_ui_smoke_input.wav").resolve()
    _make_silent_wav(smoke_wav)

    def fake_get_open_file_name(*_args, **_kwargs):
        return str(smoke_wav), "Audio Files (*.wav)"

    QFileDialog.getOpenFileName = fake_get_open_file_name

    window = None

    def run_step(name: str, func):
        try:
            func()
            app.processEvents()
            results["flow_results"].append({"flow": name, "status": "pass"})
        except Exception:
            tb = traceback.format_exc()
            results["flow_results"].append({"flow": name, "status": "fail"})
            results["exceptions"].append({"flow": name, "traceback": tb})

    try:
        def step_open_app():
            nonlocal window
            window = EchoProWindow()
            window.show()

        run_step("open_app", step_open_app)

        def step_record_arm_flow():
            window.track_name_input.setText("Smoke Track")
            window.add_track()
            window.record_track_input.setText("0")
            window.arm_recording_track()
            window.start_recording_session()
            if window.recording_controller.status.is_recording or window.recording_controller.status.count_in_active:
                window.stop_recording_session()

        run_step("record_arm_flow", step_record_arm_flow)

        def step_take_review_toggles():
            # First pass without selection to ensure warning path is safe.
            window.toggle_selected_take_keeper()
            window.toggle_selected_take_muted()
            window.rate_selected_take(+1)

            # Synthetic take metadata pass for active-list path.
            window.recording_controller.session.ensure_track(0)
            window.recording_controller.session.start_new_take(0)
            window.recording_controller.session.finish_take(
                0,
                duration_seconds=0.5,
                level_stats={"peak": -6.0, "clipping": 0.0},
                start_sample=0,
                end_sample=0,
            )
            window.refresh_take_track_selector()
            window.take_track_combo.setCurrentIndex(0)
            window.refresh_take_review_list()

            if window.take_review_list.count() > 0 and "Take " in window.take_review_list.item(0).text():
                window.take_review_list.setCurrentRow(0)
                window.toggle_selected_take_keeper()
                window.toggle_selected_take_muted()
                window.rate_selected_take(+1)

        run_step("take_review_toggles", step_take_review_toggles)

        def step_stems_dialog_flow():
            window.split_song_into_stems()

        run_step("stems_dialog_flow", step_stems_dialog_flow)

        def step_ace_generation_flow():
            window._switch_to_tab("AI Generation (ACE-Step)")
            window.ace_prompt_input.setPlainText("smoke test prompt: warm ambient loop")
            window.ace_lyrics_input.setPlainText("")
            window.ace_duration_spin.setValue(10)
            window.ace_steps_spin.setValue(10)
            window.ace_batch_spin.setValue(1)

            fmt_idx = window.ace_output_format_combo.findText("flac")
            if fmt_idx >= 0:
                window.ace_output_format_combo.setCurrentIndex(fmt_idx)
            sr_idx = window.ace_output_sample_rate_combo.findData(48000)
            if sr_idx >= 0:
                window.ace_output_sample_rate_combo.setCurrentIndex(sr_idx)

            window.ace_generate_btn.click()
            app.processEvents()
            if not getattr(window, "_ace_step_results", []):
                raise RuntimeError("ACE-Step smoke flow did not produce a result")

            if window.ace_results_list.count() > 0:
                window.ace_results_list.setCurrentRow(0)

            window._toggle_ace_step_result_playback(0)
            window._toggle_ace_step_result_loop(0)
            window._toggle_ace_step_result_favorite(0)
            window._ace_step_run_quick_action("same", 0)
            app.processEvents()

            if len(getattr(window, "_ace_step_results", [])) < 2:
                raise RuntimeError("ACE-Step quick rerun did not append a second result")

            window._transfer_ace_step_result(0)
            window._send_ace_step_result_to_demucs(0)
            app.processEvents()

            if window.stem_source_path is None:
                raise RuntimeError("ACE-Step to Demucs handoff did not set stem source")

        run_step("ace_generation_flow", step_ace_generation_flow)

    finally:
        qInstallMessageHandler(previous_qt_handler)
        QFileDialog.getOpenFileName = original_get_open_file_name
        QMessageBox.question = original_question
        QMessageBox.warning = original_warning
        QMessageBox.critical = original_critical
        QMessageBox.information = original_information
        _subprocess.Popen = original_popen

        if window is not None:
            window.close()

        app.processEvents()

        try:
            if smoke_wav.exists():
                smoke_wav.unlink()
        except OSError:
            pass

    print(json.dumps(results, indent=2))

    return 0 if not results["exceptions"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
