import json
import os
import sys
import traceback
import tempfile
import wave
from pathlib import Path
import types
from typing import Dict

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
    from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog, QPushButton, QInputDialog
    from PySide6.QtCore import QTimer
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

    from echo_pro_app import TabbedEchoProWindow, VoiceManagerDialog

    app = QApplication.instance() or QApplication([])

    results = {
        "flow_results": [],
        "dialogs": [],
        "exceptions": [],
        "button_coverage": {
            "total_enabled_buttons": 0,
            "clicked_buttons": 0,
            "coverage_percent": 0.0,
            "uncovered_enabled_buttons": [],
        },
        "button_click_audit": {
            "failed_buttons": [],
            "skipped_buttons": [],
        },
    }

    original_question = QMessageBox.question
    original_warning = QMessageBox.warning
    original_critical = QMessageBox.critical
    original_information = QMessageBox.information
    original_get_open_file_name = QFileDialog.getOpenFileName
    original_get_save_file_name = QFileDialog.getSaveFileName
    original_get_existing_directory = QFileDialog.getExistingDirectory
    original_popen = _subprocess.Popen
    original_voice_dialog_exec = VoiceManagerDialog.exec
    original_button_click = QPushButton.click
    original_get_int = QInputDialog.getInt
    original_get_double = QInputDialog.getDouble
    original_get_text = QInputDialog.getText
    original_get_item = QInputDialog.getItem

    button_inventory: Dict[int, str] = {}
    clicked_button_ids: set[int] = set()

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

    def fake_get_save_file_name(*_args, **_kwargs):
        target = Path(tempfile.gettempdir()) / "echo_ui_smoke_saved_output.txt"
        return str(target), "Text Files (*.txt)"

    def fake_get_existing_directory(*_args, **_kwargs):
        return str(Path(tempfile.gettempdir()))

    def fake_get_int(*_args, **_kwargs):
        return 1, True

    def fake_get_double(*_args, **_kwargs):
        return 0.0, True

    def fake_get_text(*_args, **_kwargs):
        return "smoke", True

    def fake_get_item(*_args, **_kwargs):
        return "", True

    QFileDialog.getOpenFileName = fake_get_open_file_name
    QFileDialog.getSaveFileName = fake_get_save_file_name
    QFileDialog.getExistingDirectory = fake_get_existing_directory
    QInputDialog.getInt = fake_get_int
    QInputDialog.getDouble = fake_get_double
    QInputDialog.getText = fake_get_text
    QInputDialog.getItem = fake_get_item

    def fake_voice_dialog_exec(self):
        QTimer.singleShot(0, self.accept)
        return original_voice_dialog_exec(self)

    def tracked_button_click(self):
        clicked_button_ids.add(id(self))
        return original_button_click(self)

    VoiceManagerDialog.exec = fake_voice_dialog_exec
    QPushButton.click = tracked_button_click

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
        def _button_descriptor(button: QPushButton) -> str:
            label = str(button.text() or "").strip() or "<no-text>"
            obj_name = str(button.objectName() or "").strip() or "<no-object-name>"
            return f"{label} [{obj_name}]"

        def _find_enabled_button_by_text(text: str) -> QPushButton | None:
            wanted = str(text).strip()
            for button in window.findChildren(QPushButton):
                if not button.isEnabled():
                    continue
                if str(button.text() or "").strip() == wanted:
                    return button
            return None

        def _find_enabled_button_by_tooltip_fragment(fragment: str) -> QPushButton | None:
            wanted = str(fragment).strip().lower()
            for button in window.findChildren(QPushButton):
                if not button.isEnabled():
                    continue
                tip = str(button.toolTip() or "").strip().lower()
                if wanted and wanted in tip:
                    return button
            return None

        def _click_by_text(text: str, required: bool = True) -> bool:
            button = _find_enabled_button_by_text(text)
            if button is None:
                if required:
                    raise RuntimeError(f"Expected clickable button with text '{text}'")
                return False
            button.click()
            app.processEvents()
            return True

        def _click_by_tooltip(fragment: str, required: bool = True) -> bool:
            button = _find_enabled_button_by_tooltip_fragment(fragment)
            if button is None:
                if required:
                    raise RuntimeError(f"Expected clickable button with tooltip containing '{fragment}'")
                return False
            button.click()
            app.processEvents()
            return True

        def _capture_button_inventory() -> None:
            button_inventory.clear()
            for button in window.findChildren(QPushButton):
                if not button.isEnabled():
                    continue
                button_inventory[id(button)] = _button_descriptor(button)

        def step_open_app():
            nonlocal window
            window = TabbedEchoProWindow()
            controller = window._get_stem_workflow_controller()

            def _fake_start_stem_separation_worker(song_path: Path) -> None:
                payload = {
                    "stems": {
                        "vocals": str(song_path),
                        "drums": str(song_path),
                    },
                    "output_dir": str(song_path.parent),
                    "model_name": window._selected_demucs_model(),
                    "source_name": song_path.name,
                }
                controller.on_stem_worker_completed(payload)

            window._start_stem_separation_worker = _fake_start_stem_separation_worker
            window.show()
            app.processEvents()
            _capture_button_inventory()

        run_step("open_app", step_open_app)

        def step_record_arm_flow():
            window.track_name_input.setText("Smoke Track")
            _click_by_tooltip("Add track", required=False)
            _click_by_text("+ Add Track", required=False)
            if len(window.current_project.tracks) == 0:
                window.add_track()
            window.volume_track_index_input.setText("0")
            window.volume_db_input.setText("0")
            if hasattr(window, "set_track_volume_btn"):
                window.set_track_volume_btn.click()
            if hasattr(window, "add_clip_btn"):
                window.clip_track_index_input.setText("0")
                window.clip_start_sec_input.setText("0")
                window.add_clip_btn.click()
            window.record_track_input.setText("0")
            _click_by_tooltip("arm recording for this track", required=False)
            if not any(getattr(track, "armed", False) for track in window.current_project.tracks):
                window.arm_recording_track()
            if hasattr(window, "mixer_transport_bar"):
                window.mixer_transport_bar.click_button.click()
            if hasattr(window, "transport_bar") and hasattr(window.transport_bar, "record_button"):
                window.transport_bar.click_button.click()
                window.transport_bar.record_button.click()
            else:
                window.start_recording_session()
            if window.recording_controller.status.is_recording or window.recording_controller.status.count_in_active:
                if hasattr(window, "transport_bar") and hasattr(window.transport_bar, "stop_button"):
                    window.transport_bar.stop_button.click()
                else:
                    window.stop_recording_session()

        run_step("record_arm_flow", step_record_arm_flow)

        def step_home_clickables_flow():
            window._switch_to_tab("Home")
            window.play_project_btn.click()
            window.stop_project_btn.click()
            window.jump_to_transport_start_btn.click()
            window.jump_to_transport_end_btn.click()
            if hasattr(window, "zoom_in_btn"):
                window.zoom_in_btn.click()
            if hasattr(window, "zoom_out_btn"):
                window.zoom_out_btn.click()
            if hasattr(window, "zoom_reset_btn"):
                window.zoom_reset_btn.click()
            _click_by_text("Play Sel", required=False)
            _click_by_text("Loop Sel", required=False)
            if hasattr(window, "add_marker_btn"):
                window.add_marker_btn.click()
            if hasattr(window, "prev_marker_btn"):
                window.prev_marker_btn.click()
            if hasattr(window, "next_marker_btn"):
                window.next_marker_btn.click()

        run_step("home_clickables_flow", step_home_clickables_flow)

        def step_take_review_toggles():
            # First pass without selection to ensure warning path is safe.
            if hasattr(window, "refresh_takes_btn"):
                window.refresh_takes_btn.click()
            if hasattr(window, "hide_inactive_take_clips_btn"):
                window.hide_inactive_take_clips_btn.click()
                window.hide_inactive_take_clips_btn.click()
            _click_by_tooltip("Toggle keeper on selected take", required=False)
            _click_by_tooltip("Toggle mute on selected take", required=False)
            _click_by_tooltip("Raise selected take rating", required=False)

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
                _click_by_tooltip("Toggle keeper on selected take", required=False)
                _click_by_tooltip("Toggle mute on selected take", required=False)
                _click_by_tooltip("Raise selected take rating", required=False)

        run_step("take_review_toggles", step_take_review_toggles)

        def step_recording_clickables_flow():
            window._switch_to_tab("Recording")
            _click_by_tooltip("Set recording tempo", required=False)
            _click_by_tooltip("Set time signature", required=False)
            _click_by_tooltip("Set count-in length", required=False)
            _click_by_text("Set Pre/Post", required=False)
            _click_by_text("Set Punch", required=False)
            _click_by_text("Set Loop", required=False)
            _click_by_tooltip("Refresh takes", required=False)
            _click_by_tooltip("Audition selected take", required=False)
            _click_by_tooltip("Audition active take", required=False)
            _click_by_tooltip("Stop take audition", required=False)
            _click_by_tooltip("Toggle keeper on selected take", required=False)
            _click_by_tooltip("Toggle mute on selected take", required=False)
            _click_by_tooltip("Lower selected take rating", required=False)
            _click_by_tooltip("Raise selected take rating", required=False)

        run_step("recording_clickables_flow", step_recording_clickables_flow)

        def step_stems_dialog_flow():
            _click_by_text("Run Demucs Split", required=False)
            if getattr(window, "stem_source_path", None) is None:
                window.split_song_into_stems()

        run_step("stems_dialog_flow", step_stems_dialog_flow)

        def step_demucs_tab_flow():
            window._switch_to_tab("Stem Separation")
            if hasattr(window, "choose_stem_source_btn"):
                window.choose_stem_source_btn.click()
            else:
                _click_by_text("Browse...", required=False)
            if window.stem_source_path is None:
                window.choose_stem_source_audio()
            if window.stem_source_path is None:
                raise RuntimeError("Demucs browse action did not set a source path")

            _click_by_text("Separate", required=False)
            if hasattr(window, "stem_split_btn") and window.stem_split_btn.isEnabled():
                window.stem_split_btn.click()
            else:
                window.run_selected_stem_split()
            app.processEvents()
            if hasattr(window, "stem_cancel_btn") and window.stem_cancel_btn.isEnabled():
                window.stem_cancel_btn.click()

            if hasattr(window, "stem_to_ace_btn"):
                window.stem_to_ace_btn.click()
            if hasattr(window, "stem_transfer_btn"):
                window.stem_transfer_btn.click()
            _click_by_text("Copy", required=False)
            _click_by_text("Save", required=False)
            _click_by_text("Clear", required=False)

        run_step("demucs_tab_flow", step_demucs_tab_flow)

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

            _click_by_text("Play", required=False)
            _click_by_text("Loop", required=False)
            _click_by_text("★", required=False)
            _click_by_text("Regenerate Same", required=False)
            if len(getattr(window, "_ace_step_results", [])) == 1:
                window._ace_step_run_quick_action("same", 0)
            app.processEvents()

            if len(getattr(window, "_ace_step_results", [])) < 2:
                raise RuntimeError("ACE-Step quick rerun did not append a second result")

            _click_by_text("Transfer", required=False)
            _click_by_text("Send to Demucs", required=False)
            if window.stem_source_path is None:
                window._send_ace_step_result_to_demucs(0)
            app.processEvents()

            if window.stem_source_path is None:
                raise RuntimeError("ACE-Step to Demucs handoff did not set stem source")

        run_step("ace_generation_flow", step_ace_generation_flow)

        def step_voice_fx_flow():
            window._switch_to_tab("Voice FX")
            window.voice_track_index_input.setText("0")
            window.voice_clip_id_input.setText("0")
            window.voice_profile_name_input.setText("smoke_missing_profile")
            if hasattr(window, "voice_apply_btn"):
                window.voice_apply_btn.click()
            else:
                _click_by_text("Apply Voice Effect", required=False)
            if hasattr(window, "voice_manage_btn"):
                window.voice_manage_btn.click()
            else:
                _click_by_text("Manage Voices", required=False)

        run_step("voice_fx_flow", step_voice_fx_flow)

        def step_tools_and_settings_flow():
            window._switch_to_tab("Tools")
            _click_by_text("Open Stem Separation Tab", required=False)
            _click_by_text("Open AI Generation Tab", required=False)
            if hasattr(window, "_switch_to_tab"):
                window._switch_to_tab("Settings")

            if hasattr(window, "settings_shortcut_profile_combo"):
                profile_idx = window.settings_shortcut_profile_combo.findData("Modern Echo")
                if profile_idx >= 0:
                    window.settings_shortcut_profile_combo.setCurrentIndex(profile_idx)
                if hasattr(window, "settings_apply_shortcut_preset_btn"):
                    window.settings_apply_shortcut_preset_btn.click()
                else:
                    _click_by_text("Apply Preset", required=False)
                if hasattr(window, "settings_reset_shortcuts_btn"):
                    window.settings_reset_shortcuts_btn.click()
                else:
                    _click_by_text("Reset All to Defaults", required=False)

        run_step("tools_and_settings_flow", step_tools_and_settings_flow)

        def step_settings_clickables_flow():
            window._switch_to_tab("Settings")
            if hasattr(window, "settings_refresh_devices_btn"):
                window.settings_refresh_devices_btn.click()
            else:
                _click_by_text("Refresh Devices", required=False)
            if hasattr(window, "settings_test_tone_btn"):
                window.settings_test_tone_btn.click()
            else:
                _click_by_text("Test Tone", required=False)
            if hasattr(window, "settings_apply_audio_btn"):
                window.settings_apply_audio_btn.click()
            else:
                _click_by_text("Apply Audio Settings", required=False)
            if hasattr(window, "settings_apply_appearance_btn"):
                window.settings_apply_appearance_btn.click()
            else:
                _click_by_text("Apply Appearance", required=False)
            if hasattr(window, "settings_save_defaults_btn"):
                window.settings_save_defaults_btn.click()
            else:
                _click_by_text("Save Project Defaults", required=False)

        run_step("settings_clickables_flow", step_settings_clickables_flow)

        def step_mastering_clickables_flow():
            window._switch_to_tab("Mastering")
            _click_by_text("Play", required=False)
            _click_by_text("Loop On", required=False)
            _click_by_text("Loop Off", required=False)
            _click_by_text("To Tracks", required=False)
            _click_by_text("To Demucs", required=False)
            _click_by_text("Bypass", required=False)
            _click_by_text("FX", required=False)
            _click_by_text("Learn", required=False)
            _click_by_text("Reset", required=False)

        if str(os.environ.get("ECHO_UI_SMOKE_EXTRA_CLICK_COVERAGE", "")).strip().lower() in {"1", "true", "yes", "on"}:
            run_step("mastering_clickables_flow", step_mastering_clickables_flow)

        def step_click_all_enabled_buttons_flow():
            _capture_button_inventory()
            failures = []
            skipped = []
            buttons = [button for button in window.findChildren(QPushButton) if button.isEnabled()]
            buttons.sort(key=lambda b: _button_descriptor(b).lower())

            skip_text_exact = {
                "Browse...",
                "Add from Folder...",
                "Download",
                "Open Master FX",
                "Generate",
                "Separate",
                "Regenerate Same",
                "Regenerate New",
                "Vary Subtle",
                "Vary Strong",
            }
            skip_object_names = {
                "ColorSwatch",
            }
            skip_text_contains = {
                "to demucs",
                "to tracks",
                "transfer",
                "send to demucs",
            }

            for button in buttons:
                descriptor = _button_descriptor(button)
                label = str(button.text() or "").strip()
                obj_name = str(button.objectName() or "").strip()
                label_norm = label.lower()
                if (
                    label in skip_text_exact
                    or obj_name in skip_object_names
                    or any(token in label_norm for token in skip_text_contains)
                ):
                    skipped.append(descriptor)
                    continue
                try:
                    button.click()
                    app.processEvents()
                    if hasattr(window, "stem_cancel_btn") and window.stem_cancel_btn.isEnabled():
                        window.stem_cancel_btn.click()
                        app.processEvents()
                except Exception:
                    failures.append({
                        "button": descriptor,
                        "traceback": traceback.format_exc(),
                    })

            results["button_click_audit"] = {
                "failed_buttons": failures,
                "skipped_buttons": skipped,
            }
            if failures:
                raise RuntimeError(f"{len(failures)} clickable controls raised exceptions during click audit")

        if str(os.environ.get("ECHO_UI_SMOKE_CLICK_ALL", "")).strip().lower() in {"1", "true", "yes", "on"}:
            run_step("click_all_enabled_buttons_flow", step_click_all_enabled_buttons_flow)

        def step_button_coverage_audit_flow():
            _capture_button_inventory()
            enabled_ids = set(button_inventory.keys())
            covered_ids = enabled_ids.intersection(clicked_button_ids)
            uncovered = [button_inventory[button_id] for button_id in sorted(enabled_ids - covered_ids, key=lambda key: button_inventory[key].lower())]
            total_enabled = len(enabled_ids)
            clicked = len(covered_ids)
            coverage = 100.0 if total_enabled == 0 else round((clicked * 100.0) / float(total_enabled), 1)

            results["button_coverage"] = {
                "total_enabled_buttons": total_enabled,
                "clicked_buttons": clicked,
                "coverage_percent": coverage,
                "uncovered_enabled_buttons": uncovered,
            }

        run_step("button_coverage_audit_flow", step_button_coverage_audit_flow)

    finally:
        qInstallMessageHandler(previous_qt_handler)
        QFileDialog.getOpenFileName = original_get_open_file_name
        QFileDialog.getSaveFileName = original_get_save_file_name
        QFileDialog.getExistingDirectory = original_get_existing_directory
        QInputDialog.getInt = original_get_int
        QInputDialog.getDouble = original_get_double
        QInputDialog.getText = original_get_text
        QInputDialog.getItem = original_get_item
        QMessageBox.question = original_question
        QMessageBox.warning = original_warning
        QMessageBox.critical = original_critical
        QMessageBox.information = original_information
        _subprocess.Popen = original_popen
        VoiceManagerDialog.exec = original_voice_dialog_exec
        QPushButton.click = original_button_click

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
