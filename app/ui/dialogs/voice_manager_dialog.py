import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from app_paths import VOICES_DIR
from voice_recorder import record_voice_to_wav
from voice_store import add_voice_profile, load_voice_profiles


class VoiceManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Voice Manager")
        self.setMinimumWidth(540)

        layout = QVBoxLayout()

        consent_lbl = QLabel(
            "Voice profiles are recordings of voices you own or have permission to use.\n"
            "Do not use other people's voices without their consent."
        )
        consent_lbl.setStyleSheet("color:#e94560; font-style:italic;")
        layout.addWidget(consent_lbl)

        self.voice_list = QListWidget()
        self.voice_list.setToolTip("Double-click a profile to select it")
        self.refresh_voice_list()
        layout.addWidget(self.voice_list)

        name_row = QHBoxLayout()
        name_lbl = QLabel("Profile name:")
        name_row.addWidget(name_lbl)
        self.new_voice_name = QLineEdit()
        self.new_voice_name.setPlaceholderText("New voice profile name")
        self.new_voice_name.setToolTip("Enter a unique name for this voice profile")
        name_row.addWidget(self.new_voice_name, stretch=1)
        layout.addLayout(name_row)

        dur_row = QHBoxLayout()
        dur_lbl = QLabel("Clip duration (sec):")
        dur_lbl.setToolTip("How many seconds to record for voice training (longer = better match)")
        dur_row.addWidget(dur_lbl)
        self.duration_combo = QComboBox()
        for secs in [10, 20, 30, 60, 90, 120]:
            self.duration_combo.addItem(f"{secs} s", secs)
        self.duration_combo.setToolTip(
            "Recording duration. Longer clips improve voice model quality.\n"
            "A short script is provided below to help guide the recording."
        )
        dur_row.addWidget(self.duration_combo)
        dur_row.addStretch()
        layout.addLayout(dur_row)

        script_group = QGroupBox("Optional Speaking Script (read aloud during recording)")
        script_layout = QVBoxLayout(script_group)
        self.script_text = QTextEdit()
        self.script_text.setFixedHeight(90)
        self.script_text.setPlaceholderText(
            "Leave blank to record freely, or paste a script here to read aloud.\n\n"
            "Example: \"The quick brown fox jumps over the lazy dog. "
            "She sells sea shells by the seashore. How much wood would a woodchuck chuck…\""
        )
        self.script_text.setToolTip(
            "Reading a phonetically rich script improves voice model accuracy.\n"
            "This is optional — you may speak or sing freely instead."
        )
        script_layout.addWidget(self.script_text)
        layout.addWidget(script_group)

        btn_row = QHBoxLayout()
        record_btn = QPushButton("Record New Voice")
        record_btn.setToolTip("Start recording a new voice profile using the microphone")
        record_btn.clicked.connect(self.record_new_voice)
        btn_row.addWidget(record_btn)

        import_btn = QPushButton("Import Audio File")
        import_btn.setToolTip("Use an existing WAV/MP3 file as a voice profile instead of recording")
        import_btn.clicked.connect(self.import_voice_file)
        btn_row.addWidget(import_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self.setLayout(layout)

    def refresh_voice_list(self):
        self.voice_list.clear()
        profiles = load_voice_profiles()
        for p in profiles:
            item = QListWidgetItem(f"{p.name} [{p.file_path}]")
            item.setData(Qt.ItemDataRole.UserRole, p)
            self.voice_list.addItem(item)

    def record_new_voice(self):
        name = self.new_voice_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Input error", "Please enter a name for the voice profile.")
            return

        duration_sec = self.duration_combo.currentData() or 10

        confirm = QMessageBox.question(
            self,
            "Consent confirmation",
            "You should only record your own voice or voices you have explicit permission to use.\n\n"
            "Do you confirm this?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        output_wav = VOICES_DIR / f"{name.replace(' ', '_')}.wav"
        try:
            record_voice_to_wav(output_wav, duration_sec=duration_sec)
            add_voice_profile(name, output_wav)
            self.new_voice_name.clear()
            self.refresh_voice_list()
            QMessageBox.information(self, "Voice recorded", f"Saved voice profile: {name}")
        except Exception as e:
            QMessageBox.critical(self, "Recording error", f"Failed to record voice:\n{e}")

    def import_voice_file(self):
        """Import an existing audio file as a voice profile."""
        name = self.new_voice_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Input error", "Please enter a profile name before importing.")
            return

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Import voice audio file",
            "",
            "Audio Files (*.wav *.mp3 *.flac *.ogg);;All Files (*)"
        )
        if not filename:
            return

        confirm = QMessageBox.question(
            self,
            "Consent confirmation",
            "You should only import voice recordings of yourself or voices you have explicit permission to use.\n\n"
            "Do you confirm this?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            src = Path(filename)
            dest = VOICES_DIR / f"{name.replace(' ', '_')}.wav"
            if src.suffix.lower() == ".wav":
                shutil.copy2(src, dest)
            else:
                try:
                    import soundfile as sf
                    data, sr = sf.read(str(src))
                    sf.write(str(dest), data, sr)
                except Exception:
                    shutil.copy2(src, dest)
            add_voice_profile(name, dest)
            self.new_voice_name.clear()
            self.refresh_voice_list()
            QMessageBox.information(self, "Voice imported", f"Imported voice profile: {name}")
        except Exception as e:
            QMessageBox.critical(self, "Import error", f"Failed to import voice file:\n{e}")
