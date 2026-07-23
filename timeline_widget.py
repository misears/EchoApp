
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtCore import Qt, QRect

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
        self.setMinimumHeight(300)
        self.setMouseTracking(True)

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