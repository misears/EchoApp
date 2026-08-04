from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QComboBox, QDial, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSlider, QVBoxLayout

from .level_meter import VerticalLevelMeter


class TrackMixerRow(QFrame):
    """220px channel strip with inline edit, arm/mute/solo, pan, sends, and EQ entrypoint."""

    def __init__(
        self,
        track_index: int,
        track_name: str,
        *,
        on_volume_change=None,
        on_pan_change=None,
        on_mute_toggle=None,
        on_solo_toggle=None,
        on_arm_toggle=None,
        on_name_change=None,
        on_color_change=None,
        on_input_change=None,
        on_send_change=None,
        on_automation_param_change=None,
        on_open_playback_settings=None,
        parent=None,
    ):
        super().__init__(parent)
        self.track_index = track_index
        self._on_volume_change = on_volume_change
        self._on_pan_change = on_pan_change
        self._on_mute_toggle = on_mute_toggle
        self._on_solo_toggle = on_solo_toggle
        self._on_arm_toggle = on_arm_toggle
        self._on_name_change = on_name_change
        self._on_color_change = on_color_change
        self._on_input_change = on_input_change
        self._on_send_change = on_send_change
        self._on_automation_param_change = on_automation_param_change
        self._on_open_playback_settings = on_open_playback_settings
        self._track_color_hex = "#00F0FF"

        self.setObjectName("TrackMixerRow")
        self.setFrameShape(QFrame.StyledPanel)
        self.setFixedWidth(220)
        self.setMinimumHeight(520)
        self.setStyleSheet(
            "QFrame#TrackMixerRow { background:#1E1E22; border:1px solid #2D2D32; border-radius:6px; }"
            "QPushButton#ColorSwatch { border:1px solid #2D2D32; border-radius:7px; min-width:14px; max-width:14px; min-height:14px; max-height:14px; padding:0; }"
            "QPushButton#RecordArmButton { background:#2A1418; color:#FF3366; border:1px solid #6A2630; font-weight:bold; }"
            "QPushButton#RecordArmButton:checked { background:#3A0E18; border:1px solid #FF3366; color:#FF3366; }"
            "QLineEdit#TrackNameEdit, QComboBox#TrackInputCombo { background:#0E0E10; border:1px solid #2D2D32; color:#E2E2E5; padding:3px 6px; border-radius:4px; }"
            "QPushButton#EqMiniGraph { background:#16161A; border:1px solid #2D2D32; color:#909095; font-size:8px; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 10)
        root.setSpacing(5)

        header_row = QHBoxLayout()
        header_row.setSpacing(6)
        badge = QLabel(str(track_index + 1))
        badge.setFixedSize(20, 20)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet("background:#0f3460; border-radius:10px; color:#e94560; font-weight:bold; font-size:9px;")
        header_row.addWidget(badge)

        self.color_button = QPushButton("")
        self.color_button.setObjectName("ColorSwatch")
        self.color_button.setToolTip("Pick the track color.")
        self.color_button.clicked.connect(self._pick_track_color)
        header_row.addWidget(self.color_button)

        self.name_edit = QLineEdit(track_name)
        self.name_edit.setObjectName("TrackNameEdit")
        self.name_edit.setPlaceholderText("Track name")
        self.name_edit.editingFinished.connect(self._name_edit_finished)
        header_row.addWidget(self.name_edit, stretch=1)
        root.addLayout(header_row)

        self.input_combo = QComboBox()
        self.input_combo.setObjectName("TrackInputCombo")
        self.input_combo.addItems(["Auto", "Input 1", "Input 2", "Stereo 1/2", "Bus A", "Bus B"])
        self.input_combo.setToolTip("Track input source.")
        self.input_combo.currentTextChanged.connect(self._input_changed)
        root.addWidget(self.input_combo)

        meter_lbl = QLabel("L / R Meter")
        meter_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        meter_lbl.setStyleSheet("font-size:8px; color:#aab4be;")
        root.addWidget(meter_lbl)

        meter_row = QHBoxLayout()
        meter_row.setSpacing(4)
        self.meter_l = VerticalLevelMeter()
        self.meter_l.setMinimumHeight(92)
        self.meter_r = VerticalLevelMeter()
        self.meter_r.setMinimumHeight(92)
        self.peak_label = QLabel("-∞")
        self.peak_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.peak_label.setStyleSheet("font-size:8px; color:#aab4be;")
        meter_row.addStretch()
        meter_row.addWidget(self.meter_l)
        meter_row.addWidget(self.meter_r)
        meter_row.addStretch()
        root.addLayout(meter_row)
        root.addWidget(self.peak_label)

        eq_lbl = QLabel("EQ / Sends")
        eq_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        eq_lbl.setStyleSheet("font-size:8px; color:#aab4be;")
        root.addWidget(eq_lbl)

        self.eq_button = QPushButton("EQ Curve")
        self.eq_button.setObjectName("EqMiniGraph")
        self.eq_button.setFixedHeight(28)
        self.eq_button.setToolTip("Open the track EQ panel.")
        self.eq_button.clicked.connect(self._open_playback_settings)
        root.addWidget(self.eq_button)

        self.automation_param_combo = QComboBox()
        self.automation_param_combo.addItem("Auto: Volume", "volume_db")
        self.automation_param_combo.addItem("Auto: Pan", "pan")
        self.automation_param_combo.addItem("Auto: Send A", "send_a")
        self.automation_param_combo.addItem("Auto: Send B", "send_b")
        self.automation_param_combo.setToolTip("Choose which parameter to edit as inline automation on the timeline.")
        self.automation_param_combo.currentIndexChanged.connect(self._automation_parameter_changed)
        root.addWidget(self.automation_param_combo)

        control_row = QHBoxLayout()
        control_row.setSpacing(8)

        fader_col = QVBoxLayout()
        fader_col.setSpacing(2)
        self.db_label = QLabel("0 dB")
        self.db_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.db_label.setStyleSheet("font-size:9px;")
        fader_col.addWidget(self.db_label)
        self.vol_slider = QSlider(Qt.Orientation.Vertical)
        self.vol_slider.setRange(-60, 6)
        self.vol_slider.setValue(0)
        self.vol_slider.setMinimumHeight(150)
        self.vol_slider.setFixedWidth(20)
        self.vol_slider.setToolTip("Track gain: -60 dB to +6 dB")
        self.vol_slider.valueChanged.connect(self._volume_changed)
        fader_col.addWidget(self.vol_slider, alignment=Qt.AlignmentFlag.AlignHCenter)
        fader_lbl = QLabel("GAIN")
        fader_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fader_lbl.setStyleSheet("font-size:8px; color:#aab4be;")
        fader_col.addWidget(fader_lbl)
        control_row.addLayout(fader_col)

        right_stack = QVBoxLayout()
        right_stack.setSpacing(5)

        pan_col = QVBoxLayout()
        pan_col.setSpacing(1)
        self.pan_knob = QDial()
        self.pan_knob.setRange(-100, 100)
        self.pan_knob.setValue(0)
        self.pan_knob.setFixedSize(40, 40)
        self.pan_knob.setNotchesVisible(True)
        self.pan_knob.setToolTip("Pan: left (L) to right (R)")
        self.pan_knob.valueChanged.connect(self._pan_changed)
        pan_col.addWidget(self.pan_knob, alignment=Qt.AlignmentFlag.AlignCenter)
        pan_lbl = QLabel("PAN")
        pan_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pan_lbl.setStyleSheet("font-size:8px; color:#aab4be;")
        pan_col.addWidget(pan_lbl)
        right_stack.addLayout(pan_col)

        send_row = QHBoxLayout()
        send_row.setSpacing(10)
        self.send_a_knob = self._build_send_knob("Bus 1")
        self.send_b_knob = self._build_send_knob("Bus 2")
        self.send_a_knob["knob"].valueChanged.connect(lambda value: self._send_changed("a", value))
        self.send_b_knob["knob"].valueChanged.connect(lambda value: self._send_changed("b", value))
        send_row.addLayout(self.send_a_knob["layout"])
        send_row.addLayout(self.send_b_knob["layout"])
        right_stack.addLayout(send_row)
        right_stack.addStretch()

        control_row.addLayout(right_stack)
        control_row.addStretch()
        root.addLayout(control_row)

        pms_row = QHBoxLayout()
        pms_row.setSpacing(3)
        self.arm_btn = QPushButton("R")
        self.arm_btn.setObjectName("RecordArmButton")
        self.arm_btn.setCheckable(True)
        self.arm_btn.setFixedSize(28, 22)
        self.arm_btn.setToolTip("Record-arm this channel")
        self.arm_btn.clicked.connect(self._arm_clicked)
        pms_row.addWidget(self.arm_btn)

        self.mute_btn = QPushButton("M")
        self.mute_btn.setCheckable(True)
        self.mute_btn.setFixedSize(28, 22)
        self.mute_btn.setProperty("channelBtn", "mute")
        self.mute_btn.setToolTip("Mute this channel")
        self.mute_btn.clicked.connect(self._mute_clicked)
        pms_row.addWidget(self.mute_btn)

        self.solo_btn = QPushButton("S")
        self.solo_btn.setCheckable(True)
        self.solo_btn.setFixedSize(28, 22)
        self.solo_btn.setProperty("channelBtn", "solo")
        self.solo_btn.setToolTip("Solo this channel (silences all others)")
        self.solo_btn.clicked.connect(self._solo_clicked)
        pms_row.addWidget(self.solo_btn)
        pms_row.addStretch()
        root.addLayout(pms_row)

        playback_row = QHBoxLayout()
        playback_row.setSpacing(4)
        self.fx_btn = QPushButton("FX")
        self.fx_btn.setFixedSize(40, 22)
        self.fx_btn.setToolTip("Open playback settings for fades, loop region, and starter effects")
        self.fx_btn.clicked.connect(self._open_playback_settings)
        playback_row.addWidget(self.fx_btn)
        self.playback_summary = QLabel("DRY")
        self.playback_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.playback_summary.setStyleSheet("font-size:8px; color:#aab4be;")
        playback_row.addWidget(self.playback_summary, stretch=1)
        root.addLayout(playback_row)
        root.addStretch()

        self.set_track_color(self._track_color_hex)

    def _build_send_knob(self, label_text: str) -> dict:
        layout = QVBoxLayout()
        layout.setSpacing(1)
        knob = QDial()
        knob.setRange(0, 100)
        knob.setValue(0)
        knob.setFixedSize(32, 32)
        knob.setNotchesVisible(True)
        knob.setToolTip(f"{label_text} send level")
        label = QLabel(label_text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size:7px; color:#aab4be;")
        layout.addWidget(knob, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        return {"knob": knob, "layout": layout}

    def _volume_changed(self, value: int):
        self.db_label.setText(f"{value:+d} dB" if value != 0 else "0 dB")
        if self._on_volume_change:
            self._on_volume_change(self.track_index, float(value))

    def _pan_changed(self, value: int) -> None:
        if self._on_pan_change:
            self._on_pan_change(self.track_index, float(value) / 100.0)

    def _mute_clicked(self, checked: bool):
        if self._on_mute_toggle:
            self._on_mute_toggle(self.track_index, checked)

    def _solo_clicked(self, checked: bool):
        if self._on_solo_toggle:
            self._on_solo_toggle(self.track_index, checked)

    def _arm_clicked(self, checked: bool) -> None:
        if self._on_arm_toggle:
            self._on_arm_toggle(self.track_index, checked)

    def _name_edit_finished(self) -> None:
        if self._on_name_change:
            self._on_name_change(self.track_index, self.name_edit.text().strip())

    def _pick_track_color(self) -> None:
        selected = QColorDialog.getColor(QColor(self._track_color_hex), self, "Choose Track Color")
        if selected.isValid():
            self.set_track_color(selected.name())
            if self._on_color_change:
                self._on_color_change(self.track_index, selected.name())

    def _input_changed(self, value: str) -> None:
        if self._on_input_change:
            self._on_input_change(self.track_index, value)

    def _open_playback_settings(self) -> None:
        if self._on_open_playback_settings:
            self._on_open_playback_settings(self.track_index)

    def _send_changed(self, bus: str, value: int) -> None:
        if self._on_send_change:
            normalized = max(0.0, min(1.0, float(value) / 100.0))
            self._on_send_change(self.track_index, bus, normalized)

    def _automation_parameter_changed(self) -> None:
        if not self._on_automation_param_change:
            return
        parameter = str(self.automation_param_combo.currentData() or "volume_db")
        self._on_automation_param_change(self.track_index, parameter)

    def set_volume_db(self, db: float):
        self.vol_slider.blockSignals(True)
        self.vol_slider.setValue(int(db))
        self.db_label.setText(f"{int(db):+d} dB" if int(db) != 0 else "0 dB")
        self.vol_slider.blockSignals(False)

    def set_pan(self, pan: float) -> None:
        self.pan_knob.blockSignals(True)
        self.pan_knob.setValue(int(max(-1.0, min(1.0, float(pan))) * 100.0))
        self.pan_knob.blockSignals(False)

    def update_meter(self, current_db: float, peak_db: float):
        self.meter_l.set_db(current_db)
        self.meter_r.set_db(current_db)
        self.peak_label.setText(f"{peak_db:.0f}")

    def set_mute(self, muted: bool) -> None:
        self.mute_btn.blockSignals(True)
        self.mute_btn.setChecked(bool(muted))
        self.mute_btn.blockSignals(False)

    def set_solo(self, soloed: bool) -> None:
        self.solo_btn.blockSignals(True)
        self.solo_btn.setChecked(bool(soloed))
        self.solo_btn.blockSignals(False)

    def set_armed(self, armed: bool) -> None:
        self.arm_btn.blockSignals(True)
        self.arm_btn.setChecked(bool(armed))
        self.arm_btn.blockSignals(False)

    def set_track_name(self, name: str) -> None:
        self.name_edit.blockSignals(True)
        self.name_edit.setText(name)
        self.name_edit.blockSignals(False)

    def set_track_color(self, color_hex: str) -> None:
        self._track_color_hex = color_hex or "#00F0FF"
        self.color_button.setStyleSheet(f"background:{self._track_color_hex}; border:1px solid #2D2D32; border-radius:7px;")

    def set_input_source(self, input_source: str) -> None:
        text = input_source or "Auto"
        self.input_combo.blockSignals(True)
        index = self.input_combo.findText(text)
        if index < 0:
            self.input_combo.addItem(text)
            index = self.input_combo.findText(text)
        self.input_combo.setCurrentIndex(index if index >= 0 else 0)
        self.input_combo.blockSignals(False)

    def set_playback_summary(self, summary: str, tooltip: str = "") -> None:
        self.playback_summary.setText(summary)
        self.playback_summary.setToolTip(tooltip)

    def set_send_levels(self, send_a: float, send_b: float) -> None:
        self.send_a_knob["knob"].blockSignals(True)
        self.send_b_knob["knob"].blockSignals(True)
        try:
            self.send_a_knob["knob"].setValue(int(max(0.0, min(1.0, float(send_a))) * 100.0))
            self.send_b_knob["knob"].setValue(int(max(0.0, min(1.0, float(send_b))) * 100.0))
        finally:
            self.send_a_knob["knob"].blockSignals(False)
            self.send_b_knob["knob"].blockSignals(False)

    def set_automation_parameter(self, parameter: str) -> None:
        target_parameter = str(parameter or "volume_db")
        self.automation_param_combo.blockSignals(True)
        index = self.automation_param_combo.findData(target_parameter)
        self.automation_param_combo.setCurrentIndex(index if index >= 0 else 0)
        self.automation_param_combo.blockSignals(False)
