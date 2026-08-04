"""Audio-Thread-to-UI Communication Bridge (Group 2.3)

Non-blocking thread-safe bridge for real-time audio data to flow from the
audio playback thread to the PySide UI thread without stalling playback.

Uses Python's thread-safe queue.Queue for lock-free communication.
"""

import threading
import queue
from typing import Optional, Callable, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AudioThreadMessageType(Enum):
    """Message types that can flow from audio thread to UI."""
    PLAYHEAD_UPDATE = "playhead_update"  # Playback position in ms
    PEAK_METER_UPDATE = "peak_meter"  # Left/right peak levels
    VU_METER_UPDATE = "vu_meter"  # VU meter readings
    WAVEFORM_BUFFER = "waveform_buffer"  # Waveform data for rendering
    PLAYBACK_STATE_CHANGE = "state_change"  # Play/pause/stop
    ERROR = "error"  # Audio thread error


class AudioThreadMessage:
    """Message envelope for audio→UI communication."""
    
    def __init__(self, msg_type: AudioThreadMessageType, payload: Any = None):
        self.msg_type = msg_type
        self.payload = payload
        self.timestamp_ms = 0  # Set by audio thread


class AudioThreadBridge:
    """
    Thread-safe, non-blocking bridge for audio→UI communication.
    
    Audio playback thread (real-time):
    - Pushes messages (playhead, meters, waveform) to queue
    - Never blocks (uses queue.Queue.put_nowait)
    - Drops messages if queue is full (bounded)
    
    UI thread (PySide event loop):
    - Polls queue periodically (e.g., every 16ms for 60fps)
    - Delivers messages to subscribed handlers via callbacks
    - Handles dropped messages gracefully
    """
    
    # Queue settings
    MAX_QUEUE_SIZE = 256  # Maximum messages before dropping oldest
    
    def __init__(self):
        """Initialize the bridge."""
        # Thread-safe queue: audio thread → UI thread
        self._message_queue: queue.Queue = queue.Queue(maxsize=self.MAX_QUEUE_SIZE)
        
        # Registered callbacks: MessageType → list of handlers
        self._handlers: dict[AudioThreadMessageType, list[Callable]] = {
            msg_type: [] for msg_type in AudioThreadMessageType
        }
        
        # Statistics
        self._messages_dropped = 0
        self._messages_processed = 0
        self._last_error_msg = ""
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Audio Thread Methods (Real-Time, Non-Blocking)
    # ═══════════════════════════════════════════════════════════════════════════
    
    def send_playhead_update(self, playhead_ms: int) -> bool:
        """
        Send playhead position update from audio thread.
        
        Args:
            playhead_ms: Current playback position in milliseconds
        
        Returns:
            True if queued successfully; False if queue full (message dropped)
        """
        msg = AudioThreadMessage(AudioThreadMessageType.PLAYHEAD_UPDATE, playhead_ms)
        return self._enqueue_message(msg)
    
    def send_peak_meter_update(self, left_peak: float, right_peak: float) -> bool:
        """
        Send peak meter readings (0.0–1.0).
        
        Args:
            left_peak: Left channel peak
            right_peak: Right channel peak
        
        Returns:
            True if queued; False if dropped
        """
        msg = AudioThreadMessage(
            AudioThreadMessageType.PEAK_METER_UPDATE,
            {"left": left_peak, "right": right_peak}
        )
        return self._enqueue_message(msg)
    
    def send_vu_meter_update(self, left_db: float, right_db: float) -> bool:
        """
        Send VU meter readings in dB.
        
        Args:
            left_db: Left channel in dB
            right_db: Right channel in dB
        
        Returns:
            True if queued; False if dropped
        """
        msg = AudioThreadMessage(
            AudioThreadMessageType.VU_METER_UPDATE,
            {"left_db": left_db, "right_db": right_db}
        )
        return self._enqueue_message(msg)
    
    def send_playback_state(self, is_playing: bool) -> bool:
        """
        Send playback state change.
        
        Args:
            is_playing: True if playing, False if stopped/paused
        
        Returns:
            True if queued; False if dropped
        """
        msg = AudioThreadMessage(AudioThreadMessageType.PLAYBACK_STATE_CHANGE, is_playing)
        return self._enqueue_message(msg)
    
    def send_error(self, error_msg: str) -> bool:
        """
        Send error message from audio thread.
        
        Args:
            error_msg: Error description
        
        Returns:
            True if queued; False if dropped
        """
        msg = AudioThreadMessage(AudioThreadMessageType.ERROR, error_msg)
        self._last_error_msg = error_msg
        return self._enqueue_message(msg)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UI Thread Methods
    # ═══════════════════════════════════════════════════════════════════════════
    
    def subscribe(self, msg_type: AudioThreadMessageType, handler: Callable) -> None:
        """
        Register a callback for a message type.
        
        Args:
            msg_type: AudioThreadMessageType to listen for
            handler: Callable(payload) that will be invoked
        
        Example:
            bridge.subscribe(AudioThreadMessageType.PLAYHEAD_UPDATE, on_playhead)
            # Later, audio thread calls: bridge.send_playhead_update(5000)
            # UI callback invoked: on_playhead(5000)
        """
        if msg_type in self._handlers:
            self._handlers[msg_type].append(handler)
    
    def unsubscribe(self, msg_type: AudioThreadMessageType, handler: Callable) -> None:
        """Unregister a callback."""
        if msg_type in self._handlers and handler in self._handlers[msg_type]:
            self._handlers[msg_type].remove(handler)
    
    def poll(self) -> int:
        """
        Poll and process all queued messages (call from UI thread).
        
        Returns:
            Number of messages processed
        """
        count = 0
        try:
            while True:
                try:
                    msg = self._message_queue.get_nowait()
                    self._dispatch_message(msg)
                    self._messages_processed += 1
                    count += 1
                except queue.Empty:
                    break
        except Exception as e:
            logger.error(f"Error polling audio bridge: {e}")
        
        return count
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Statistics & Diagnostics
    # ═══════════════════════════════════════════════════════════════════════════
    
    def get_stats(self) -> dict:
        """Get bridge statistics."""
        return {
            "messages_processed": self._messages_processed,
            "messages_dropped": self._messages_dropped,
            "queue_size": self._message_queue.qsize(),
            "last_error": self._last_error_msg,
        }
    
    def reset_stats(self) -> None:
        """Reset counters."""
        self._messages_dropped = 0
        self._messages_processed = 0
        self._last_error_msg = ""
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Private Methods
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _enqueue_message(self, msg: AudioThreadMessage) -> bool:
        """
        Enqueue a message without blocking (audio thread).
        
        If queue is full, drops the oldest message silently to prevent
        real-time audio stalls.
        """
        try:
            self._message_queue.put_nowait(msg)
            return True
        except queue.Full:
            # Queue is full; drop oldest message to make room
            try:
                self._message_queue.get_nowait()  # Drop oldest
                self._message_queue.put_nowait(msg)
                self._messages_dropped += 1
                return True
            except queue.Empty:
                return False
    
    def _dispatch_message(self, msg: AudioThreadMessage) -> None:
        """Deliver message to all registered handlers."""
        handlers = self._handlers.get(msg.msg_type, [])
        for handler in handlers:
            try:
                handler(msg.payload)
            except Exception as e:
                logger.error(f"Error in audio bridge handler: {e}")


# Global bridge instance (singleton)
_global_bridge: Optional[AudioThreadBridge] = None


def get_audio_bridge() -> AudioThreadBridge:
    """Get or create the global audio bridge."""
    global _global_bridge
    if _global_bridge is None:
        _global_bridge = AudioThreadBridge()
    return _global_bridge


def reset_audio_bridge() -> None:
    """Reset global bridge (for testing)."""
    global _global_bridge
    _global_bridge = None
