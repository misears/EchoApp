"""Stem workflow helper controller for Echo Pro windows."""

from __future__ import annotations

import re
import shutil
import time
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QDial, QFileDialog, QFrame, QHBoxLayout, QLabel, QListWidgetItem, QMessageBox, QPushButton

from app_paths import PROJECTS_DIR
from stems_engine import DEFAULT_DEMUCS_MODEL, add_stems_to_project, get_stem_backend_capability


class StemWorkflowController:
    """Controller for stem activity, progress UI, and preview helper behavior."""

    def __init__(self, window) -> None:
        self.window = window

    def classify_stem_log_level(self, message: str) -> str:
        lowered = str(message or "").lower()
        if "error" in lowered or "failed" in lowered or "missing" in lowered:
            return "error"
        if "warning" in lowered or "cancel" in lowered:
            return "warn"
        return "info"

    def append_stem_activity(self, text: str, *, reset: bool = False, level: Optional[str] = None) -> None:
        if not hasattr(self.window, "stem_activity_view"):
            return
        message = text.strip()
        if reset:
            self.window._stem_activity_lines = []
        if not message:
            self.refresh_stem_activity_log_view()
            return
        if self.window._stem_activity_lines:
            last = self.window._stem_activity_lines[-1]
            if isinstance(last, dict) and str(last.get("text", "")) == message:
                return
            if isinstance(last, str) and last == message:
                return
        log_level = str(level or self.classify_stem_log_level(message)).lower()
        if log_level not in {"info", "warn", "error"}:
            log_level = "info"
        timestamp = time.strftime("%H:%M:%S")
        entry = {"level": log_level, "time": timestamp, "text": message}
        self.window._stem_activity_lines.append(entry)
        self.window._stem_activity_lines = self.window._stem_activity_lines[-120:]
        self.refresh_stem_activity_log_view()

    def refresh_stem_activity_log_view(self) -> None:
        if not hasattr(self.window, "stem_activity_view"):
            return
        filter_mode = str(self.window._stem_progress_filter or "all")
        lines: list[str] = []
        for item in self.window._stem_activity_lines:
            if isinstance(item, dict):
                level = str(item.get("level", "info")).lower()
                text = str(item.get("text", "")).strip()
                at = str(item.get("time", ""))
            else:
                level = "info"
                text = str(item).strip()
                at = ""
            if not text:
                continue
            if filter_mode != "all" and level != filter_mode:
                continue
            prefix = "I"
            color = "#6ce47a"
            if level == "warn":
                prefix = "W"
                color = "#f0b55a"
            elif level == "error":
                prefix = "E"
                color = "#f16f6f"
            stamp = f"[{at}] " if at else ""
            safe_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            lines.append(f"<span style='color:{color};'>{prefix}</span> {stamp}{safe_text}")

        if not lines:
            self.window.stem_activity_view.setHtml("<span style='color:#8aa0b3;'>No activity lines for current filter.</span>")
            return
        self.window.stem_activity_view.setHtml("<br/>".join(lines))
        cursor = self.window.stem_activity_view.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.window.stem_activity_view.setTextCursor(cursor)

    def on_stem_log_filter_changed(self, *_args) -> None:
        if hasattr(self.window, "stem_log_filter_combo"):
            value = self.window.stem_log_filter_combo.currentData()
            self.window._stem_progress_filter = str(value or "all")
        self.refresh_stem_activity_log_view()

    def copy_stem_log(self) -> None:
        if not hasattr(self.window, "stem_activity_view"):
            return
        QApplication.clipboard().setText(self.window.stem_activity_view.toPlainText())
        self.window.update_status("Stem activity log copied")

    def save_stem_log(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self.window,
            "Save Stem Activity Log",
            "stem_activity.log",
            "Log Files (*.log);;Text Files (*.txt)",
        )
        if not filename:
            return
        try:
            Path(filename).write_text(self.window.stem_activity_view.toPlainText(), encoding="utf-8")
            self.window.update_status(f"Saved stem activity log: {filename}")
        except Exception as exc:
            QMessageBox.warning(self.window, "Save log", f"Could not save log:\n{exc}")

    def clear_stem_log(self) -> None:
        self.window._stem_activity_lines = []
        self.refresh_stem_activity_log_view()
        self.window.update_status("Stem activity log cleared")

    def set_stem_progress_state_label(self, text: str) -> None:
        if hasattr(self.window, "stem_progress_state_label"):
            self.window.stem_progress_state_label.setText(str(text))

    def reset_stem_progress_ui(self, *, state_text: str = "Idle") -> None:
        self.window._stem_last_percent = 0
        self.set_stem_progress_state_label(state_text)
        if hasattr(self.window, "stem_overall_progress"):
            self.window.stem_overall_progress.setValue(0)
        if hasattr(self.window, "stem_elapsed_label"):
            self.window.stem_elapsed_label.setText("Elapsed: 0s")
        if hasattr(self.window, "stem_eta_label"):
            self.window.stem_eta_label.setText("ETA: --")
        bars = getattr(self.window, "stem_per_stem_bars", {})
        if isinstance(bars, dict):
            for bar in bars.values():
                bar.setValue(0)

    def update_stem_elapsed_eta(self, percent: int) -> None:
        if self.window._stem_started_at is None:
            return
        elapsed = max(0, int(time.monotonic() - float(self.window._stem_started_at)))
        if hasattr(self.window, "stem_elapsed_label"):
            self.window.stem_elapsed_label.setText(f"Elapsed: {elapsed}s")
        if hasattr(self.window, "stem_eta_label"):
            if percent > 0:
                total_est = int((elapsed * 100.0) / float(percent))
                eta = max(0, total_est - elapsed)
                self.window.stem_eta_label.setText(f"ETA: {eta}s")
            else:
                self.window.stem_eta_label.setText("ETA: --")

    def update_stem_progress_from_message(self, message: str) -> None:
        text = str(message).strip()
        if not text:
            return

        lower = text.lower()
        if "loading" in lower or "launching" in lower or "downloading" in lower:
            self.set_stem_progress_state_label("Loading model...")
        elif "processing" in lower or "separating" in lower:
            self.set_stem_progress_state_label("Processing...")
        elif "collecting" in lower:
            self.set_stem_progress_state_label("Collecting stems...")
        elif "finished" in lower or "complete" in lower:
            self.set_stem_progress_state_label("Complete")

        percent_match = re.search(r"(\d{1,3})%", text)
        if percent_match is not None:
            try:
                percent = max(0, min(100, int(percent_match.group(1))))
            except ValueError:
                percent = self.window._stem_last_percent
            self.window._stem_last_percent = max(self.window._stem_last_percent, percent)
            if hasattr(self.window, "stem_overall_progress"):
                self.window.stem_overall_progress.setValue(int(self.window._stem_last_percent))
            self.update_stem_elapsed_eta(int(self.window._stem_last_percent))

            bars = getattr(self.window, "stem_per_stem_bars", {})
            ordered_names = ["vocals", "drums", "bass", "guitar", "piano", "other"]
            if isinstance(bars, dict) and bars:
                active_idx = min(len(ordered_names) - 1, int((self.window._stem_last_percent / 100.0) * len(ordered_names)))
                for idx, stem_name in enumerate(ordered_names):
                    bar = bars.get(stem_name)
                    if bar is None:
                        continue
                    if idx < active_idx:
                        bar.setValue(100)
                    elif idx == active_idx:
                        per = int((self.window._stem_last_percent * len(ordered_names)) % 100)
                        bar.setValue(max(5, min(100, per)))

    def set_stem_status(self, summary: str, *, detail: Optional[str] = None, reset_activity: bool = False) -> None:
        if hasattr(self.window, "stem_status_label"):
            self.window.stem_status_label.setText(summary)
        payload = detail or summary
        self.append_stem_activity(payload, reset=reset_activity)
        self.update_stem_progress_from_message(payload)

    def format_file_size(self, path: Path) -> str:
        try:
            size = float(path.stat().st_size)
        except Exception:
            return "unknown"
        units = ["B", "KB", "MB", "GB"]
        idx = 0
        while size >= 1024.0 and idx < len(units) - 1:
            size /= 1024.0
            idx += 1
        return f"{size:.1f} {units[idx]}"

    def project_folder_for_transfer(self) -> Path:
        folder_raw = str(self.window.current_project.metadata.get("project_folder", "") or "").strip()
        if folder_raw:
            return Path(folder_raw)
        if self.window._project_save_directory is not None:
            return Path(self.window._project_save_directory)
        return PROJECTS_DIR

    def render_waveform_ascii_for_file(self, file_path: Path, columns: int = 32) -> str:
        try:
            audio, _sr = sf.read(str(file_path), always_2d=True)
        except Exception:
            return "-" * columns
        if audio.shape[0] <= 0:
            return "-" * columns
        mono = np.mean(np.abs(audio), axis=1)
        if mono.size <= 0:
            return "-" * columns
        sample_positions = np.linspace(0, mono.size - 1, int(max(4, columns)), dtype=np.int32)
        sampled = mono[sample_positions]
        glyphs = "▁▂▃▄▅▆▇█"
        out = []
        for value in sampled:
            normalized = max(0.0, min(1.0, float(value)))
            idx = min(len(glyphs) - 1, int(round(normalized * (len(glyphs) - 1))))
            out.append(glyphs[idx])
        return "".join(out)

    def refresh_stem_preview_rows(self) -> None:
        if not hasattr(self.window, "stem_preview_rows_layout"):
            return
        layout = self.window.stem_preview_rows_layout
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not self.window._latest_stem_results:
            hint = QLabel("Run a separation to preview stems.")
            hint.setStyleSheet("color:#8aa0b3;")
            layout.addWidget(hint)
            return

        ordered_names = [name for name in ["vocals", "drums", "bass", "guitar", "piano", "other"] if name in self.window._latest_stem_results]
        extras = [name for name in self.window._latest_stem_results.keys() if name not in ordered_names]
        for stem_name in ordered_names + extras:
            file_path = Path(self.window._latest_stem_results[stem_name])
            row = QFrame()
            row.setFrameShape(QFrame.Shape.StyledPanel)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(6, 4, 6, 4)
            row_layout.setSpacing(6)

            name_label = QLabel(stem_name.title())
            name_label.setMinimumWidth(72)
            row_layout.addWidget(name_label)

            waveform = QLabel(self.render_waveform_ascii_for_file(file_path, columns=30))
            waveform.setStyleSheet("font-family:Consolas, monospace; color:#63d8ff;")
            waveform.setMinimumWidth(220)
            row_layout.addWidget(waveform, stretch=1)

            play_btn = QPushButton("Play")
            play_btn.clicked.connect(lambda _=False, n=stem_name: self.toggle_stem_preview_playback(n))
            row_layout.addWidget(play_btn)

            volume_dial = QDial()
            volume_dial.setRange(0, 100)
            volume_dial.setNotchesVisible(True)
            volume_dial.setFixedSize(36, 36)
            volume_dial.setValue(int(round(self.window._stem_preview_volume_by_name.get(stem_name, 70.0))))
            volume_dial.valueChanged.connect(lambda value, n=stem_name: self.set_stem_preview_volume(n, int(value)))
            row_layout.addWidget(volume_dial)

            row_layout.addWidget(QLabel(self.format_file_size(file_path)))
            layout.addWidget(row)

    def set_stem_preview_volume(self, stem_name: str, dial_value: int) -> None:
        self.window._stem_preview_volume_by_name[str(stem_name)] = max(0.0, min(1.0, float(dial_value) / 100.0))

    def toggle_stem_preview_playback(self, stem_name: str) -> None:
        name = str(stem_name)
        if self.window._stem_preview_playing_name == name:
            self.stop_stem_preview_playback()
            return
        self.play_stem_preview(name)

    def play_stem_preview(self, stem_name: str) -> None:
        path_raw = self.window._latest_stem_results.get(str(stem_name))
        if not path_raw:
            return
        file_path = Path(path_raw)
        if not file_path.exists():
            QMessageBox.warning(self.window, "Stem Preview", f"Stem file not found:\n{file_path}")
            return
        try:
            import sounddevice as sd  # type: ignore

            audio, sample_rate = sf.read(str(file_path), always_2d=True)
            gain = float(self.window._stem_preview_volume_by_name.get(str(stem_name), 0.7))
            preview = np.asarray(audio, dtype=np.float32) * max(0.0, min(1.0, gain))
            sd.stop()
            sd.play(preview, int(sample_rate), blocking=False)
            self.window._stem_preview_playing_name = str(stem_name)
            self.window.update_status(f"Previewing stem: {stem_name}")
        except Exception as exc:
            QMessageBox.warning(self.window, "Stem Preview", f"Could not preview stem:\n{exc}")

    def stop_stem_preview_playback(self) -> None:
        try:
            import sounddevice as sd  # type: ignore

            sd.stop()
        except Exception:
            pass
        self.window._stem_preview_playing_name = None

    def populate_stem_transfer_checklist(self) -> None:
        if not hasattr(self.window, "stem_transfer_checklist"):
            return
        self.window.stem_transfer_checklist.clear()
        if not self.window._latest_stem_results:
            return
        ordered_names = [name for name in ["vocals", "drums", "bass", "guitar", "piano", "other"] if name in self.window._latest_stem_results]
        extras = [name for name in self.window._latest_stem_results.keys() if name not in ordered_names]
        for stem_name in ordered_names + extras:
            stem_path = Path(self.window._latest_stem_results[stem_name])
            item = QListWidgetItem(f"{stem_name.title()}  ({self.format_file_size(stem_path)})")
            item.setData(Qt.ItemDataRole.UserRole, stem_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.window.stem_transfer_checklist.addItem(item)

    def checked_stem_names(self) -> list[str]:
        names: list[str] = []
        if not hasattr(self.window, "stem_transfer_checklist"):
            return names
        for idx in range(self.window.stem_transfer_checklist.count()):
            item = self.window.stem_transfer_checklist.item(idx)
            if item is None:
                continue
            if item.checkState() != Qt.CheckState.Checked:
                continue
            stem_name = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
            if stem_name and stem_name in self.window._latest_stem_results:
                names.append(stem_name)
        return names

    def copy_selected_stems_to_project_folder(self, stem_names: list[str]) -> Optional[Path]:
        if not stem_names:
            return None
        if not hasattr(self.window, "stem_transfer_save_checkbox") or not self.window.stem_transfer_save_checkbox.isChecked():
            return None
        subfolder_pattern = "stems"
        if hasattr(self.window, "stem_transfer_subfolder_input"):
            subfolder_pattern = str(self.window.stem_transfer_subfolder_input.text() or "stems").strip() or "stems"
        target_root = self.project_folder_for_transfer() / subfolder_pattern
        target_root.mkdir(parents=True, exist_ok=True)
        for stem_name in stem_names:
            src = Path(self.window._latest_stem_results[stem_name])
            if not src.exists():
                continue
            try:
                shutil.copy2(str(src), str(target_root / src.name))
            except Exception:
                continue
        return target_root

    def transfer_selected_stems_to_project(self) -> None:
        if not self.window._latest_stem_results:
            QMessageBox.information(self.window, "Transfer Stems", "No stem results are ready to transfer.")
            return
        checked = self.checked_stem_names()
        if not checked:
            QMessageBox.information(self.window, "Transfer Stems", "Select at least one stem to transfer.")
            return
        selected_stems = {name: self.window._latest_stem_results[name] for name in checked}
        pre_count = len(self.window.current_project.tracks)
        insert_mode = "append"
        if hasattr(self.window, "stem_transfer_insert_combo"):
            insert_mode = str(self.window.stem_transfer_insert_combo.currentData() or "append").strip().lower()
        self.window.next_clip_id = add_stems_to_project(
            self.window.current_project,
            selected_stems,
            self.window._latest_stem_output_dir or Path("."),
            next_clip_id_start=self.window.next_clip_id,
        )
        if insert_mode == "top":
            total_tracks = len(self.window.current_project.tracks)
            new_count = max(0, total_tracks - pre_count)
            if new_count > 0:
                order = list(range(pre_count, total_tracks)) + list(range(0, pre_count))
                remap = {old_idx: new_idx for new_idx, old_idx in enumerate(order)}
                self.window.current_project.tracks = [self.window.current_project.tracks[idx] for idx in order]
                for clip in self.window.current_project.clips:
                    original = int(getattr(clip, "track_index", 0))
                    if original in remap:
                        clip.track_index = int(remap[original])
        if hasattr(self.window, "stem_transfer_auto_color_checkbox") and self.window.stem_transfer_auto_color_checkbox.isChecked():
            color_map = {
                "vocals": "#f36f9f",
                "drums": "#f6bd60",
                "bass": "#4dd7ff",
                "guitar": "#7fd29c",
                "piano": "#b79cff",
                "other": "#9aa7b6",
            }
            for track in self.window.current_project.tracks[pre_count:]:
                stem_key = str(track.name or "").strip().lower()
                if stem_key in color_map:
                    track.color_hex = color_map[stem_key]

        copied_dir = self.copy_selected_stems_to_project_folder(checked)
        self.window.sync_project_tracks_to_recording_engine()
        self.window.refresh_track_list()
        self.window.refresh_timeline()

        message = f"Transferred {len(checked)} stem(s) to project tracks."
        if copied_dir is not None:
            message += f" Copies saved to {copied_dir}."
        self.set_stem_status("Stem transfer complete.", detail=message)
        self.window.update_status(message)

    def send_selected_stem_to_ace_step(self) -> None:
        if not self.window._latest_stem_results:
            QMessageBox.information(self.window, "Transfer to ACE-Step", "No stem results are ready.")
            return
        checked = self.checked_stem_names()
        if not checked:
            QMessageBox.information(self.window, "Transfer to ACE-Step", "Select at least one stem first.")
            return
        selected = checked[0]
        stem_path = self.window._latest_stem_results[selected]
        self.window._sync_transfer_options_between_ace_and_stems("stems")
        self.window.ace_audio_reference_upload_path = Path(stem_path)
        if hasattr(self.window, "ace_audio_reference_source_combo"):
            self.window.ace_audio_reference_source_combo.setCurrentText("Upload")
        self.window._refresh_ace_audio_reference_preview()
        self.window._switch_to_tab("AI Generation (ACE-Step)")
        self.window.update_status(f"Stem ready for ACE-Step reference: {selected} ({stem_path})")
        QMessageBox.information(
            self.window,
            "Transfer to ACE-Step",
            f"Selected stem prepared: {selected}\n{stem_path}\n\nUse the AI Generation (ACE-Step) tab to continue generation with this reference.",
        )

    def update_stem_backend_summary(self) -> None:
        if not hasattr(self.window, "stem_backend_label"):
            return
        capability = get_stem_backend_capability()
        backend_text = f"Backend: {capability['backend']}"
        if capability["ready"]:
            backend_text += f" ready ({capability['demucs_executable']})"
        else:
            backend_text += f" needs setup - {capability['reason']}"
        self.window.stem_backend_label.setText(backend_text)
        self.refresh_stem_device_indicator()

    def refresh_stem_device_indicator(self) -> None:
        if not hasattr(self.window, "stem_vram_indicator"):
            return
        capability = get_stem_backend_capability()
        selected_device = "auto"
        if hasattr(self.window, "stem_device_combo"):
            current = self.window.stem_device_combo.currentData()
            if isinstance(current, str):
                selected_device = current.lower()
        force_cpu = bool(getattr(self.window, "stem_force_cpu_checkbox", None).isChecked()) if hasattr(self.window, "stem_force_cpu_checkbox") else False

        if not bool(capability.get("ready", False)):
            text = "Runtime missing"
            color = "#d34f5a"
        elif force_cpu or selected_device == "cpu":
            text = "CPU mode"
            color = "#e6a23c"
        elif selected_device == "cuda":
            text = "GPU candidate"
            color = "#26d07c"
        else:
            text = "Auto-detect"
            color = "#2cc7de"

        self.window.stem_vram_indicator.setText(text)
        self.window.stem_vram_indicator.setStyleSheet(
            f"color:{color}; font-family:Consolas, monospace; font-size:11px; font-weight:600;"
        )

    def set_stem_processing_state(self, processing: bool) -> None:
        self.window._stem_is_processing = bool(processing)
        split_button = getattr(self.window, "stem_split_btn", None)
        cancel_button = getattr(self.window, "stem_cancel_btn", None)

        if split_button is None:
            return

        if processing:
            self.window._stem_started_at = time.monotonic()
            split_button.setText("Separating...")
            split_button.setEnabled(False)
            self.window._stem_pulse_state = False
            self.apply_stem_processing_button_style()
            if not hasattr(self.window, "_stem_pulse_timer"):
                self.window._stem_pulse_timer = QTimer(self.window)
                self.window._stem_pulse_timer.setInterval(420)
                self.window._stem_pulse_timer.timeout.connect(self.window._on_stem_processing_pulse)
            self.window._stem_pulse_timer.start()
            if cancel_button is not None:
                cancel_button.setVisible(True)
                cancel_button.setEnabled(True)
            self.set_stem_progress_state_label("Processing...")
            return

        if hasattr(self.window, "_stem_pulse_timer"):
            self.window._stem_pulse_timer.stop()
        split_button.setText("Separate")
        split_button.setStyleSheet(
            "QPushButton {"
            " background:#1f6f3f;"
            " color:#f5fff7;"
            " border:1px solid #3dc57a;"
            " border-radius:6px;"
            " padding:8px 12px;"
            " font-weight:700;"
            "}"
            "QPushButton:hover { background:#278c4f; }"
            "QPushButton:pressed { background:#166138; }"
            "QPushButton:disabled { background:#2a3038; color:#8e98a6; border-color:#3a4655; }"
        )
        if cancel_button is not None:
            cancel_button.setVisible(False)
            cancel_button.setEnabled(False)

        self.window._stem_started_at = None

        self.refresh_stem_section_state()

    def apply_stem_processing_button_style(self) -> None:
        split_button = getattr(self.window, "stem_split_btn", None)
        if split_button is None:
            return
        active_bg = "#a0621e" if self.window._stem_pulse_state else "#8b4f18"
        active_border = "#ffc062" if self.window._stem_pulse_state else "#d69a48"
        split_button.setStyleSheet(
            "QPushButton {"
            f" background:{active_bg};"
            " color:#fff6e8;"
            f" border:1px solid {active_border};"
            " border-radius:6px;"
            " padding:8px 12px;"
            " font-weight:700;"
            "}"
            "QPushButton:disabled { color:#fff0dc; }"
        )

    def on_stem_processing_pulse(self) -> None:
        if not bool(self.window._stem_is_processing):
            return
        self.window._stem_pulse_state = not bool(self.window._stem_pulse_state)
        self.apply_stem_processing_button_style()

    def refresh_stem_section_state(self) -> None:
        self.update_stem_backend_summary()
        if not hasattr(self.window, "stem_split_btn"):
            return

        selected_source = self.window.stem_source_path
        source_exists = selected_source is not None and selected_source.exists()
        self.window.stem_split_btn.setEnabled(bool(source_exists) and not bool(self.window._stem_is_processing))

        if hasattr(self.window, "stem_source_input"):
            self.window.stem_source_input.setText(str(selected_source) if selected_source is not None else "")

        if hasattr(self.window, "stem_source_drop_zone"):
            self.window.stem_source_drop_zone.set_current_path(selected_source)

        if hasattr(self.window, "stem_output_label"):
            if selected_source is not None:
                output_dir = selected_source.parent / "echo_stems" / selected_source.stem
                self.window.stem_output_dir = output_dir
                self.window.stem_output_label.setText(f"Output folder: {output_dir}")
            else:
                self.window.stem_output_dir = None
                self.window.stem_output_label.setText("Output folder: choose source audio to preview the stem folder.")

        if hasattr(self.window, "stem_transfer_target_label"):
            self.window.stem_transfer_target_label.setText(f"Project folder: {self.project_folder_for_transfer()}")

        if not source_exists and hasattr(self.window, "stem_status_label"):
            self.window.stem_status_label.setText("Choose source audio to enable Demucs splitting.")

        self.refresh_stem_device_indicator()

    def cancel_selected_stem_split(self) -> None:
        worker = self.window._stem_worker
        if worker is None or not self.window._stem_is_processing:
            return
        worker.request_cancel()
        self.set_stem_status("Cancelling stem split...", detail="Cancellation requested.")
        self.window.update_status("Cancelling Demucs separation...")

    def set_stem_source_path(self, song_path: Optional[Path]) -> None:
        self.window.stem_source_path = song_path.resolve() if song_path is not None else None
        self.refresh_stem_section_state()
        if self.window.stem_source_path is not None:
            self.set_stem_status(
                "Stem source ready.",
                detail=f"Selected source audio: {self.window.stem_source_path.name}",
                reset_activity=True,
            )

    def on_stem_source_dropped(self, song_path: Path) -> None:
        if not song_path.exists() or not song_path.is_file():
            self.window.update_status("Dropped source path is not a file")
            return
        self.set_stem_source_path(song_path)

    def show_demucs_model_manager_placeholder(self) -> None:
        QMessageBox.information(
            self.window,
            "Manage Demucs Models",
            "Model management is being moved into Settings -> Model Manager.\n"
            "For now, install/update model assets via install_echo_pro.bat install/update.",
        )

    def choose_stem_source_audio(self) -> None:
        initial_dir = ""
        if self.window.stem_source_path is not None:
            initial_dir = str(self.window.stem_source_path.parent)
        elif PROJECTS_DIR.exists():
            initial_dir = str(PROJECTS_DIR)
        filename, _ = QFileDialog.getOpenFileName(
            self.window,
            "Choose song to split into stems",
            initial_dir,
            "Audio Files (*.wav *.mp3 *.flac *.ogg);;All Files (*)",
        )
        if not filename:
            return
        self.set_stem_source_path(Path(filename))

    def selected_demucs_model(self) -> str:
        if hasattr(self.window, "stem_model_combo"):
            model_name = self.window.stem_model_combo.currentData()
            if isinstance(model_name, str) and model_name.strip():
                return model_name
        return DEFAULT_DEMUCS_MODEL

    def run_selected_stem_split(self) -> None:
        if self.window.stem_source_path is None or not self.window.stem_source_path.exists():
            self.choose_stem_source_audio()
            if self.window.stem_source_path is None or not self.window.stem_source_path.exists():
                return
        self.start_stem_separation_worker(self.window.stem_source_path)

    def clear_stem_worker(self) -> None:
        if self.window._stem_worker_thread is not None:
            self.window._stem_worker_thread.quit()
            self.window._stem_worker_thread.wait(2000)
            self.window._stem_worker_thread.deleteLater()
        self.window._stem_worker_thread = None
        self.window._stem_worker = None
        self.set_stem_processing_state(False)

    def on_stem_worker_progress(self, message: str) -> None:
        text = str(message).strip()
        if not text:
            return
        self.set_stem_status(text, detail=text)
        self.window.update_status(text)

    def on_stem_worker_completed(self, payload: dict) -> None:
        self.clear_stem_worker()
        stems = payload.get("stems", {}) if isinstance(payload, dict) else {}
        if not isinstance(stems, dict) or not stems:
            self.set_stem_status("Stem split failed.", detail="No stems were returned by Demucs.")
            QMessageBox.warning(self.window, "Stems", "Demucs completed but no stems were returned.")
            return

        output_dir_raw = payload.get("output_dir", "") if isinstance(payload, dict) else ""
        output_dir = Path(str(output_dir_raw)) if output_dir_raw else Path(".")
        model_name = str(payload.get("model_name", self.selected_demucs_model())) if isinstance(payload, dict) else self.selected_demucs_model()
        source_name = str(payload.get("source_name", "source audio")) if isinstance(payload, dict) else "source audio"

        self.window._latest_stem_results = {str(name): str(path) for name, path in stems.items()}
        self.window._latest_stem_output_dir = output_dir
        self.populate_stem_transfer_checklist()
        self.refresh_stem_preview_rows()

        if hasattr(self.window, "stem_transfer_btn"):
            self.window.stem_transfer_btn.setEnabled(True)
        if hasattr(self.window, "stem_to_ace_btn"):
            self.window.stem_to_ace_btn.setEnabled(True)
        if hasattr(self.window, "stem_overall_progress"):
            self.window.stem_overall_progress.setValue(100)
        self.set_stem_progress_state_label("Complete")
        self.update_stem_elapsed_eta(100)

        stem_count = len(stems)
        self.set_stem_status(
            f"Stem split complete: {stem_count} stems ready from {source_name}.",
            detail=f"Demucs completed with {stem_count} stems from {model_name}. Select transfer options to continue.",
        )
        self.window.update_status("Stems ready for transfer")

    def on_stem_worker_cancelled(self, message: str) -> None:
        self.clear_stem_worker()
        text = str(message).strip() or "Stem separation cancelled."
        self.set_stem_status("Stem split cancelled.", detail=text)
        self.window.update_status("Stems cancelled")

    def on_stem_worker_failed(self, error_kind: str, message: str) -> None:
        self.clear_stem_worker()
        text = str(message).strip() or "Demucs failed."
        kind = str(error_kind).strip().lower()

        if kind == "dependency":
            self.set_stem_status("Stem backend needs setup.", detail=text)
            install_choice = QMessageBox.question(
                self.window,
                "Missing dependency",
                f"{text}\n\nRun dependency update now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if install_choice == QMessageBox.StandardButton.Yes and self.window._run_dependency_update_dialog("update"):
                if self.window.stem_source_path is not None and self.window.stem_source_path.exists():
                    self.start_stem_separation_worker(self.window.stem_source_path)
                return
            self.window.update_status("Stems dependency issue")
            return

        self.set_stem_status("Stem split failed.", detail=text)
        QMessageBox.critical(self.window, "Error", f"Failed to split stems:\n{text}")
        self.window.update_status("Stems error")

    def start_stem_separation_worker(self, song_path: Path) -> None:
        self.window._start_stem_separation_worker(song_path)
