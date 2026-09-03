"""Timeline widget for Echo Pro.

Custom QWidget that renders the multi-track arrangement view: clip blocks,
waveform thumbnails, fade handles, automation lanes, comp regions, and the
playhead.  All interaction (clip drag, fade drag, automation editing, context
menus, zoom) is handled here and reported back via callback attributes.
"""

from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf
from PySide6.QtWidgets import QWidget, QMenu, QToolTip
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtCore import Qt, QRect, QPoint, QSize

from project_model import Project

TRACK_HEIGHT = 60
TRACK_GAP = 10
CLIP_COLOR = QColor(100, 180, 255)
CLIP_BORDER = QColor(30, 60, 120)

PIXELS_PER_SECOND = 50  # how many pixels represent one second
MARKER_HIT_TOLERANCE_PX = 8
MARKER_HEADER_HEIGHT = 18
EDIT_STRIP_HEIGHT = 84

class TimelineWidget(QWidget):
    
    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.project = project
        self.selected_clip_id = None
        self.selected_track_index = None
        self.hide_inactive_take_clips = False
        self.on_project_changed: Optional[Callable[[], None]] = None
        self.on_comp_range_selected: Optional[Callable[[int, int, int], None]] = None
        self.on_add_clip_at: Optional[Callable[[int, int], None]] = None
        self.on_clip_action: Optional[Callable[[str, int], None]] = None
        self.on_track_selected: Optional[Callable[[int], None]] = None
        self.on_zoom_request: Optional[Callable[[int, int], None]] = None
        self.on_time_range_changed: Optional[Callable[[Optional[int], Optional[int], Optional[int]], None]] = None
        self.on_automation_points_changed: Optional[Callable[[int, str, List[dict]], None]] = None
        self.on_clip_fade_changed: Optional[Callable[[int, int, int, bool], None]] = None
        self.on_track_double_click: Optional[Callable[[int], None]] = None
        self.on_split_clip_requested: Optional[Callable[[int, int], None]] = None
        self.on_marker_action: Optional[Callable[[str, int, Optional[int]], None]] = None
        self.on_playhead_scrubbed: Optional[Callable[[int], None]] = None
        self.on_gain_envelope_changed: Optional[Callable[[int, int, int, float, float, bool], None]] = None
        self._clip_rects = []
        self._fade_handle_rects: List[Tuple[int, str, QRect]] = []
        self._dragging_clip_id = None
        self._drag_start_point = None
        self._drag_origin_start_ms = None
        self._dragging_fade_handle: Optional[Tuple[int, str]] = None
        self._dragging_automation_node: Optional[Tuple[int, str, int]] = None
        self._comp_regions_by_track: Dict[int, List[dict]] = {}
        self._comp_color_mode = "alternating"
        self._comp_selecting = False
        self._comp_select_start_ms: Optional[int] = None
        self._comp_select_end_ms: Optional[int] = None
        self._comp_select_track_index: Optional[int] = None
        self._selected_time_range: Optional[Tuple[int, int, int]] = None
        self._automation_points_by_track_param: Dict[Tuple[int, str], List[dict]] = {}
        self._active_automation_parameter_by_track: Dict[int, str] = {}
        self._waveform_cache: Dict[str, tuple[int, int, np.ndarray]] = {}
        self._hovered_clip_id: Optional[int] = None
        self._zoom_factor = 1.0
        self.playhead_ms = 0
        self._interaction_mode = "multitrack"
        self._tool_mode = "pointer"
        self._markers: List[dict] = []
        self._scrubbing_playhead = False
        self._dragging_gain_handle: Optional[dict] = None
        self.setMinimumHeight(300)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self._sync_view_size()

    def set_project(self, project: Project):
        self.project = project
        self._sync_view_size()
        self.update()

    def set_selected_track(self, track_index):
        self.selected_track_index = track_index
        self._sync_view_size()
        self.update()

    def set_playhead_ms(self, ms: int) -> None:
        self.playhead_ms = max(0, int(ms))
        self.update()

    def set_zoom_factor(self, factor: float) -> None:
        next_zoom = max(0.0625, min(64.0, float(factor)))
        if abs(next_zoom - float(self._zoom_factor)) <= 1e-9:
            return
        self._zoom_factor = next_zoom
        self._sync_view_size()
        self.update()

    def get_zoom_factor(self) -> float:
        return float(self._zoom_factor)

    def get_playhead_ms(self) -> int:
        return max(0, int(self.playhead_ms))

    def set_interaction_mode(self, mode: str) -> None:
        normalized = str(mode or "multitrack").strip().lower()
        self._interaction_mode = "edit" if normalized == "edit" else "multitrack"
        self._sync_view_size()
        self.update()

    def interaction_mode(self) -> str:
        return str(self._interaction_mode)

    def set_tool_mode(self, mode: str) -> None:
        normalized = str(mode or "pointer").strip().lower()
        if normalized not in {"pointer", "razor", "envelope"}:
            normalized = "pointer"
        self._tool_mode = normalized
        self.update()

    def tool_mode(self) -> str:
        return str(self._tool_mode)

    def set_markers(self, markers: List[dict]) -> None:
        normalized: List[dict] = []
        for marker in markers:
            if not isinstance(marker, dict):
                continue
            try:
                marker_id = int(marker.get("id", 0))
                time_ms = max(0, int(marker.get("time_ms", 0)))
            except (TypeError, ValueError):
                continue
            name = str(marker.get("name", f"Marker {marker_id}"))
            normalized.append({"id": marker_id, "time_ms": time_ms, "name": name})
        normalized.sort(key=lambda item: int(item["time_ms"]))
        self._markers = normalized
        self.update()

    def markers(self) -> List[dict]:
        return [dict(marker) for marker in self._markers]

    def _find_marker_near_x(self, x: int) -> Optional[dict]:
        nearest: Optional[dict] = None
        nearest_delta = MARKER_HIT_TOLERANCE_PX + 1
        for marker in self._markers:
            marker_x = self.time_to_x(int(marker.get("time_ms", 0)))
            delta = abs(int(x) - int(marker_x))
            if delta <= MARKER_HIT_TOLERANCE_PX and delta < nearest_delta:
                nearest = marker
                nearest_delta = delta
        return dict(nearest) if nearest is not None else None

    def _emit_marker_action(self, action: str, time_ms: int, marker_id: Optional[int]) -> None:
        if self.on_marker_action is None:
            return
        self.on_marker_action(str(action), int(time_ms), None if marker_id is None else int(marker_id))

    def _draw_markers(self, painter: QPainter) -> None:
        if not self._markers:
            return
        label_bg = QColor(26, 34, 49, 220)
        label_pen = QColor(255, 220, 120)
        line_pen = QPen(QColor(255, 190, 80, 180), 1)
        triangle_brush = QColor(255, 190, 80)
        for marker in self._markers:
            marker_ms = int(marker.get("time_ms", 0))
            marker_name = str(marker.get("name", "Marker"))
            marker_x = self.time_to_x(marker_ms)

            painter.setPen(line_pen)
            painter.drawLine(marker_x, 0, marker_x, self.height())

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(triangle_brush)
            painter.drawRect(QRect(marker_x - 4, 1, 8, 8))

            text_rect = QRect(marker_x + 6, 1, 120, MARKER_HEADER_HEIGHT - 2)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(label_bg)
            painter.drawRect(text_rect)
            painter.setPen(label_pen)
            painter.drawText(text_rect.adjusted(4, 0, -4, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, marker_name)

    def _edit_strip_rect(self) -> Optional[QRect]:
        if self._interaction_mode != "edit":
            return None
        top = max(MARKER_HEADER_HEIGHT + 24, self.height() - EDIT_STRIP_HEIGHT)
        return QRect(0, top, self.width(), max(40, EDIT_STRIP_HEIGHT))

    def _selected_edit_clip(self):
        clip = self._find_clip_by_id(int(self.selected_clip_id)) if self.selected_clip_id is not None else None
        if clip is None:
            return None
        if self.selected_track_index is not None and int(clip.track_index) != int(self.selected_track_index):
            return None
        return clip

    def _db_to_strip_y(self, strip: QRect, gain_db: float) -> int:
        clamped = max(-18.0, min(12.0, float(gain_db)))
        normalized = (clamped + 18.0) / 30.0
        top = strip.top() + 20
        bottom = strip.bottom() - 8
        span = max(1, bottom - top)
        return int(round(bottom - (normalized * span)))

    def _strip_y_to_db(self, strip: QRect, y: int) -> float:
        top = strip.top() + 20
        bottom = strip.bottom() - 8
        clamped_y = max(top, min(bottom, int(y)))
        span = max(1, bottom - top)
        normalized = float(bottom - clamped_y) / float(span)
        return max(-18.0, min(12.0, (normalized * 30.0) - 18.0))

    def _clip_gain_envelopes(self, clip) -> List[dict]:
        metadata = getattr(clip, "metadata", {}) or {}
        raw = metadata.get("gain_envelopes", [])
        if not isinstance(raw, list):
            return []
        cleaned: List[dict] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                start_ms = int(item.get("start_ms", 0))
                end_ms = int(item.get("end_ms", 0))
                start_db = float(item.get("start_gain_db", 0.0))
                end_db = float(item.get("end_gain_db", 0.0))
            except (TypeError, ValueError):
                continue
            if end_ms <= start_ms:
                continue
            cleaned.append(
                {
                    "start_ms": int(start_ms),
                    "end_ms": int(end_ms),
                    "start_gain_db": float(max(-18.0, min(12.0, start_db))),
                    "end_gain_db": float(max(-18.0, min(12.0, end_db))),
                }
            )
        return cleaned

    def _set_clip_gain_envelopes(self, clip, envelopes: List[dict]) -> None:
        metadata = dict(getattr(clip, "metadata", {}) or {})
        metadata["gain_envelopes"] = list(envelopes)
        clip.metadata = metadata

    def _active_gain_envelope_context(self) -> Optional[dict]:
        clip = self._selected_edit_clip()
        if clip is None:
            return None
        selected_range = self.get_selected_time_range_ms()
        clip_start = int(getattr(clip, "start_ms", 0))
        clip_end = clip_start + int(getattr(clip, "length_ms", 0))
        if selected_range is None:
            range_start, range_end = clip_start, clip_end
        else:
            range_start, range_end = int(selected_range[0]), int(selected_range[1])
            range_start = max(range_start, clip_start)
            range_end = min(range_end, clip_end)
            if range_end <= range_start:
                range_start, range_end = clip_start, clip_end

        envelopes = self._clip_gain_envelopes(clip)
        envelope_index = -1
        start_db = 0.0
        end_db = 0.0
        for idx, envelope in enumerate(envelopes):
            if int(envelope["start_ms"]) == int(range_start) and int(envelope["end_ms"]) == int(range_end):
                envelope_index = idx
                start_db = float(envelope.get("start_gain_db", 0.0))
                end_db = float(envelope.get("end_gain_db", 0.0))
                break

        return {
            "clip": clip,
            "clip_id": int(getattr(clip, "id", -1)),
            "track_index": int(getattr(clip, "track_index", -1)),
            "start_ms": int(range_start),
            "end_ms": int(range_end),
            "start_db": float(start_db),
            "end_db": float(end_db),
            "envelope_index": int(envelope_index),
            "envelopes": envelopes,
        }

    def _apply_active_gain_envelope(self, context: dict, start_db: float, end_db: float) -> None:
        clip = context.get("clip")
        if clip is None:
            return
        envelopes = list(context.get("envelopes", []))
        payload = {
            "start_ms": int(context["start_ms"]),
            "end_ms": int(context["end_ms"]),
            "start_gain_db": float(max(-18.0, min(12.0, float(start_db)))),
            "end_gain_db": float(max(-18.0, min(12.0, float(end_db)))),
        }
        envelope_index = int(context.get("envelope_index", -1))
        if envelope_index >= 0 and envelope_index < len(envelopes):
            envelopes[envelope_index] = payload
        else:
            envelopes.append(payload)
            envelopes.sort(key=lambda item: (int(item["start_ms"]), int(item["end_ms"])))
            envelope_index = next(
                (
                    idx
                    for idx, envelope in enumerate(envelopes)
                    if int(envelope["start_ms"]) == int(payload["start_ms"])
                    and int(envelope["end_ms"]) == int(payload["end_ms"])
                ),
                -1,
            )
        context["envelopes"] = envelopes
        context["envelope_index"] = int(envelope_index)
        context["start_db"] = float(payload["start_gain_db"])
        context["end_db"] = float(payload["end_gain_db"])
        self._set_clip_gain_envelopes(clip, envelopes)

    def _draw_edit_strip(self, painter: QPainter) -> None:
        strip = self._edit_strip_rect()
        if strip is None:
            return

        painter.setPen(QPen(QColor(48, 64, 84), 1))
        painter.setBrush(QColor(16, 24, 34, 230))
        painter.drawRect(strip)

        clip = self._selected_edit_clip()
        painter.setPen(QColor(158, 178, 198))
        if clip is None:
            painter.drawText(strip.adjusted(10, 8, -10, -8), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, "Edit Strip: select a clip in Edit mode to view spectral detail and gain envelope handles.")
            return

        peaks = self._read_waveform_peaks(str(getattr(clip, "file_path", "")), target_points=max(64, strip.width() // 3))
        graph_left = strip.left() + 10
        graph_right = strip.right() - 10
        graph_top = strip.top() + 22
        graph_bottom = strip.bottom() - 10
        center_y = int((graph_top + graph_bottom) / 2)

        # Draw quick dB guides so envelope ramps are easier to judge by eye.
        for guide_db in (12.0, 0.0, -12.0):
            guide_y = self._db_to_strip_y(strip, guide_db)
            pen = QPen(QColor(84, 108, 132, 150), 1)
            if abs(guide_db) < 0.01:
                pen = QPen(QColor(110, 146, 180, 190), 1)
            painter.setPen(pen)
            painter.drawLine(graph_left, guide_y, graph_right, guide_y)
            painter.setPen(QColor(128, 150, 174))
            painter.drawText(graph_left + 2, guide_y - 2, f"{guide_db:+.0f} dB")

        painter.setPen(QPen(QColor(44, 96, 140), 1))
        painter.drawLine(graph_left, center_y, graph_right, center_y)

        if peaks is not None and peaks.size > 0:
            columns = max(8, graph_right - graph_left)
            positions = np.linspace(0, peaks.size - 1, columns, dtype=np.int32)
            sampled = peaks[positions]
            painter.setPen(QPen(QColor(80, 170, 255, 180), 1))
            for idx, peak in enumerate(sampled):
                amplitude = max(1, int(round(float(peak) * max(1, (graph_bottom - graph_top) // 2))))
                x = graph_left + idx
                painter.drawLine(x, center_y - amplitude, x, center_y + amplitude)

        context = self._active_gain_envelope_context()
        if context is None:
            painter.setPen(QColor(170, 170, 170))
            painter.drawText(strip.adjusted(10, 6, -10, -8), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, f"Edit Strip: {Path(str(getattr(clip, 'file_path', ''))).name}")
            return

        envelopes = self._clip_gain_envelopes(clip)
        for envelope in envelopes:
            env_start_x = self.time_to_x(int(envelope.get("start_ms", 0)))
            env_end_x = self.time_to_x(int(envelope.get("end_ms", 0)))
            if env_end_x <= env_start_x:
                continue
            if env_end_x < strip.left() or env_start_x > strip.right():
                continue
            env_start_x = max(strip.left() + 8, env_start_x)
            env_end_x = min(strip.right() - 8, env_end_x)
            env_start_y = self._db_to_strip_y(strip, float(envelope.get("start_gain_db", 0.0)))
            env_end_y = self._db_to_strip_y(strip, float(envelope.get("end_gain_db", 0.0)))
            painter.setPen(QPen(QColor(118, 152, 186, 150), 1))
            painter.drawLine(env_start_x, env_start_y, env_end_x, env_end_y)

        start_x = self.time_to_x(int(context["start_ms"]))
        end_x = self.time_to_x(int(context["end_ms"]))
        if end_x <= start_x:
            return
        if end_x < strip.left() or start_x > strip.right():
            return

        start_x = max(strip.left() + 8, start_x)
        end_x = min(strip.right() - 8, end_x)
        start_db = float(context["start_db"])
        end_db = float(context["end_db"])
        start_y = self._db_to_strip_y(strip, start_db)
        end_y = self._db_to_strip_y(strip, end_db)

        painter.setPen(QPen(QColor(255, 210, 110, 90), 1, Qt.PenStyle.DashLine))
        painter.drawLine(start_x, graph_bottom, start_x, graph_top)
        painter.drawLine(end_x, graph_bottom, end_x, graph_top)

        painter.setPen(QPen(QColor(255, 210, 110), 2))
        painter.drawLine(start_x, start_y, end_x, end_y)
        painter.setBrush(QColor(255, 180, 90, 220))
        painter.setPen(QPen(QColor(255, 235, 170), 1))
        painter.drawEllipse(QPoint(start_x, start_y), 5, 5)
        painter.drawEllipse(QPoint(end_x, end_y), 5, 5)

        painter.setPen(QColor(198, 212, 227))
        painter.drawText(
            strip.adjusted(10, 4, -10, -6),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            f"Edit Strip: {Path(str(getattr(clip, 'file_path', ''))).name} | Region Gain {start_db:+.1f} dB → {end_db:+.1f} dB",
        )

    def get_selected_clip_range_ms(self) -> Optional[Tuple[int, int]]:
        if self.selected_clip_id is None:
            return None
        clip = self._find_clip_by_id(int(self.selected_clip_id))
        if clip is None:
            return None
        start_ms = max(0, int(clip.start_ms))
        end_ms = max(start_ms, int(clip.start_ms) + int(clip.length_ms))
        return start_ms, end_ms

    def get_selected_time_range_ms(self) -> Optional[Tuple[int, int]]:
        if self._selected_time_range is None:
            return None
        _track_index, start_ms, end_ms = self._selected_time_range
        return int(start_ms), int(end_ms)

    def clear_selected_time_range(self) -> None:
        if self._selected_time_range is None:
            return
        self._selected_time_range = None
        self._emit_time_range_changed(None, None, None)
        self.update()

    def _emit_time_range_changed(
        self,
        track_index: Optional[int],
        start_ms: Optional[int],
        end_ms: Optional[int],
    ) -> None:
        if self.on_time_range_changed is None:
            return
        self.on_time_range_changed(track_index, start_ms, end_ms)

    def _set_selected_time_range(self, track_index: int, start_ms: int, end_ms: int) -> None:
        safe_start = max(0, int(min(start_ms, end_ms)))
        safe_end = max(safe_start + 1, int(max(start_ms, end_ms)))
        self._selected_time_range = (int(track_index), safe_start, safe_end)
        self._emit_time_range_changed(int(track_index), safe_start, safe_end)

    def _edit_selected_time_range_edge(self, track_index: int, clicked_ms: int, *, move_start: bool) -> bool:
        if self._selected_time_range is None:
            return False
        selected_track_index, selected_start_ms, selected_end_ms = self._selected_time_range
        if int(selected_track_index) != int(track_index):
            return False
        click_ms = max(0, int(clicked_ms))
        if move_start:
            next_start = min(click_ms, int(selected_end_ms) - 1)
            self._set_selected_time_range(int(track_index), next_start, int(selected_end_ms))
            return True
        next_end = max(click_ms, int(selected_start_ms) + 1)
        self._set_selected_time_range(int(track_index), int(selected_start_ms), next_end)
        return True

    def _content_width(self) -> int:
        max_end_ms = max((int(clip.start_ms) + int(clip.length_ms) for clip in self.project.clips), default=30000)
        return max(1200, self.time_to_x(max_end_ms) + 180)

    def _content_height(self) -> int:
        row_height = TRACK_HEIGHT + TRACK_GAP
        extra = EDIT_STRIP_HEIGHT if self._interaction_mode == "edit" else 0
        return max(320, len(self.project.tracks) * row_height + 40 + extra)

    def _sync_view_size(self) -> None:
        width = self._content_width()
        height = self._content_height()
        self.setMinimumSize(width, height)
        self.resize(width, height)

    def sizeHint(self) -> QSize:
        return QSize(self._content_width(), self._content_height())

    def set_hide_inactive_take_clips(self, hide: bool):
        self.hide_inactive_take_clips = bool(hide)
        self.update()

    def set_comp_regions_for_track(self, track_index: int, regions: List[dict]) -> None:
        self._comp_regions_by_track[int(track_index)] = list(regions)
        self.update()

    def clear_comp_regions(self) -> None:
        self._comp_regions_by_track = {}
        self.update()

    def set_track_automation_points(self, track_index: int, parameter: str, points: List[dict]) -> None:
        key = (int(track_index), str(parameter).strip().lower() or "volume_db")
        self._automation_points_by_track_param[key] = self._normalize_automation_points(points)
        self.update()

    def clear_automation_points(self) -> None:
        self._automation_points_by_track_param = {}
        self.update()

    def set_active_automation_parameter(self, track_index: int, parameter: str) -> None:
        normalized_track = int(track_index)
        if normalized_track < 0:
            return
        normalized_parameter = str(parameter).strip().lower() or "volume_db"
        self._active_automation_parameter_by_track[normalized_track] = normalized_parameter
        self.update()

    def set_comp_color_mode(self, mode: str) -> None:
        mode_value = str(mode).strip().lower()
        self._comp_color_mode = "single" if mode_value == "single" else "alternating"
        self.update()

    def _comp_region_color(self, source_take_number: int) -> QColor:
        if self._comp_color_mode == "single":
            return QColor(237, 168, 67, 210)
        palette = [
            QColor(237, 168, 67, 210),
            QColor(91, 168, 255, 210),
            QColor(168, 224, 99, 210),
            QColor(215, 130, 255, 210),
        ]
        index = abs(int(source_take_number)) % len(palette)
        return palette[index]

    def _normalize_automation_points(self, points: List[dict]) -> List[dict]:
        normalized: List[dict] = []
        for point in points:
            if not isinstance(point, dict):
                continue
            try:
                time_ms = max(0, int(point.get("time_ms", 0)))
            except (TypeError, ValueError):
                continue
            try:
                value = float(point.get("value", 0.5))
            except (TypeError, ValueError):
                value = 0.5
            normalized.append({"time_ms": time_ms, "value": max(0.0, min(1.0, value))})

        normalized.sort(key=lambda item: int(item["time_ms"]))
        deduped: List[dict] = []
        for point in normalized:
            if deduped and int(deduped[-1]["time_ms"]) == int(point["time_ms"]):
                deduped[-1] = point
            else:
                deduped.append(point)
        return deduped

    def _track_automation_parameter(self, track_index: int) -> str:
        return self._active_automation_parameter_by_track.get(int(track_index), "volume_db")

    def _track_automation_points(self, track_index: int, parameter: str) -> List[dict]:
        key = (int(track_index), str(parameter).strip().lower() or "volume_db")
        return self._automation_points_by_track_param.setdefault(key, [])

    def _lane_top_bottom(self, track_top: int) -> Tuple[int, int]:
        return track_top + 22, track_top + TRACK_HEIGHT - 5

    def _lane_value_to_y(self, lane_top: int, lane_bottom: int, value: float) -> int:
        clamped = max(0.0, min(1.0, float(value)))
        span = max(1, lane_bottom - lane_top)
        return int(round(lane_bottom - (clamped * span)))

    def _y_to_lane_value(self, lane_top: int, lane_bottom: int, y: int) -> float:
        span = max(1, lane_bottom - lane_top)
        clamped_y = max(lane_top, min(lane_bottom, int(y)))
        return max(0.0, min(1.0, float(lane_bottom - clamped_y) / float(span)))

    def _draw_track_automation(self, painter: QPainter, track_index: int, top: int) -> None:
        parameter = self._track_automation_parameter(track_index)
        points = self._track_automation_points(track_index, parameter)
        lane_top, lane_bottom = self._lane_top_bottom(top)
        cyan = QColor(0, 240, 255, 220)
        if points:
            painter.setPen(QPen(cyan, 2))
            for idx in range(len(points) - 1):
                left = points[idx]
                right = points[idx + 1]
                x1 = self.time_to_x(int(left["time_ms"]))
                y1 = self._lane_value_to_y(lane_top, lane_bottom, float(left["value"]))
                x2 = self.time_to_x(int(right["time_ms"]))
                y2 = self._lane_value_to_y(lane_top, lane_bottom, float(right["value"]))
                painter.drawLine(x1, y1, x2, y2)

        painter.setPen(QPen(QColor(0, 255, 255, 245), 1))
        for node_index, point in enumerate(points):
            x = self.time_to_x(int(point["time_ms"]))
            y = self._lane_value_to_y(lane_top, lane_bottom, float(point["value"]))
            radius = 4
            if self._dragging_automation_node == (int(track_index), parameter, int(node_index)):
                radius = 5
            painter.setBrush(QColor(0, 255, 255, 210))
            painter.drawEllipse(QPoint(x, y), radius, radius)

        parameter_label = parameter.replace("_", " ").upper()
        label_rect = QRect(118, top + 6, 152, 14)
        painter.setPen(QColor(0, 240, 255, 185))
        painter.drawText(label_rect, Qt.AlignLeft | Qt.AlignVCenter, f"AUTO: {parameter_label}")

    def _find_automation_node_at_point(self, point: QPoint) -> Optional[Tuple[int, str, int]]:
        track_index = self._track_index_for_y(int(point.y()))
        if track_index is None:
            return None
        parameter = self._track_automation_parameter(int(track_index))
        points = self._track_automation_points(int(track_index), parameter)
        lane_top, lane_bottom = self._lane_top_bottom(int(track_index) * (TRACK_HEIGHT + TRACK_GAP))
        for node_index, node in enumerate(points):
            node_x = self.time_to_x(int(node["time_ms"]))
            node_y = self._lane_value_to_y(lane_top, lane_bottom, float(node["value"]))
            if abs(int(point.x()) - int(node_x)) <= 7 and abs(int(point.y()) - int(node_y)) <= 7:
                return int(track_index), parameter, int(node_index)
        return None

    def _emit_automation_points_changed(self, track_index: int, parameter: str) -> None:
        if self.on_automation_points_changed is None:
            return
        points = self._track_automation_points(int(track_index), parameter)
        payload = [{"time_ms": int(point["time_ms"]), "value": float(point["value"])} for point in points]
        self.on_automation_points_changed(int(track_index), str(parameter), payload)

    def _insert_automation_node(self, track_index: int, parameter: str, time_ms: int, value: float) -> None:
        points = self._track_automation_points(int(track_index), parameter)
        points.append({"time_ms": max(0, int(time_ms)), "value": max(0.0, min(1.0, float(value)))})
        points[:] = self._normalize_automation_points(points)

    def _move_automation_node(self, track_index: int, parameter: str, node_index: int, time_ms: int, value: float) -> None:
        points = self._track_automation_points(int(track_index), parameter)
        if node_index < 0 or node_index >= len(points):
            return
        safe_time = max(0, int(time_ms))
        safe_value = max(0.0, min(1.0, float(value)))

        if node_index > 0:
            safe_time = max(safe_time, int(points[node_index - 1]["time_ms"]) + 1)
        if node_index < (len(points) - 1):
            safe_time = min(safe_time, int(points[node_index + 1]["time_ms"]) - 1)

        points[node_index] = {"time_ms": safe_time, "value": safe_value}

    def time_to_x(self, ms: int) -> int:
        seconds = ms / 1000.0
        return int(seconds * PIXELS_PER_SECOND * float(self._zoom_factor))

    def _read_waveform_peaks(self, file_path: str, target_points: int = 512) -> Optional[np.ndarray]:
        path = Path(file_path)
        if not path.exists():
            return None
        try:
            stat = path.stat()
        except OSError:
            return None

        cache_key = str(path.resolve())
        cache_entry = self._waveform_cache.get(cache_key)
        signature = (int(stat.st_mtime_ns), int(stat.st_size))
        if cache_entry is not None and cache_entry[0] == signature[0] and cache_entry[1] == signature[1]:
            return cache_entry[2]

        try:
            with sf.SoundFile(str(path)) as audio_file:
                if audio_file.frames <= 0:
                    return None
                block_size = max(1, int(audio_file.frames // target_points))
                peaks: list[float] = []
                while True:
                    block = audio_file.read(block_size, dtype="float32", always_2d=True)
                    if block.size == 0:
                        break
                    mono = np.mean(np.abs(block), axis=1)
                    peaks.append(float(np.max(mono)) if mono.size else 0.0)
        except Exception:
            return None

        if not peaks:
            return None

        peak_array = np.clip(np.asarray(peaks, dtype=np.float32), 0.0, 1.0)
        self._waveform_cache[cache_key] = (signature[0], signature[1], peak_array)
        return peak_array

    def _draw_clip_waveform(self, painter: QPainter, clip_rect: QRect, file_path: str) -> None:
        inner = clip_rect.adjusted(3, 3, -3, -3)
        if inner.width() < 4 or inner.height() < 4:
            return

        peaks = self._read_waveform_peaks(file_path)
        if peaks is None or peaks.size == 0:
            return

        column_count = max(1, inner.width())
        sample_positions = np.linspace(0, peaks.size - 1, column_count, dtype=np.int32)
        sampled = peaks[sample_positions]
        center_y = inner.center().y()
        max_amp = max(1, inner.height() // 2)

        painter.setPen(QPen(QColor(216, 238, 255, 210), 1))
        for offset, peak in enumerate(sampled):
            height = max(1, int(round(float(peak) * max_amp)))
            x = inner.left() + offset
            painter.drawLine(x, center_y - height, x, center_y + height)

    def _track_color(self, track) -> QColor:
        color_hex = getattr(track, "color_hex", "#00F0FF") or "#00F0FF"
        color = QColor(color_hex)
        return color if color.isValid() else QColor(0, 240, 255)

    def _clip_fill_color(self, track, clip_selected: bool) -> QColor:
        base = self._track_color(track)
        fill = QColor(base)
        fill.setAlpha(210 if clip_selected else 150)
        return fill

    def _clip_border_color(self, track, clip_selected: bool) -> QColor:
        base = self._track_color(track)
        return QColor(255, 230, 120) if clip_selected else base.darker(160)

    def _draw_slice_markers(self, painter: QPainter, clip_rect: QRect, clip) -> None:
        metadata = getattr(clip, "metadata", {}) or {}
        markers = metadata.get("slice_markers_ms", [])
        if not isinstance(markers, list):
            return
        painter.setPen(QPen(QColor(255, 70, 170), 1))
        clip_start_ms = int(clip.start_ms)
        clip_end_ms = clip_start_ms + int(clip.length_ms)
        for marker_ms in markers:
            try:
                marker_value = int(marker_ms)
            except (TypeError, ValueError):
                continue
            if marker_value < clip_start_ms or marker_value > clip_end_ms:
                continue
            marker_x = self.time_to_x(marker_value)
            painter.drawLine(marker_x, clip_rect.top() + 2, marker_x, clip_rect.bottom() - 2)

    def _clip_fade_values_ms(self, clip) -> Tuple[int, int]:
        metadata = getattr(clip, "metadata", {}) or {}
        length_ms = max(1, int(getattr(clip, "length_ms", 1)))
        try:
            fade_in_ms = int(metadata.get("fade_in_ms", 0))
        except (TypeError, ValueError):
            fade_in_ms = 0
        try:
            fade_out_ms = int(metadata.get("fade_out_ms", 0))
        except (TypeError, ValueError):
            fade_out_ms = 0
        return max(0, min(length_ms, fade_in_ms)), max(0, min(length_ms, fade_out_ms))

    def _set_clip_fade_values_ms(self, clip, fade_in_ms: int, fade_out_ms: int) -> Tuple[int, int]:
        metadata = dict(getattr(clip, "metadata", {}) or {})
        length_ms = max(1, int(getattr(clip, "length_ms", 1)))
        next_fade_in = max(0, min(length_ms, int(fade_in_ms)))
        next_fade_out = max(0, min(length_ms, int(fade_out_ms)))
        metadata["fade_in_ms"] = int(next_fade_in)
        metadata["fade_out_ms"] = int(next_fade_out)
        metadata.setdefault("fade_in_curve", "Linear")
        metadata.setdefault("fade_out_curve", "Linear")
        clip.metadata = metadata
        return int(next_fade_in), int(next_fade_out)

    def _draw_clip_fades(self, painter: QPainter, clip_rect: QRect, clip, clip_selected: bool) -> None:
        fade_in_ms, fade_out_ms = self._clip_fade_values_ms(clip)
        if fade_in_ms <= 0 and fade_out_ms <= 0 and not clip_selected:
            return

        clip_start = int(getattr(clip, "start_ms", 0))
        clip_end = clip_start + int(getattr(clip, "length_ms", 0))
        inner_top = clip_rect.top() + 2
        inner_bottom = clip_rect.bottom() - 2
        if inner_bottom <= inner_top:
            return

        painter.setPen(QPen(QColor(255, 190, 120, 210), 2))
        if fade_in_ms > 0:
            fade_in_end_ms = min(clip_end, clip_start + int(fade_in_ms))
            x1 = self.time_to_x(clip_start)
            x2 = self.time_to_x(fade_in_end_ms)
            painter.drawLine(x1, inner_bottom, x2, inner_top)
        if fade_out_ms > 0:
            fade_out_start_ms = max(clip_start, clip_end - int(fade_out_ms))
            x1 = self.time_to_x(fade_out_start_ms)
            x2 = self.time_to_x(clip_end)
            painter.drawLine(x1, inner_top, x2, inner_bottom)

        if not clip_selected:
            return

        handle_width = 6
        left_handle = QRect(clip_rect.left(), clip_rect.top(), handle_width, max(10, clip_rect.height()))
        right_handle = QRect(clip_rect.right() - handle_width + 1, clip_rect.top(), handle_width, max(10, clip_rect.height()))
        painter.setPen(QPen(QColor(255, 200, 130, 230), 1))
        painter.setBrush(QColor(255, 175, 110, 120))
        painter.drawRect(left_handle)
        painter.drawRect(right_handle)
        self._fade_handle_rects.append((int(clip.id), "in", left_handle))
        self._fade_handle_rects.append((int(clip.id), "out", right_handle))

    def _clip_tooltip_text(self, clip) -> str:
        clip_name = self._clip_display_name(clip)
        path = Path(clip.file_path)
        duration_ms = max(0, int(getattr(clip, "length_ms", 0)))
        duration_sec = duration_ms / 1000.0
        sample_rate_text = "unknown"
        try:
            info = sf.info(str(path))
            if getattr(info, "samplerate", 0):
                sample_rate_text = f"{int(info.samplerate)} Hz"
        except Exception:
            pass
        return f"{clip_name}\nSource: {path.name}\nDuration: {duration_sec:.2f}s\nSample rate: {sample_rate_text}"

    def _clip_display_name(self, clip) -> str:
        metadata = getattr(clip, "metadata", {}) or {}
        custom_name = str(metadata.get("display_name", "")).strip()
        if custom_name:
            return custom_name
        return Path(clip.file_path).name

    def _count_enabled_track_effects(self, track) -> int:
        settings = track.playback_settings
        effects = settings.effects
        return int(bool(effects.echo_enabled)) + int(bool(effects.distortion_enabled)) + int(bool(effects.chorus_enabled))

    def _draw_track_playback_badges(self, painter: QPainter, track, top: int) -> None:
        settings = track.playback_settings
        badges: list[tuple[str, QColor]] = []
        if settings.fade_in_ms > 0 or settings.fade_out_ms > 0:
            badges.append(("FADE", QColor(214, 123, 54)))
        if settings.loop_enabled and settings.loop_end_ms > settings.loop_start_ms:
            badges.append(("LOOP", QColor(66, 146, 230)))
        effect_count = self._count_enabled_track_effects(track)
        if effect_count > 0:
            badges.append((f"FX{effect_count}", QColor(134, 90, 214)))

        badge_x = 90
        for text, color in badges:
            badge_width = 32 if len(text) <= 4 else 42
            badge_rect = QRect(badge_x, top + 6, badge_width, 14)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawRect(badge_rect)
            painter.setPen(Qt.white)
            painter.drawText(badge_rect, Qt.AlignCenter, text)
            badge_x += badge_width + 6

    def _draw_track_playback_markers(self, painter: QPainter, track, track_index: int, top: int) -> None:
        settings = track.playback_settings
        lane_top = top + 22
        lane_bottom = top + TRACK_HEIGHT - 5

        if settings.fade_in_ms > 0:
            fade_in_x = self.time_to_x(int(settings.fade_in_ms))
            painter.setPen(QPen(QColor(255, 190, 120), 2, Qt.DashLine))
            painter.drawLine(fade_in_x, lane_top, fade_in_x, lane_bottom)
            painter.setPen(QColor(255, 210, 150))
            painter.drawText(fade_in_x + 4, top + 34, "FI")

        if settings.fade_out_ms > 0:
            track_end_ms = max(
                (
                    int(clip.start_ms) + int(clip.length_ms)
                    for clip in self.project.clips
                    if clip.track_index == track_index
                ),
                default=0,
            )
            fade_out_start_ms = max(0, track_end_ms - int(settings.fade_out_ms))
            fade_out_x = self.time_to_x(fade_out_start_ms)
            painter.setPen(QPen(QColor(255, 190, 120), 2, Qt.DashLine))
            painter.drawLine(fade_out_x, lane_top, fade_out_x, lane_bottom)
            painter.setPen(QColor(255, 210, 150))
            painter.drawText(fade_out_x + 4, top + 46, "FO")

        if settings.loop_enabled and settings.loop_end_ms > settings.loop_start_ms:
            loop_start_x = self.time_to_x(int(settings.loop_start_ms))
            loop_end_x = self.time_to_x(int(settings.loop_end_ms))
            loop_rect = QRect(min(loop_start_x, loop_end_x), top + 24, max(abs(loop_end_x - loop_start_x), 2), TRACK_HEIGHT - 31)
            painter.setPen(QPen(QColor(90, 175, 255), 2, Qt.DashDotLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(loop_rect)
            painter.setPen(QColor(185, 225, 255))
            painter.drawText(loop_rect.adjusted(4, 0, -4, 0), Qt.AlignLeft | Qt.AlignTop, "LOOP")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(30, 30, 30))  # background
        self._clip_rects = []
        self._fade_handle_rects = []

        painter.setPen(QPen(QColor(53, 64, 82), 1))
        painter.drawLine(0, MARKER_HEADER_HEIGHT, self.width(), MARKER_HEADER_HEIGHT)

        # Draw tracks and clips
        for track_index, track in enumerate(self.project.tracks):
            top = track_index * (TRACK_HEIGHT + TRACK_GAP)
            # Track background
            track_rect = QRect(0, top, self.width(), TRACK_HEIGHT)
            track_color = self._track_color(track)
            if self.selected_track_index == track_index:
                selected_fill = QColor(track_color)
                selected_fill.setAlpha(80)
                painter.fillRect(track_rect, selected_fill)
            else:
                lane_fill = QColor(track_color)
                lane_fill.setAlpha(42)
                painter.fillRect(track_rect, lane_fill)
            painter.setPen(QPen(track_color.darker(170), 1))
            painter.drawRect(track_rect.adjusted(0, 0, -1, -1))
            lane_center_y = top + 20 + ((TRACK_HEIGHT - 25) // 2)
            painter.setPen(QPen(QColor(220, 230, 240, 70), 1))
            painter.drawLine(0, lane_center_y, self.width(), lane_center_y)
            painter.setPen(Qt.white)
            painter.drawText(8, top + 18, track.name)
            self._draw_track_playback_badges(painter, track, top)
            self._draw_track_playback_markers(painter, track, track_index, top)

            # Draw clips on this track
            for clip in self.project.clips:
                if clip.track_index != track_index:
                    continue

                metadata = getattr(clip, "metadata", {}) or {}
                is_recording_take = metadata.get("source") == "recording_take"
                is_active_take = bool(metadata.get("is_active_take", True))
                if self.hide_inactive_take_clips and is_recording_take and not is_active_take:
                    continue

                x = self.time_to_x(clip.start_ms)
                w = self.time_to_x(clip.length_ms)
                clip_rect = QRect(x, top + 20, max(w, 10), TRACK_HEIGHT - 25)

                clip_selected = self.selected_clip_id == clip.id
                painter.setPen(QPen(self._clip_border_color(track, clip_selected), 2))
                painter.setBrush(self._clip_fill_color(track, clip_selected))
                painter.drawRoundedRect(clip_rect, 4, 4)
                self._clip_rects.append((clip.id, clip_rect))
                self._draw_clip_waveform(painter, clip_rect, clip.file_path)
                self._draw_slice_markers(painter, clip_rect, clip)
                self._draw_clip_fades(painter, clip_rect, clip, clip_selected)

                label_rect = clip_rect.adjusted(6, 3, -6, -3)
                if label_rect.width() > 24:
                    painter.setPen(QColor(242, 246, 250))
                    painter.drawText(label_rect, Qt.AlignLeft | Qt.AlignTop, self._clip_display_name(clip))

                if clip_selected:
                    painter.setPen(QPen(QColor(255, 230, 120), 3))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawRoundedRect(clip_rect.adjusted(-1, -1, 1, 1), 5, 5)

                if is_recording_take:
                    badge_text = "ACTIVE" if is_active_take else "ALT"
                    badge_color = QColor(20, 130, 80) if is_active_take else QColor(110, 110, 110)
                    badge_w = 44 if is_active_take else 28
                    badge_rect = QRect(clip_rect.right() - badge_w - 4, clip_rect.top() + 4, badge_w, 14)
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(badge_color)
                    painter.drawRect(badge_rect)
                    painter.setPen(Qt.white)
                    painter.drawText(badge_rect, Qt.AlignCenter, badge_text)

                    if bool(metadata.get("comp_selected", False)):
                        comp_rect = QRect(clip_rect.left() + 4, clip_rect.top() + 4, 38, 14)
                        painter.setPen(Qt.NoPen)
                        painter.setBrush(QColor(188, 102, 22))
                        painter.drawRect(comp_rect)
                        painter.setPen(Qt.white)
                        painter.drawText(comp_rect, Qt.AlignCenter, "COMP")

            # Draw comp regions as track overlays.
            for region in self._comp_regions_by_track.get(track_index, []):
                start_ms = int(region.get("start_ms", 0))
                end_ms = int(region.get("end_ms", 0))
                if end_ms <= start_ms:
                    continue
                source_take_number = int(region.get("source_take_number", 0))
                color = self._comp_region_color(source_take_number)
                x1 = self.time_to_x(start_ms)
                x2 = self.time_to_x(end_ms)
                overlay = QRect(min(x1, x2), top + 22, max(abs(x2 - x1), 2), TRACK_HEIGHT - 29)
                painter.setPen(QPen(color, 2, Qt.DashLine))
                fill = QColor(color)
                fill.setAlpha(60)
                painter.setBrush(fill)
                painter.drawRect(overlay)
                painter.setPen(Qt.white)
                painter.drawText(overlay.adjusted(4, 0, -4, 0), Qt.AlignLeft | Qt.AlignVCenter, f"R{int(region.get('region_id', 0))}")

            if self._selected_time_range is not None:
                selection_track_index, start_ms, end_ms = self._selected_time_range
                if int(selection_track_index) == int(track_index) and end_ms > start_ms:
                    x1 = self.time_to_x(int(start_ms))
                    x2 = self.time_to_x(int(end_ms))
                    selected_rect = QRect(min(x1, x2), top + 22, max(abs(x2 - x1), 2), TRACK_HEIGHT - 29)
                    painter.setPen(QPen(QColor(112, 190, 255), 2, Qt.DashLine))
                    painter.setBrush(QColor(112, 190, 255, 40))
                    painter.drawRect(selected_rect)

            self._draw_track_automation(painter, track_index, top)

        # Draw in-progress range selection on top for immediate feedback.
        if self._comp_selecting and self._comp_select_track_index is not None and self._comp_select_start_ms is not None and self._comp_select_end_ms is not None:
            top = int(self._comp_select_track_index) * (TRACK_HEIGHT + TRACK_GAP)
            x1 = self.time_to_x(self._comp_select_start_ms)
            x2 = self.time_to_x(self._comp_select_end_ms)
            sel_rect = QRect(min(x1, x2), top + 22, max(abs(x2 - x1), 2), TRACK_HEIGHT - 29)
            painter.setPen(QPen(QColor(112, 190, 255), 2))
            painter.setBrush(QColor(112, 190, 255, 55))
            painter.drawRect(sel_rect)

        playhead_x = self.time_to_x(self.playhead_ms)
        painter.setPen(QPen(QColor(255, 92, 92), 2))
        painter.drawLine(playhead_x, 0, playhead_x, self.height())
        self._draw_markers(painter)
        self._draw_edit_strip(painter)

        painter.end()

    def _x_to_ms(self, x: int) -> int:
        zoom = max(0.0625, float(self._zoom_factor))
        seconds = float(max(0, x)) / float(PIXELS_PER_SECOND * zoom)
        return int(round(seconds * 1000.0))

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta != 0 and self.on_zoom_request is not None:
                steps = 1 if delta > 0 else -1
                self.on_zoom_request(steps, int(event.position().x()))
                event.accept()
                return
        super().wheelEvent(event)

    def _find_clip_at_point(self, point: QPoint):
        for clip_id, clip_rect in reversed(self._clip_rects):
            if clip_rect.contains(point):
                return clip_id
        return None

    def _find_fade_handle_at_point(self, point: QPoint) -> Optional[Tuple[int, str]]:
        for clip_id, edge, rect in reversed(self._fade_handle_rects):
            if rect.contains(point):
                return int(clip_id), str(edge)
        return None

    def _find_clip_by_id(self, clip_id: int):
        for clip in self.project.clips:
            if clip.id == clip_id:
                return clip
        return None

    def _set_selected_track_from_timeline(self, track_index: Optional[int]) -> None:
        if track_index is None:
            return
        normalized = int(track_index)
        if normalized < 0 or normalized >= len(self.project.tracks):
            return
        if self.selected_track_index == normalized:
            return
        self.selected_track_index = normalized
        if self.on_track_selected is not None:
            self.on_track_selected(normalized)

    def _track_index_for_y(self, y: int) -> Optional[int]:
        if y < 0:
            return None
        row_height = TRACK_HEIGHT + TRACK_GAP
        track_index = int(y // row_height)
        if track_index < 0 or track_index >= len(self.project.tracks):
            return None
        track_top = track_index * row_height
        if y > (track_top + TRACK_HEIGHT):
            return None
        return track_index

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)

        if self._interaction_mode == "edit":
            strip = self._edit_strip_rect()
            context = self._active_gain_envelope_context()
            if strip is not None and context is not None and strip.contains(event.position().toPoint()):
                start_x = self.time_to_x(int(context["start_ms"]))
                end_x = self.time_to_x(int(context["end_ms"]))
                start_y = self._db_to_strip_y(strip, float(context["start_db"]))
                end_y = self._db_to_strip_y(strip, float(context["end_db"]))
                point = event.position().toPoint()
                if abs(int(point.x()) - int(start_x)) <= 8 and abs(int(point.y()) - int(start_y)) <= 8:
                    self._dragging_gain_handle = {"edge": "start", "context": context}
                    return
                if abs(int(point.x()) - int(end_x)) <= 8 and abs(int(point.y()) - int(end_y)) <= 8:
                    self._dragging_gain_handle = {"edge": "end", "context": context}
                    return

        if int(event.position().toPoint().y()) <= MARKER_HEADER_HEIGHT:
            self._scrubbing_playhead = True
            scrub_ms = self._x_to_ms(event.position().toPoint().x())
            self.playhead_ms = int(scrub_ms)
            if self.on_playhead_scrubbed is not None:
                self.on_playhead_scrubbed(int(scrub_ms))
            self.update()
            return

        fade_hit = self._find_fade_handle_at_point(event.position().toPoint())
        if fade_hit is not None:
            clip = self._find_clip_by_id(int(fade_hit[0]))
            if clip is not None:
                self.selected_clip_id = int(fade_hit[0])
                self._set_selected_track_from_timeline(int(clip.track_index))
                self._dragging_fade_handle = (int(fade_hit[0]), str(fade_hit[1]))
                self._dragging_clip_id = None
                self._drag_start_point = None
                self._drag_origin_start_ms = None
                self._dragging_automation_node = None
                self.setFocus(Qt.MouseFocusReason)
                self.update()
                return

        automation_hit = self._find_automation_node_at_point(event.position().toPoint())
        if automation_hit is not None:
            self._dragging_automation_node = automation_hit
            self.selected_clip_id = None
            self._dragging_clip_id = None
            self._drag_start_point = None
            self._drag_origin_start_ms = None
            self._set_selected_track_from_timeline(int(automation_hit[0]))
            self.setFocus(Qt.MouseFocusReason)
            self.update()
            return

        clip_id = self._find_clip_at_point(event.position().toPoint())

        if self._tool_mode == "razor" and clip_id is not None:
            clip = self._find_clip_by_id(int(clip_id))
            if clip is not None and self.on_split_clip_requested is not None:
                split_ms = self._x_to_ms(event.position().toPoint().x())
                clip_start = int(getattr(clip, "start_ms", 0))
                clip_end = clip_start + int(getattr(clip, "length_ms", 0))
                if clip_start < split_ms < clip_end:
                    self.on_split_clip_requested(int(clip_id), int(split_ms))
                    self.selected_clip_id = int(clip_id)
                    self.update()
                    return

        if self._tool_mode == "envelope" and clip_id is None:
            track_index = self._track_index_for_y(event.position().toPoint().y())
            if track_index is not None:
                self._set_selected_track_from_timeline(int(track_index))
                parameter = self._track_automation_parameter(int(track_index))
                clicked_ms = self._x_to_ms(event.position().toPoint().x())
                lane_top, lane_bottom = self._lane_top_bottom(int(track_index) * (TRACK_HEIGHT + TRACK_GAP))
                value = self._y_to_lane_value(lane_top, lane_bottom, int(event.position().toPoint().y()))
                self._insert_automation_node(int(track_index), parameter, int(clicked_ms), float(value))
                self._emit_automation_points_changed(int(track_index), parameter)
                self.update()
                return

        self.selected_clip_id = clip_id
        if clip_id is None:
            track_index = self._track_index_for_y(event.position().toPoint().y())
            self._set_selected_track_from_timeline(track_index)
            clicked_ms = self._x_to_ms(event.position().toPoint().x())
            if track_index is not None and self.selected_track_index is not None and int(track_index) == int(self.selected_track_index):
                modifiers = event.modifiers()
                if modifiers & Qt.KeyboardModifier.AltModifier:
                    if self._edit_selected_time_range_edge(int(track_index), int(clicked_ms), move_start=True):
                        self.update()
                        return
                if modifiers & Qt.KeyboardModifier.ShiftModifier:
                    if self._edit_selected_time_range_edge(int(track_index), int(clicked_ms), move_start=False):
                        self.update()
                        return
                self._comp_selecting = True
                self._comp_select_track_index = int(track_index)
                self._comp_select_start_ms = int(clicked_ms)
                self._comp_select_end_ms = self._comp_select_start_ms
            else:
                self._selected_time_range = None
                self._emit_time_range_changed(None, None, None)
            self._dragging_clip_id = None
            self._drag_start_point = None
            self._drag_origin_start_ms = None
            self.update()
            return

        selected_clip = self._find_clip_by_id(clip_id)
        if selected_clip is not None:
            self._set_selected_track_from_timeline(int(selected_clip.track_index))
            if self._interaction_mode == "edit":
                clip_start_ms = int(getattr(selected_clip, "start_ms", 0))
                clip_end_ms = clip_start_ms + int(getattr(selected_clip, "length_ms", 0))
                self._set_selected_time_range(int(selected_clip.track_index), int(clip_start_ms), int(clip_end_ms))
            else:
                self._selected_time_range = None
            self._dragging_clip_id = clip_id
            self._drag_start_point = event.position().toPoint()
            self._drag_origin_start_ms = int(selected_clip.start_ms)
            self.setFocus(Qt.MouseFocusReason)
        self.update()

    def mouseDoubleClickEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mouseDoubleClickEvent(event)

        clip_id = self._find_clip_at_point(event.position().toPoint())
        if clip_id is not None:
            clip = self._find_clip_by_id(int(clip_id))
            if clip is not None:
                track_index = int(clip.track_index)
                self._set_selected_track_from_timeline(track_index)
                if self.on_track_double_click is not None:
                    self.on_track_double_click(track_index)
                return

        track_index = self._track_index_for_y(event.position().toPoint().y())
        if track_index is None:
            return super().mouseDoubleClickEvent(event)

        if event.position().toPoint().x() <= 128:
            self._set_selected_track_from_timeline(int(track_index))
            if self.on_track_double_click is not None:
                self.on_track_double_click(int(track_index))
            return

        self._set_selected_track_from_timeline(int(track_index))
        parameter = self._track_automation_parameter(int(track_index))
        clicked_ms = self._x_to_ms(event.position().toPoint().x())
        lane_top, lane_bottom = self._lane_top_bottom(int(track_index) * (TRACK_HEIGHT + TRACK_GAP))
        value = self._y_to_lane_value(lane_top, lane_bottom, int(event.position().toPoint().y()))
        self._insert_automation_node(int(track_index), parameter, int(clicked_ms), float(value))
        self._emit_automation_points_changed(int(track_index), parameter)
        self.update()
        return

    def mouseMoveEvent(self, event):
        if self._dragging_gain_handle is not None:
            if not (event.buttons() & Qt.MouseButton.LeftButton):
                return super().mouseMoveEvent(event)
            drag_context = self._dragging_gain_handle.get("context")
            if not isinstance(drag_context, dict):
                return super().mouseMoveEvent(event)
            strip = self._edit_strip_rect()
            if strip is None:
                return super().mouseMoveEvent(event)
            next_db = self._strip_y_to_db(strip, int(event.position().toPoint().y()))
            start_db = float(drag_context.get("start_db", 0.0))
            end_db = float(drag_context.get("end_db", 0.0))
            if str(self._dragging_gain_handle.get("edge")) == "start":
                start_db = float(next_db)
            else:
                end_db = float(next_db)
            self._apply_active_gain_envelope(drag_context, start_db, end_db)
            clip_id = int(drag_context.get("clip_id", -1))
            if self.on_gain_envelope_changed is not None and clip_id >= 0:
                self.on_gain_envelope_changed(
                    clip_id,
                    int(drag_context.get("start_ms", 0)),
                    int(drag_context.get("end_ms", 0)),
                    float(drag_context.get("start_db", 0.0)),
                    float(drag_context.get("end_db", 0.0)),
                    False,
                )
            self.update()
            return

        if self._scrubbing_playhead and (event.buttons() & Qt.MouseButton.LeftButton):
            scrub_ms = self._x_to_ms(event.position().toPoint().x())
            self.playhead_ms = int(scrub_ms)
            if self.on_playhead_scrubbed is not None:
                self.on_playhead_scrubbed(int(scrub_ms))
            self.update()
            return

        clip_id = self._find_clip_at_point(event.position().toPoint())
        if clip_id != self._hovered_clip_id:
            self._hovered_clip_id = clip_id
            if clip_id is None:
                marker_hit = self._find_marker_near_x(int(event.position().toPoint().x()))
                if marker_hit is not None and int(event.position().toPoint().y()) <= MARKER_HEADER_HEIGHT + 4:
                    QToolTip.showText(
                        event.globalPosition().toPoint(),
                        f"{marker_hit.get('name', 'Marker')}\n{int(marker_hit.get('time_ms', 0)) / 1000.0:.3f}s",
                        self,
                    )
                else:
                    QToolTip.hideText()
            else:
                clip = self._find_clip_by_id(clip_id)
                if clip is not None:
                    QToolTip.showText(event.globalPosition().toPoint(), self._clip_tooltip_text(clip), self)

        if self._comp_selecting and self._comp_select_start_ms is not None:
            self._comp_select_end_ms = self._x_to_ms(event.position().toPoint().x())
            self.update()
            return

        if self._dragging_fade_handle is not None:
            if not (event.buttons() & Qt.LeftButton):
                return super().mouseMoveEvent(event)
            clip_id, edge = self._dragging_fade_handle
            clip = self._find_clip_by_id(int(clip_id))
            if clip is None:
                return super().mouseMoveEvent(event)

            clip_start_ms = int(getattr(clip, "start_ms", 0))
            clip_end_ms = clip_start_ms + int(getattr(clip, "length_ms", 0))
            pointer_ms = self._x_to_ms(event.position().toPoint().x())
            fade_in_ms, fade_out_ms = self._clip_fade_values_ms(clip)
            if edge == "in":
                fade_in_ms = max(0, min(int(getattr(clip, "length_ms", 0)), int(pointer_ms - clip_start_ms)))
            else:
                fade_out_ms = max(0, min(int(getattr(clip, "length_ms", 0)), int(clip_end_ms - pointer_ms)))
            next_in, next_out = self._set_clip_fade_values_ms(clip, fade_in_ms, fade_out_ms)
            if self.on_clip_fade_changed is not None:
                self.on_clip_fade_changed(int(clip_id), int(next_in), int(next_out), False)
            self.update()
            return

        if self._dragging_automation_node is not None:
            if not (event.buttons() & Qt.LeftButton):
                return super().mouseMoveEvent(event)
            track_index, parameter, node_index = self._dragging_automation_node
            lane_top, lane_bottom = self._lane_top_bottom(int(track_index) * (TRACK_HEIGHT + TRACK_GAP))
            next_time_ms = self._x_to_ms(event.position().toPoint().x())
            next_value = self._y_to_lane_value(lane_top, lane_bottom, int(event.position().toPoint().y()))
            self._move_automation_node(int(track_index), str(parameter), int(node_index), int(next_time_ms), float(next_value))
            self.update()
            return

        if self._dragging_clip_id is None or self._drag_start_point is None or self._drag_origin_start_ms is None:
            return super().mouseMoveEvent(event)
        if not (event.buttons() & Qt.LeftButton):
            return super().mouseMoveEvent(event)

        clip = self._find_clip_by_id(self._dragging_clip_id)
        if clip is None:
            return

        delta_x = event.position().toPoint().x() - self._drag_start_point.x()
        delta_ms = self._x_to_ms(abs(delta_x))
        if delta_x < 0:
            delta_ms *= -1
        clip.start_ms = max(0, int(self._drag_origin_start_ms + delta_ms))
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._dragging_gain_handle is not None:
            drag_context = self._dragging_gain_handle.get("context")
            self._dragging_gain_handle = None
            if isinstance(drag_context, dict):
                clip_id = int(drag_context.get("clip_id", -1))
                if self.on_gain_envelope_changed is not None and clip_id >= 0:
                    self.on_gain_envelope_changed(
                        clip_id,
                        int(drag_context.get("start_ms", 0)),
                        int(drag_context.get("end_ms", 0)),
                        float(drag_context.get("start_db", 0.0)),
                        float(drag_context.get("end_db", 0.0)),
                        True,
                    )
            self.update()
            return super().mouseReleaseEvent(event)

        if event.button() == Qt.MouseButton.LeftButton and self._scrubbing_playhead:
            self._scrubbing_playhead = False
            return super().mouseReleaseEvent(event)

        if event.button() == Qt.MouseButton.LeftButton and self._dragging_fade_handle is not None:
            clip_id, _edge = self._dragging_fade_handle
            self._dragging_fade_handle = None
            clip = self._find_clip_by_id(int(clip_id))
            if clip is not None:
                fade_in_ms, fade_out_ms = self._clip_fade_values_ms(clip)
                if self.on_clip_fade_changed is not None:
                    self.on_clip_fade_changed(int(clip_id), int(fade_in_ms), int(fade_out_ms), True)
                elif self.on_project_changed is not None:
                    self.on_project_changed()
            self.update()
            return super().mouseReleaseEvent(event)

        if event.button() == Qt.MouseButton.LeftButton and self._dragging_automation_node is not None:
            track_index, parameter, _node_index = self._dragging_automation_node
            self._dragging_automation_node = None
            self._emit_automation_points_changed(int(track_index), str(parameter))
            self.update()
            return super().mouseReleaseEvent(event)

        if event.button() == Qt.MouseButton.LeftButton and self._comp_selecting:
            start_ms = self._comp_select_start_ms
            end_ms = self._comp_select_end_ms
            track_index = self._comp_select_track_index
            self._comp_selecting = False
            self._comp_select_start_ms = None
            self._comp_select_end_ms = None
            self._comp_select_track_index = None

            if start_ms is not None and end_ms is not None and track_index is not None:
                range_start = min(int(start_ms), int(end_ms))
                range_end = max(int(start_ms), int(end_ms))
                if range_end - range_start >= 50 and self.on_comp_range_selected is not None:
                    self._set_selected_time_range(int(track_index), range_start, range_end)
                    self.on_comp_range_selected(int(track_index), range_start, range_end)
                elif range_end - range_start < 50:
                    self._selected_time_range = None
                    self._emit_time_range_changed(None, None, None)
            self.update()
            return super().mouseReleaseEvent(event)

        if event.button() == Qt.MouseButton.LeftButton and self._dragging_clip_id is not None and self.on_project_changed is not None:
            self.on_project_changed()
        self._dragging_clip_id = None
        self._drag_start_point = None
        self._drag_origin_start_ms = None
        return super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self.selected_clip_id is not None:
            before_count = len(self.project.clips)
            self.project.clips = [clip for clip in self.project.clips if clip.id != self.selected_clip_id]
            if len(self.project.clips) != before_count:
                self.selected_clip_id = None
                if self.on_project_changed is not None:
                    self.on_project_changed()
                self.update()
            return
        return super().keyPressEvent(event)

    def _show_context_menu(self, pos: QPoint) -> None:
        """Show a context menu for clip actions or adding a clip at the clicked position."""
        clip_id = self._find_clip_at_point(pos)
        track_index = self._track_index_for_y(pos.y())
        start_ms = self._x_to_ms(pos.x())
        marker_hit = self._find_marker_near_x(int(pos.x())) if int(pos.y()) <= MARKER_HEADER_HEIGHT + 6 else None

        menu = QMenu(self)

        if marker_hit is not None:
            marker_id = int(marker_hit.get("id", 0))
            marker_time = int(marker_hit.get("time_ms", 0))
            jump_act = menu.addAction(f"Jump to Marker: {marker_hit.get('name', 'Marker')}")
            jump_act.triggered.connect(lambda: self._emit_marker_action("jump", marker_time, marker_id))
            rename_act = menu.addAction("Rename Marker")
            rename_act.triggered.connect(lambda: self._emit_marker_action("rename", marker_time, marker_id))
            delete_act = menu.addAction("Delete Marker")
            delete_act.triggered.connect(lambda: self._emit_marker_action("delete", marker_time, marker_id))
            menu.addSeparator()
        add_marker_act = menu.addAction(f"Add Marker at {start_ms / 1000.0:.3f}s")
        add_marker_act.triggered.connect(lambda: self._emit_marker_action("add", start_ms, None))
        menu.addSeparator()

        if clip_id is not None:
            select_act = menu.addAction("Select clip")
            select_act.triggered.connect(lambda: self._select_clip(clip_id))
            fade_settings_act = menu.addAction("Fade Settings…")
            fade_settings_act.triggered.connect(lambda: self._dispatch_clip_action("fade_settings", clip_id))
            rename_act = menu.addAction("Rename")
            rename_act.triggered.connect(lambda: self._dispatch_clip_action("rename", clip_id))
            duplicate_act = menu.addAction("Duplicate")
            duplicate_act.triggered.connect(lambda: self._dispatch_clip_action("duplicate", clip_id))
            delete_act = menu.addAction("Delete clip")
            delete_act.triggered.connect(lambda: self._delete_clip(clip_id))
            export_act = menu.addAction("Export Clip")
            export_act.triggered.connect(lambda: self._dispatch_clip_action("export", clip_id))
            send_demucs_act = menu.addAction("Send to Demucs")
            send_demucs_act.triggered.connect(lambda: self._dispatch_clip_action("demucs", clip_id))
            send_music_act = menu.addAction("Send to ACE-Step")
            send_music_act.triggered.connect(lambda: self._dispatch_clip_action("ace_step", clip_id))
            properties_act = menu.addAction("Properties")
            properties_act.triggered.connect(lambda: self._dispatch_clip_action("properties", clip_id))
        elif track_index is not None and self.on_add_clip_at is not None:
            track_name = self.project.tracks[track_index].name
            add_act = menu.addAction(f'Add clip at {start_ms / 1000:.2f}s on \u201c{track_name}\u201d')
            add_act.setToolTip("Open a file browser and place an audio clip at this position")
            add_act.triggered.connect(lambda: self.on_add_clip_at(track_index, start_ms))  # type: ignore[misc]
        else:
            menu.addAction("(No track at this position)").setEnabled(False)

        menu.exec(self.mapToGlobal(pos))

    def _select_clip(self, clip_id: int) -> None:
        self.selected_clip_id = clip_id
        selected_clip = self._find_clip_by_id(clip_id)
        if selected_clip is not None:
            self._set_selected_track_from_timeline(int(selected_clip.track_index))
        self.update()

    def _delete_clip(self, clip_id: int) -> None:
        before_count = len(self.project.clips)
        self.project.clips = [c for c in self.project.clips if c.id != clip_id]
        if len(self.project.clips) != before_count:
            if self.selected_clip_id == clip_id:
                self.selected_clip_id = None
            if self.on_project_changed is not None:
                self.on_project_changed()
            self.update()

    def _dispatch_clip_action(self, action: str, clip_id: int) -> None:
        self.selected_clip_id = clip_id
        selected_clip = self._find_clip_by_id(clip_id)
        if selected_clip is not None:
            self._set_selected_track_from_timeline(int(selected_clip.track_index))
        if self.on_clip_action is not None:
            self.on_clip_action(action, clip_id)
        self.update()