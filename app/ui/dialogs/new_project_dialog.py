from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class NewProjectDialog(QDialog):
    TEMPLATE_OPTIONS = [
        ("empty", "Empty", "Start from a blank timeline."),
        ("basic_4_track", "Basic 4-Track", "Four audio tracks ready for quick sketching."),
        ("podcast", "Podcast", "Host, guest, music bed, and SFX layout."),
        ("beat_maker", "Beat Maker", "Drums, bass, melody, and vocal lanes."),
        ("ai_stems_session", "AI Stems Session", "Reference mix plus stem-oriented tracks."),
    ]

    SAMPLE_RATE_OPTIONS = [
        ("44.1 kHz", 44100),
        ("48 kHz", 48000),
        ("88.2 kHz", 88200),
        ("96 kHz", 96000),
    ]

    def __init__(
        self,
        *,
        initial_name: str,
        initial_folder: Path,
        initial_sample_rate: int,
        initial_bpm: int,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setModal(True)
        self.setMinimumWidth(760)

        self._did_focus_name = False
        self._selected_template_id = "empty"
        self.result_config: Optional[Dict[str, object]] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QLabel("Create a New Echo Pro Project")
        title.setStyleSheet("font-size:16px; font-weight:600; color:#e2e2e5;")
        root.addWidget(title)

        form_grid = QGridLayout()
        form_grid.setHorizontalSpacing(8)
        form_grid.setVerticalSpacing(8)

        self.project_name_input = QLineEdit(str(initial_name or "Untitled"))
        self.project_name_input.setPlaceholderText("Project name")
        form_grid.addWidget(QLabel("Project Name"), 0, 0)
        form_grid.addWidget(self.project_name_input, 0, 1, 1, 2)

        self.folder_input = QLineEdit(str(initial_folder))
        self.folder_input.setPlaceholderText("Project folder")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_folder)
        form_grid.addWidget(QLabel("Folder"), 1, 0)
        form_grid.addWidget(self.folder_input, 1, 1)
        form_grid.addWidget(browse_btn, 1, 2)

        self.sample_rate_combo = QComboBox()
        for label, value in self.SAMPLE_RATE_OPTIONS:
            self.sample_rate_combo.addItem(label, int(value))
        sample_rate_index = self.sample_rate_combo.findData(int(initial_sample_rate))
        self.sample_rate_combo.setCurrentIndex(sample_rate_index if sample_rate_index >= 0 else 0)
        form_grid.addWidget(QLabel("Sample Rate"), 2, 0)
        form_grid.addWidget(self.sample_rate_combo, 2, 1)

        self.bpm_input = QSpinBox()
        self.bpm_input.setRange(30, 300)
        self.bpm_input.setValue(max(30, min(300, int(initial_bpm))))
        self.bpm_input.setSuffix(" BPM")
        form_grid.addWidget(QLabel("Tempo"), 2, 2)
        form_grid.addWidget(self.bpm_input, 2, 3)

        root.addLayout(form_grid)

        template_title = QLabel("Template")
        template_title.setStyleSheet("font-size:12px; font-weight:600; color:#aab4be;")
        root.addWidget(template_title)

        template_container = QWidget()
        template_grid = QGridLayout(template_container)
        template_grid.setContentsMargins(0, 0, 0, 0)
        template_grid.setHorizontalSpacing(10)
        template_grid.setVerticalSpacing(10)

        self._template_buttons: Dict[str, QPushButton] = {}
        for idx, (template_id, label, description) in enumerate(self.TEMPLATE_OPTIONS):
            button = QPushButton(f"{label}\n{description}")
            button.setCheckable(True)
            button.setMinimumHeight(84)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setProperty("templateRole", "tile")
            button.clicked.connect(lambda _checked=False, tid=template_id: self._set_selected_template(tid))
            row = idx // 2
            col = idx % 2
            template_grid.addWidget(button, row, col)
            self._template_buttons[template_id] = button

        template_container.setStyleSheet(
            "QPushButton[templateRole='tile'] {"
            " border:1px solid #2b3e53;"
            " border-radius:8px;"
            " padding:8px;"
            " text-align:left;"
            " background:#182534;"
            " color:#d4dde6;"
            "}"
            "QPushButton[templateRole='tile']:hover {"
            " border:1px solid #4d708f;"
            " background:#1c2f42;"
            "}"
            "QPushButton[templateRole='tile']:checked {"
            " border:1px solid #00f0ff;"
            " background:#103446;"
            " color:#ecfeff;"
            "}"
        )

        root.addWidget(template_container)

        button_row = QHBoxLayout()
        button_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        create_btn = QPushButton("Create Project")
        create_btn.setStyleSheet(
            "QPushButton {"
            " background:#00d6e6;"
            " color:#041016;"
            " font-weight:700;"
            " border:1px solid #00f0ff;"
            " border-radius:6px;"
            " padding:7px 14px;"
            "}"
            "QPushButton:hover { background:#20e9f6; }"
            "QPushButton:pressed { background:#00bfce; }"
        )
        create_btn.clicked.connect(self._accept_if_valid)
        button_row.addWidget(cancel_btn)
        button_row.addWidget(create_btn)
        root.addLayout(button_row)

        self._set_selected_template(self._selected_template_id)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._did_focus_name:
            self._did_focus_name = True
            self.project_name_input.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
            self.project_name_input.selectAll()

    def _browse_folder(self) -> None:
        current = self.folder_input.text().strip()
        start_dir = current if current else str(Path.home())
        selected = QFileDialog.getExistingDirectory(self, "Choose Project Folder", start_dir)
        if selected:
            self.folder_input.setText(selected)

    def _set_selected_template(self, template_id: str) -> None:
        if template_id not in self._template_buttons:
            template_id = "empty"
        self._selected_template_id = template_id
        for option_id, button in self._template_buttons.items():
            button.setChecked(option_id == template_id)

    def _accept_if_valid(self) -> None:
        project_name = self.project_name_input.text().strip()
        if not project_name:
            QMessageBox.warning(self, "New Project", "Project name is required.")
            self.project_name_input.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
            return

        folder_text = self.folder_input.text().strip()
        if not folder_text:
            QMessageBox.warning(self, "New Project", "Project folder is required.")
            self.folder_input.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
            return

        folder_path = Path(folder_text)
        if not folder_path.exists() or not folder_path.is_dir():
            QMessageBox.warning(self, "New Project", "Project folder must exist.")
            self.folder_input.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
            return

        sample_rate_value = self.sample_rate_combo.currentData()
        if not isinstance(sample_rate_value, int) or sample_rate_value <= 0:
            sample_rate_value = 44100

        self.result_config = {
            "project_name": project_name,
            "project_folder": str(folder_path),
            "template_id": str(self._selected_template_id),
            "sample_rate": int(sample_rate_value),
            "bpm": int(self.bpm_input.value()),
        }
        self.accept()
