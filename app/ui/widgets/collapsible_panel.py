from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class CollapsiblePanel(QWidget):
    """A panel with a toggle button that shows/hides its content widget."""

    def __init__(self, title: str, content: QWidget, *, collapsed: bool = False, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._content = content
        self._collapsed = collapsed

        header = QHBoxLayout()
        header.setContentsMargins(4, 2, 4, 2)
        self._toggle_btn = QPushButton()
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setFixedSize(20, 20)
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.clicked.connect(self.toggle)
        self._title_lbl = QLabel(title)
        self._title_lbl.setStyleSheet("font-weight:bold; color:#dde1e7;")
        header.addWidget(self._toggle_btn)
        header.addWidget(self._title_lbl)
        header.addStretch()

        header_frame = QFrame()
        header_frame.setFrameShape(QFrame.StyledPanel)
        header_frame.setStyleSheet(
            "QFrame { background:#0f3460; border-radius:3px; padding:1px; }"
        )
        header_frame.setLayout(header)
        root.addWidget(header_frame)
        root.addWidget(content)

        self._update_state()

    def toggle(self):
        self._collapsed = not self._collapsed
        self._update_state()

    def _update_state(self):
        self._content.setVisible(not self._collapsed)
        self._toggle_btn.setText("▶" if self._collapsed else "▼")
        self._toggle_btn.setToolTip("Expand section" if self._collapsed else "Collapse section")
