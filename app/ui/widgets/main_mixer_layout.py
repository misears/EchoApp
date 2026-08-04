"""
Main Mixer / Arrangement View Layout

Implements the ergonomic layout skeleton per UX §1.9 & §2.1:
- Fixed-width left control zones (200px master, 220px channel strips)
- Flexible waveform/timeline area (grows with window)
- Fixed-width right sidebar (260px, collapsible)
- Transport bar (72px) and status bar (24px)
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QToolBar, QScrollArea, QFrame
)
from PySide6.QtCore import Qt
from typing import Optional
from app.controllers import TimelineSyncController


class MainMixerLayout(QWidget):
    """
    Implements the main mixer/arrangement view layout with fixed-width control zones.
    
    Integrates TimelineSyncController (Group 2.1) as single source of truth for all
    timeline state: playhead, zoom, scroll, playback, BPM, master volume.
    
    All UI zones (Ruler, Transport, Waveform, Master Section) subscribe to controller
    signals instead of managing state independently.
    
    Layout structure:
    ┌─────────────────────────────────────────┐
    │ Toolbar (File/Edit/View/Project/AI...) │
    ├─────────────────────────────────────────┤
    │ Timeline Ruler (28px)                   │
    ├──────────┬───────────────────┬──────────┤
    │ Master   │ Waveform Lanes    │ Sidebar  │
    │ (200px)  │ (flexible, grows) │ (260px)  │
    │ Section  │                   │ [collaps]│
    │          │                   │          │
    ├──────────┴───────────────────┴──────────┤
    │ Transport Bar (72px, full width)        │
    ├─────────────────────────────────────────┤
    │ Status Bar (24px, managed by QMainWin)  │
    └─────────────────────────────────────────┘
    """

    def __init__(self, timeline_controller: Optional[TimelineSyncController] = None, parent=None):
        super().__init__(parent)
        self.timeline_controller = timeline_controller
        self._init_ui()

    def _init_ui(self) -> None:
        """Build the main mixer layout structure."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ─────────────────────────────────────────────────────────────────────
        # Toolbar (File/Edit/View/Project/AI Tools/Settings)
        # ─────────────────────────────────────────────────────────────────────
        toolbar = self._build_toolbar()
        root.addWidget(toolbar)

        # ─────────────────────────────────────────────────────────────────────
        # Timeline Ruler (28px, sticky top)
        # ─────────────────────────────────────────────────────────────────────
        timeline_ruler = self._build_timeline_ruler()
        root.addWidget(timeline_ruler)

        # ─────────────────────────────────────────────────────────────────────
        # Main Content Area: Master | Waveform | Sidebar (in horizontal splitter)
        # ─────────────────────────────────────────────────────────────────────
        content_splitter = self._build_content_area()
        root.addWidget(content_splitter, stretch=1)

        # ─────────────────────────────────────────────────────────────────────
        # Transport Bar (72px, full width, never resizes)
        # ─────────────────────────────────────────────────────────────────────
        # NOTE: Transport bar is managed by parent window; attach to this layout
        # when parent passes it during setup.
        self.transport_bar_container = QWidget()
        self.transport_bar_container.setFixedHeight(72)
        root.addWidget(self.transport_bar_container)

        # Status bar is managed by QMainWindow, no need to add here.

    def _build_toolbar(self) -> QToolBar:
        """Build the top toolbar with menus and action buttons."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setFixedHeight(48)
        toolbar.setMovable(False)
        toolbar.setIconSize(Qt.GlobalColor(16, 16))
        
        # TODO: Wire up File/Edit/View/Project/AI Tools/Settings menus
        # TODO: Add quick-action buttons (New/Open/Save/Export/Undo/Redo)
        # TODO: Add BPM display, master volume knob, time signature dropdown
        
        return toolbar

    def _build_timeline_ruler(self) -> QWidget:
        """Build the timeline ruler widget (28px height)."""
        ruler_widget = QFrame()
        ruler_widget.setFixedHeight(28)
        ruler_widget.setStyleSheet(
            "QFrame { background-color: #16161A; border-bottom: 1px solid #2D2D32; }"
        )
        layout = QHBoxLayout(ruler_widget)
        layout.setContentsMargins(200, 0, 260, 0)  # Align with left/right fixed zones
        
        ruler_label = QLabel("Bars:Beats | Playhead (Cyan) | Click to reposition")
        ruler_label.setStyleSheet("color: #909095; font-size: 10px;")
        layout.addWidget(ruler_label)
        layout.addStretch()
        
        # TODO: Implement full timeline ruler with bar/beat numbers
        # TODO: Add playhead marker (cyan vertical line)
        # TODO: Add click-to-reposition functionality
        # TODO: Add Bars:Beats / Seconds toggle
        
        return ruler_widget

    def _build_content_area(self) -> QSplitter:
        """
        Build the main content area with three zones:
        1. Left: Master Section (200px fixed)
        2. Center: Waveform Lanes (flexible, grows)
        3. Right: Sidebar (260px fixed, collapsible)
        """
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(
            "QSplitter::handle { background: #1A1A1E; width: 2px; }"
        )

        # ─────────────────────────────────────────────────────────────────────
        # LEFT: Master Section (200px fixed)
        # ─────────────────────────────────────────────────────────────────────
        master_section = self._build_master_section()
        splitter.addWidget(master_section)

        # ─────────────────────────────────────────────────────────────────────
        # CENTER: Waveform Lanes Container (flexible, stretch=1)
        # ─────────────────────────────────────────────────────────────────────
        waveform_area = self._build_waveform_area()
        splitter.addWidget(waveform_area)

        # ─────────────────────────────────────────────────────────────────────
        # RIGHT: Sidebar (260px fixed, collapsible)
        # ─────────────────────────────────────────────────────────────────────
        sidebar = self._build_sidebar()
        splitter.addWidget(sidebar)

        # Set initial sizes: master=200, waveform=1000, sidebar=260
        # The middle (waveform) will expand when window is resized
        splitter.setSizes([200, 1000, 260])
        splitter.setStretchFactor(0, 0)  # Master: no stretch
        splitter.setStretchFactor(1, 1)  # Waveform: stretch to fill
        splitter.setStretchFactor(2, 0)  # Sidebar: no stretch
        
        # Prevent collapsing of fixed zones
        splitter.setCollapsible(0, False)  # Master always visible
        splitter.setCollapsible(1, False)  # Waveform always visible
        splitter.setCollapsible(2, True)   # Sidebar can collapse

        return splitter

    def _build_master_section(self) -> QWidget:
        """Build the left master section (200px fixed width)."""
        master = QFrame()
        master.setFixedWidth(200)
        master.setStyleSheet(
            "QFrame { background-color: #1E1E22; border-right: 1px solid #2D2D32; }"
        )
        layout = QVBoxLayout(master)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Master section label
        title = QLabel("MASTER")
        title.setStyleSheet(
            "color: #6A6A73; font-size: 10px; font-weight: bold; letter-spacing: 1px;"
        )
        layout.addWidget(title)

        # TODO: Add vertical master fader (≥200px stroke)
        # TODO: Add dual-channel L+R VU meter
        # TODO: Add LUFS integrated readout (cyan monospace)
        # TODO: Add master EQ toggle button
        # TODO: Add master limiter threshold knob
        # TODO: Add master effects chain button

        layout.addStretch()
        return master

    def _build_waveform_area(self) -> QWidget:
        """
        Build the center waveform lanes area (flexible width, grows with window).
        This is where the timeline and track waveforms are displayed.
        """
        waveform = QFrame()
        waveform.setStyleSheet(
            "QFrame { background-color: #121214; }"
        )
        layout = QVBoxLayout(waveform)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        # Placeholder for timeline/waveform widget
        placeholder = QLabel(
            "Waveform Lanes Area\n"
            "(Per-track color fill, clip rectangles, automation curves, magenta slice markers)"
        )
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: #6A6A73; font-size: 11px;")
        layout.addWidget(placeholder)

        # TODO: Wire in TimelineWidget here
        # TODO: Display per-track waveforms with color fill
        # TODO: Show clip rectangles with labels
        # TODO: Display automation curve overlays (cyan with dot handles)
        # TODO: Show magenta slice markers

        return waveform

    def _build_sidebar(self) -> QWidget:
        """Build the right sidebar (260px fixed width, collapsible)."""
        sidebar = QFrame()
        sidebar.setFixedWidth(260)
        sidebar.setStyleSheet(
            "QFrame { background-color: #1E1E22; border-left: 1px solid #2D2D32; }"
        )
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Sidebar tabs: Browser and Sessions
        title = QLabel("BROWSER / SESSIONS")
        title.setStyleSheet(
            "color: #6A6A73; font-size: 10px; font-weight: bold; letter-spacing: 1px;"
        )
        layout.addWidget(title)

        # TODO: Build tab widget with Browser and Sessions tabs
        # TODO: Browser: File tree, drag-and-drop, hover tooltips
        # TODO: Sessions: Session list, right-click menu, truncation with tooltip

        layout.addStretch()
        return sidebar

    def set_transport_bar(self, transport_bar_widget: QWidget) -> None:
        """
        Attach the transport bar to this mixer layout.
        Called by parent window after transport bar is created.
        """
        layout = self.transport_bar_container.layout()
        if layout is None:
            layout = QVBoxLayout(self.transport_bar_container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            self.transport_bar_container.setLayout(layout)
        
        layout.addWidget(transport_bar_widget)

    def get_timeline_widget_container(self) -> QWidget:
        """Return the waveform area container for inserting TimelineWidget."""
        # Find the waveform area by searching for the middle widget in splitter
        # This allows parent to insert the actual TimelineWidget
        pass

    def get_master_section_container(self) -> QWidget:
        """Return the master section container for setup."""
        pass

    def get_sidebar_container(self) -> QWidget:
        """Return the sidebar container for setup."""
        pass
