from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPainter, QColor, QPen

from app.styles import C_L0, C_L3, C_CYAN, C_TEXT, C_MUTED, C_RED


class CustomTitleBar(QWidget):
    """Frameless title bar: waveform logo, app name, window chrome buttons."""

    HEIGHT = 36

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self._window = window
        self._drag_pos: QPoint | None = None

        self.setFixedHeight(self.HEIGHT)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"background-color: {C_L0}; border-bottom: 1px solid {C_L3};"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 4, 0)
        layout.setSpacing(6)

        layout.addWidget(_WaveformLogo())

        name = QLabel("EchoApp")
        name.setStyleSheet(
            f"color: {C_TEXT}; font-size: 12px; font-weight: bold;"
            " background: transparent; border: none;"
        )
        layout.addWidget(name)
        layout.addStretch()

        for symbol, tip, slot, hover in [
            ("\u2212", "Minimize",          self._minimize,         C_MUTED),
            ("\u25a1", "Maximize / Restore", self._maximize_restore, C_MUTED),
            ("\u00d7", "Close",              self._close,            C_RED),
        ]:
            btn = QPushButton(symbol)
            btn.setToolTip(tip)
            btn.setFixedSize(36, 36)
            btn.setStyleSheet(
                "QPushButton {"
                f"  background: transparent; color: {C_MUTED};"
                "  border: none; font-size: 16px;"
                "}"
                f"QPushButton:hover {{ background: {C_L3}; color: {hover}; }}"
            )
            btn.clicked.connect(slot)
            layout.addWidget(btn)

    # ── drag-to-move ──────────────────────────────────────────────────────────
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._drag_pos
            if not self._window.isMaximized():
                self._window.move(self._window.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._maximize_restore()

    # ── chrome button actions ─────────────────────────────────────────────────
    def _minimize(self) -> None:
        self._window.showMinimized()

    def _maximize_restore(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()

    def _close(self) -> None:
        self._window.close()


class _WaveformLogo(QWidget):
    """20×20 simple waveform bar icon drawn with QPainter."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(20, 20)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(C_CYAN), 1.5))
        mid = 10
        # Five vertical bars at increasing then decreasing heights
        for i, h in enumerate((5, 12, 16, 10, 7)):
            x = 2 + i * 4
            painter.drawLine(x, mid - h // 2, x, mid + h // 2)
