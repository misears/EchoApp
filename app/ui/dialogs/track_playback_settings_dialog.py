from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from project_model import TrackEffectChain, TrackPlaybackSettings


class TrackPlaybackSettingsDialog(QDialog):
    def __init__(self, track_name: str, settings: TrackPlaybackSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Track Playback Settings - {track_name}")
        self.setMinimumWidth(420)

        root = QVBoxLayout(self)

        help_label = QLabel(
            "Configure per-track fades, looping, and a small starter effect chain.\n"
            "Looping repeats the selected region from the loop end onward during playback."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color:#aab4be;")
        root.addWidget(help_label)

        fade_group = QGroupBox("Fades")
        fade_form = QFormLayout(fade_group)
        self.fade_in_ms = QSpinBox()
        self.fade_in_ms.setRange(0, 60000)
        self.fade_in_ms.setSuffix(" ms")
        self.fade_in_ms.setValue(int(settings.fade_in_ms))
        fade_form.addRow("Fade in", self.fade_in_ms)

        self.fade_out_ms = QSpinBox()
        self.fade_out_ms.setRange(0, 60000)
        self.fade_out_ms.setSuffix(" ms")
        self.fade_out_ms.setValue(int(settings.fade_out_ms))
        fade_form.addRow("Fade out", self.fade_out_ms)
        root.addWidget(fade_group)

        loop_group = QGroupBox("Loop Region")
        loop_form = QFormLayout(loop_group)
        self.loop_enabled = QCheckBox("Enable loop region during playback")
        self.loop_enabled.setChecked(bool(settings.loop_enabled))
        loop_form.addRow(self.loop_enabled)

        self.loop_start_ms = QSpinBox()
        self.loop_start_ms.setRange(0, 600000)
        self.loop_start_ms.setSuffix(" ms")
        self.loop_start_ms.setValue(int(settings.loop_start_ms))
        loop_form.addRow("Loop start", self.loop_start_ms)

        self.loop_end_ms = QSpinBox()
        self.loop_end_ms.setRange(0, 600000)
        self.loop_end_ms.setSuffix(" ms")
        self.loop_end_ms.setValue(int(settings.loop_end_ms))
        loop_form.addRow("Loop end", self.loop_end_ms)
        root.addWidget(loop_group)

        effects = settings.effects

        echo_group = QGroupBox("Echo")
        echo_form = QFormLayout(echo_group)
        self.echo_enabled = QCheckBox("Enable echo")
        self.echo_enabled.setChecked(bool(effects.echo_enabled))
        echo_form.addRow(self.echo_enabled)

        self.echo_delay_ms = QSpinBox()
        self.echo_delay_ms.setRange(20, 2000)
        self.echo_delay_ms.setSuffix(" ms")
        self.echo_delay_ms.setValue(int(effects.echo_delay_ms))
        echo_form.addRow("Delay", self.echo_delay_ms)

        self.echo_decay = QDoubleSpinBox()
        self.echo_decay.setRange(0.0, 0.95)
        self.echo_decay.setSingleStep(0.05)
        self.echo_decay.setDecimals(2)
        self.echo_decay.setValue(float(effects.echo_decay))
        echo_form.addRow("Decay", self.echo_decay)

        self.echo_mix = QDoubleSpinBox()
        self.echo_mix.setRange(0.0, 1.0)
        self.echo_mix.setSingleStep(0.05)
        self.echo_mix.setDecimals(2)
        self.echo_mix.setValue(float(effects.echo_mix))
        echo_form.addRow("Mix", self.echo_mix)
        root.addWidget(echo_group)

        distortion_group = QGroupBox("Distortion")
        distortion_form = QFormLayout(distortion_group)
        self.distortion_enabled = QCheckBox("Enable distortion")
        self.distortion_enabled.setChecked(bool(effects.distortion_enabled))
        distortion_form.addRow(self.distortion_enabled)

        self.distortion_drive = QDoubleSpinBox()
        self.distortion_drive.setRange(1.0, 10.0)
        self.distortion_drive.setSingleStep(0.1)
        self.distortion_drive.setDecimals(2)
        self.distortion_drive.setValue(float(effects.distortion_drive))
        distortion_form.addRow("Drive", self.distortion_drive)

        self.distortion_mix = QDoubleSpinBox()
        self.distortion_mix.setRange(0.0, 1.0)
        self.distortion_mix.setSingleStep(0.05)
        self.distortion_mix.setDecimals(2)
        self.distortion_mix.setValue(float(effects.distortion_mix))
        distortion_form.addRow("Mix", self.distortion_mix)
        root.addWidget(distortion_group)

        chorus_group = QGroupBox("Chorus")
        chorus_form = QFormLayout(chorus_group)
        self.chorus_enabled = QCheckBox("Enable chorus")
        self.chorus_enabled.setChecked(bool(effects.chorus_enabled))
        chorus_form.addRow(self.chorus_enabled)

        self.chorus_depth_ms = QSpinBox()
        self.chorus_depth_ms.setRange(5, 80)
        self.chorus_depth_ms.setSuffix(" ms")
        self.chorus_depth_ms.setValue(int(effects.chorus_depth_ms))
        chorus_form.addRow("Depth", self.chorus_depth_ms)

        self.chorus_mix = QDoubleSpinBox()
        self.chorus_mix.setRange(0.0, 1.0)
        self.chorus_mix.setSingleStep(0.05)
        self.chorus_mix.setDecimals(2)
        self.chorus_mix.setValue(float(effects.chorus_mix))
        chorus_form.addRow("Mix", self.chorus_mix)
        root.addWidget(chorus_group)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons, alignment=Qt.AlignmentFlag.AlignRight)

    def _accept_if_valid(self) -> None:
        if self.loop_enabled.isChecked() and self.loop_end_ms.value() <= self.loop_start_ms.value():
            self.loop_end_ms.setFocus()
            return
        self.accept()

    def get_settings(self) -> TrackPlaybackSettings:
        return TrackPlaybackSettings(
            fade_in_ms=int(self.fade_in_ms.value()),
            fade_out_ms=int(self.fade_out_ms.value()),
            loop_enabled=bool(self.loop_enabled.isChecked()),
            loop_start_ms=int(self.loop_start_ms.value()),
            loop_end_ms=int(self.loop_end_ms.value()),
            effects=TrackEffectChain(
                echo_enabled=bool(self.echo_enabled.isChecked()),
                echo_delay_ms=int(self.echo_delay_ms.value()),
                echo_decay=float(self.echo_decay.value()),
                echo_mix=float(self.echo_mix.value()),
                distortion_enabled=bool(self.distortion_enabled.isChecked()),
                distortion_drive=float(self.distortion_drive.value()),
                distortion_mix=float(self.distortion_mix.value()),
                chorus_enabled=bool(self.chorus_enabled.isChecked()),
                chorus_depth_ms=int(self.chorus_depth_ms.value()),
                chorus_mix=float(self.chorus_mix.value()),
            ),
        )
