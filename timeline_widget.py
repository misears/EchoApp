
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtCore import Qt, QRect, QPoint
from typing import Callable, Dict, List, Optional

from project_model import Project

TRACK_HEIGHT = 60
TRACK_GAP = 10
CLIP_COLOR = QColor(100, 180, 255)
CLIP_BORDER = QColor(30, 60, 120)

PIXELS_PER_SECOND = 50  # how many pixels represent one second

class TimelineWidget(QWidget):
    
    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.project = project
        self.selected_clip_id = None
        self.selected_track_index = None
        self.hide_inactive_take_clips = False
        self.on_project_changed: Optional[Callable[[], None]] = None
        self.on_comp_range_selected: Optional[Callable[[int, int, int], None]] = None
        self._clip_rects = []
        self._dragging_clip_id = None
        self._drag_start_point = None
        self._drag_origin_start_ms = None
        self._comp_regions_by_track: Dict[int, List[dict]] = {}
        self._comp_color_mode = "alternating"
        self._comp_selecting = False
        self._comp_select_start_ms: Optional[int] = None
        self._comp_select_end_ms: Optional[int] = None
        self._comp_select_track_index: Optional[int] = None
        self.setMinimumHeight(300)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

    def set_project(self, project: Project):
        self.project = project
        self.update()

    def set_selected_track(self, track_index):
        self.selected_track_index = track_index
        self.update()

    def set_hide_inactive_take_clips(self, hide: bool):
        self.hide_inactive_take_clips = bool(hide)
        self.update()

    def set_comp_regions_for_track(self, track_index: int, regions: List[dict]) -> None:
        self._comp_regions_by_track[int(track_index)] = list(regions)
        self.update()

    def clear_comp_regions(self) -> None:
        self._comp_regions_by_track = {}
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

    def time_to_x(self, ms: int) -> int:
        seconds = ms / 1000.0
        return int(seconds * PIXELS_PER_SECOND)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(30, 30, 30))  # background
        self._clip_rects = []

        # Draw tracks and clips
        for track_index, track in enumerate(self.project.tracks):
            top = track_index * (TRACK_HEIGHT + TRACK_GAP)
            # Track background
            track_rect = QRect(0, top, self.width(), TRACK_HEIGHT)
            if self.selected_track_index == track_index:
                painter.fillRect(track_rect, QColor(65, 85, 95))
            else:
                painter.fillRect(track_rect, QColor(40, 40, 40))
            painter.setPen(Qt.white)
            painter.drawText(5, top + 20, track.name)

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

                painter.setPen(QPen(CLIP_BORDER, 2))
                painter.setBrush(CLIP_COLOR)
                painter.drawRect(clip_rect)
                self._clip_rects.append((clip.id, clip_rect))

                if self.selected_clip_id == clip.id:
                    painter.setPen(QPen(QColor(255, 230, 120), 3))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawRect(clip_rect.adjusted(-1, -1, 1, 1))

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

        # Draw in-progress range selection on top for immediate feedback.
        if self._comp_selecting and self._comp_select_track_index is not None and self._comp_select_start_ms is not None and self._comp_select_end_ms is not None:
            top = int(self._comp_select_track_index) * (TRACK_HEIGHT + TRACK_GAP)
            x1 = self.time_to_x(self._comp_select_start_ms)
            x2 = self.time_to_x(self._comp_select_end_ms)
            sel_rect = QRect(min(x1, x2), top + 22, max(abs(x2 - x1), 2), TRACK_HEIGHT - 29)
            painter.setPen(QPen(QColor(112, 190, 255), 2))
            painter.setBrush(QColor(112, 190, 255, 55))
            painter.drawRect(sel_rect)

        painter.end()

    def _x_to_ms(self, x: int) -> int:
        seconds = float(max(0, x)) / float(PIXELS_PER_SECOND)
        return int(round(seconds * 1000.0))

    def _find_clip_at_point(self, point: QPoint):
        for clip_id, clip_rect in reversed(self._clip_rects):
            if clip_rect.contains(point):
                return clip_id
        return None

    def _find_clip_by_id(self, clip_id: int):
        for clip in self.project.clips:
            if clip.id == clip_id:
                return clip
        return None

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
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)

        clip_id = self._find_clip_at_point(event.position().toPoint())
        self.selected_clip_id = clip_id
        if clip_id is None:
            track_index = self._track_index_for_y(event.position().toPoint().y())
            if track_index is not None and self.selected_track_index is not None and int(track_index) == int(self.selected_track_index):
                self._comp_selecting = True
                self._comp_select_track_index = int(track_index)
                self._comp_select_start_ms = self._x_to_ms(event.position().toPoint().x())
                self._comp_select_end_ms = self._comp_select_start_ms
            self._dragging_clip_id = None
            self._drag_start_point = None
            self._drag_origin_start_ms = None
            self.update()
            return

        selected_clip = self._find_clip_by_id(clip_id)
        if selected_clip is not None:
            self._dragging_clip_id = clip_id
            self._drag_start_point = event.position().toPoint()
            self._drag_origin_start_ms = int(selected_clip.start_ms)
            self.setFocus(Qt.MouseFocusReason)
        self.update()

    def mouseMoveEvent(self, event):
        if self._comp_selecting and self._comp_select_start_ms is not None:
            self._comp_select_end_ms = self._x_to_ms(event.position().toPoint().x())
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
        if event.button() == Qt.LeftButton and self._comp_selecting:
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
                    self.on_comp_range_selected(int(track_index), range_start, range_end)
            self.update()
            return super().mouseReleaseEvent(event)

        if event.button() == Qt.LeftButton and self._dragging_clip_id is not None and self.on_project_changed is not None:
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