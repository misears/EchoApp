from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDial, QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout

from .level_meter import VerticalLevelMeter

_EQ_BANDS = ["40", "200", "500", "1k", "3k", "8k", "16k"]


class TrackMixerRow(QFrame):
    """Vertical channel strip: EQ sliders, gain fader, pan, and Punch/Mute/Solo buttons."""

    def __init__(self, track_index: int, track_name: str, *, on_volume_change=None, on_mute_toggle=None, on_solo_toggle=None, parent=None):
        super().__init__(parent)
        self.track_index = track_index
        self._on_volume_change = on_volume_change
        self._on_mute_toggle = on_mute_toggle
        self._on_solo_toggle = on_solo_toggle

        self.setObjectName("TrackMixerRow")
        self.setFrameShape(QFrame.StyledPanel)
        self.setFixedWidth(130)
        self.setMinimumHeight(520)
        self.setStyleSheet("QFrame#TrackMixerRow { background:#0d1b2a; border:1px solid #1a4080; border-radius:6px; }")

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 8)
        root.setSpacing(4)

        header_row = QHBoxLayout()
        header_row.setSpacing(4)
        badge = QLabel(str(track_index + 1))
        badge.setFixedSize(20, 20)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet("background:#0f3460; border-radius:10px; color:#e94560; font-weight:bold; font-size:9px;")
        header_row.addWidget(badge)
        self.name_label = QLabel(track_name)
        self.name_label.setStyleSheet("font-size:9px; font-weight:bold;")
        self.name_label.setWordWrap(True)
        header_row.addWidget(self.name_label, stretch=1)
        root.addLayout(header_row)

        meter_lbl = QLabel("L/R")
        meter_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        meter_lbl.setStyleSheet("font-size:8px; color:#aab4be;")
        root.addWidget(meter_lbl)

        meter_row = QHBoxLayout()
        meter_row.setSpacing(3)
        meter_row.setContentsMargins(4, 0, 4, 0)
        self.meter_l = VerticalLevelMeter()
        self.meter_r = VerticalLevelMeter()
        self.peak_label = QLabel("-∞")
        self.peak_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.peak_label.setStyleSheet("font-size:8px; color:#aab4be;")
        meter_row.addStretch()
        meter_row.addWidget(self.meter_l)
        meter_row.addWidget(self.meter_r)
        meter_row.addStretch()
        root.addLayout(meter_row)
        root.addWidget(self.peak_label)

        eq_lbl = QLabel("EQ")
        eq_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        eq_lbl.setStyleSheet("font-size:8px; color:#aab4be;")
        root.addWidget(eq_lbl)

        eq_row = QHBoxLayout()
        eq_row.setSpacing(2)
        eq_row.setContentsMargins(2, 0, 2, 0)
        self.eq_sliders: list = []
        for band in _EQ_BANDS:
            col = QVBoxLayout()
            col.setSpacing(1)
            col.setContentsMargins(0, 0, 0, 0)
            sl = QSlider(Qt.Orientation.Vertical)
            sl.setRange(-12, 12)
            sl.setValue(0)
            sl.setFixedWidth(12)
            sl.setFixedHeight(56)
            sl.setToolTip(f"EQ {band}Hz: ±12 dB")
            col.addWidget(sl, alignment=Qt.AlignmentFlag.AlignHCenter)
            lbl = QLabel(band)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-size:7px; color:#aab4be;")
            col.addWidget(lbl)
            eq_row.addLayout(col)
            self.eq_sliders.append(sl)
        root.addLayout(eq_row)

        root.addSpacing(2)

        gain_row = QHBoxLayout()
        gain_row.setSpacing(4)

        fader_col = QVBoxLayout()
        fader_col.setSpacing(2)
        self.db_label = QLabel("0 dB")
        self.db_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.db_label.setStyleSheet("font-size:9px;")
        fader_col.addWidget(self.db_label)

        self.vol_slider = QSlider(Qt.Orientation.Vertical)
        self.vol_slider.setRange(-60, 6)
        self.vol_slider.setValue(0)
        self.vol_slider.setMinimumHeight(90)
        self.vol_slider.setFixedWidth(20)
        self.vol_slider.setToolTip("Track gain: -60 dB to +6 dB")
        self.vol_slider.valueChanged.connect(self._volume_changed)
        fader_col.addWidget(self.vol_slider, alignment=Qt.AlignmentFlag.AlignHCenter)
        fader_lbl = QLabel("GAIN")
        fader_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fader_lbl.setStyleSheet("font-size:8px; color:#aab4be;")
        fader_col.addWidget(fader_lbl)
        gain_row.addStretch()
        gain_row.addLayout(fader_col)
        gain_row.addStretch()
        root.addLayout(gain_row)

        root.addSpacing(2)

        pan_col = QVBoxLayout()
        pan_col.setSpacing(1)
        self.pan_knob = QDial()
        self.pan_knob.setRange(-100, 100)
        self.pan_knob.setValue(0)
        self.pan_knob.setFixedSize(36, 36)
        self.pan_knob.setNotchesVisible(True)
        self.pan_knob.setToolTip("Pan: left (L) to right (R)")
        pan_col.addWidget(self.pan_knob, alignment=Qt.AlignmentFlag.AlignCenter)
        pan_lbl = QLabel("PAN")
        pan_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pan_lbl.setStyleSheet("font-size:8px; color:#aab4be;")
        pan_col.addWidget(pan_lbl)
        root.addLayout(pan_col)

        root.addSpacing(2)

        pms_row = QHBoxLayout()
        pms_row.setSpacing(3)

        self.punch_btn = QPushButton("P")
        self.punch_btn.setCheckable(True)
        self.punch_btn.setFixedSize(28, 22)
        self.punch_btn.setProperty("channelBtn", "punch")
        self.punch_btn.setToolTip("Punch-in arm: enable punch recording on this channel")
        pms_row.addWidget(self.punch_btn)

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

        root.addLayout(pms_row)
        root.addStretch()

    def _volume_changed(self, value: int):
        self.db_label.setText(f"{value:+d} dB" if value != 0 else "0 dB")
        if self._on_volume_change:
            self._on_volume_change(self.track_index, float(value))

    def _mute_clicked(self, checked: bool):
        if self._on_mute_toggle:
            self._on_mute_toggle(self.track_index, checked)

    def _solo_clicked(self, checked: bool):
        if self._on_solo_toggle:
            self._on_solo_toggle(self.track_index, checked)

    def set_volume_db(self, db: float):
        self.vol_slider.blockSignals(True)
        self.vol_slider.setValue(int(db))
        self.db_label.setText(f"{int(db):+d} dB" if int(db) != 0 else "0 dB")
        self.vol_slider.blockSignals(False)

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
