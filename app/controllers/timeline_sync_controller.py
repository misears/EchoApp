"""Timeline Synchronization Controller (Group 2.1)

Centralizes timeline state (playhead, zoom, scroll) so all timeline-linked widgets
subscribe to a single source of truth instead of updating independently.
"""

from PySide6.QtCore import QObject, Signal, Property
from typing import Optional


class TimelineSyncController(QObject):
    """
    Manages single source of truth for timeline state across the main mixer view.
    
    All timeline-dependent widgets (waveform, ruler, transport) subscribe to this
    controller's signals rather than updating independently.
    """
    
    # Signals
    playhead_changed = Signal(int)  # milliseconds
    zoom_factor_changed = Signal(float)
    scroll_position_changed = Signal(int)  # pixels
    is_playing_changed = Signal(bool)
    bpm_changed = Signal(float)
    time_signature_changed = Signal(str)
    master_volume_changed = Signal(float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Timeline state
        self._playhead_ms = 0
        self._zoom_factor = 1.0
        self._scroll_position_px = 0
        self._is_playing = False
        self._bpm = 120.0
        self._time_signature = "4/4"
        self._master_volume_db = 0.0
        
        # Zoom limits
        self._zoom_min = 0.0078125  # 1/128
        self._zoom_max = 128.0
        
        self._sample_rate = 44100
        
    def set_playhead(self, playhead_ms: int) -> None:
        """Update playhead position (in milliseconds)."""
        playhead_ms = max(0, playhead_ms)
        if playhead_ms != self._playhead_ms:
            self._playhead_ms = playhead_ms
            self.playhead_changed.emit(playhead_ms)
    
    def get_playhead(self) -> int:
        return self._playhead_ms
    
    playhead = Property(int, get_playhead, set_playhead, notify=playhead_changed)
    
    def set_zoom_factor(self, factor: float) -> None:
        factor = max(self._zoom_min, min(self._zoom_max, factor))
        if factor != self._zoom_factor:
            self._zoom_factor = factor
            self.zoom_factor_changed.emit(factor)
    
    def get_zoom_factor(self) -> float:
        return self._zoom_factor
    
    zoom_factor = Property(float, get_zoom_factor, set_zoom_factor, notify=zoom_factor_changed)
    
    def zoom_in(self, steps: int = 1) -> None:
        factor = self._zoom_factor * (1.25 ** steps)
        self.set_zoom_factor(factor)
    
    def zoom_out(self, steps: int = 1) -> None:
        factor = self._zoom_factor / (1.25 ** steps)
        self.set_zoom_factor(factor)
    
    def set_scroll_position(self, scroll_px: int) -> None:
        scroll_px = max(0, scroll_px)
        if scroll_px != self._scroll_position_px:
            self._scroll_position_px = scroll_px
            self.scroll_position_changed.emit(scroll_px)
    
    def get_scroll_position(self) -> int:
        return self._scroll_position_px
    
    scroll_position = Property(int, get_scroll_position, set_scroll_position, notify=scroll_position_changed)
    
    def set_is_playing(self, playing: bool) -> None:
        if playing != self._is_playing:
            self._is_playing = playing
            self.is_playing_changed.emit(playing)
    
    def get_is_playing(self) -> bool:
        return self._is_playing
    
    is_playing = Property(bool, get_is_playing, set_is_playing, notify=is_playing_changed)
    
    def toggle_playback(self) -> None:
        self.set_is_playing(not self._is_playing)
    
    def set_bpm(self, bpm: float) -> None:
        bpm = max(30.0, min(300.0, bpm))
        if bpm != self._bpm:
            self._bpm = bpm
            self.bpm_changed.emit(bpm)
    
    def get_bpm(self) -> float:
        return self._bpm
    
    bpm = Property(float, get_bpm, set_bpm, notify=bpm_changed)
    
    def set_time_signature(self, sig: str) -> None:
        if sig != self._time_signature:
            self._time_signature = sig
            self.time_signature_changed.emit(sig)
    
    def get_time_signature(self) -> str:
        return self._time_signature
    
    time_signature = Property(str, get_time_signature, set_time_signature, notify=time_signature_changed)
    
    def set_master_volume(self, volume_db: float) -> None:
        volume_db = max(-80.0, min(12.0, volume_db))
        if volume_db != self._master_volume_db:
            self._master_volume_db = volume_db
            self.master_volume_changed.emit(volume_db)
    
    def get_master_volume(self) -> float:
        return self._master_volume_db
    
    master_volume = Property(float, get_master_volume, set_master_volume, notify=master_volume_changed)
    
    def set_sample_rate(self, sample_rate: int) -> None:
        self._sample_rate = max(8000, sample_rate)
    
    def reset(self) -> None:
        """Reset all state to defaults."""
        self.set_playhead(0)
        self.set_zoom_factor(1.0)
        self.set_scroll_position(0)
        self.set_is_playing(False)
        self.set_bpm(120.0)
        self.set_time_signature("4/4")
        self.set_master_volume(0.0)
