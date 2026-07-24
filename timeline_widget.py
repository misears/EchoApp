
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtCore import Qt, QRect, QPoint

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
        self.on_project_changed = None
        self._clip_rects = []
        self._dragging_clip_id = None
        self._drag_start_point = None
        self._drag_origin_start_ms = None
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

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)

        clip_id = self._find_clip_at_point(event.position().toPoint())
        self.selected_clip_id = clip_id
        if clip_id is None:
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