"""Tabbed window GUI layout helpers for Echo Pro.

This module keeps heavy PySide widget construction out of the main app module
while preserving the same runtime behavior.
"""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QCompleter,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from music_generator import get_music_backend_capability
from app_paths import ACE_MODELS_DIR, MODELS_DIR
from audio_info import get_audio_length_ms
from project_model import Clip
from recording_ui_components import (
    RecordingDiagnosticsWidget,
    TakeListWidget,
    TransportBar,
    TransportPunchLoopWidget,
)
from stems_engine import DEFAULT_DEMUCS_MODEL, DEMUCS_MODEL_OPTIONS
from timeline_widget import TimelineWidget
from voice_store import load_voice_profiles
from app.ui.widgets.collapsible_panel import CollapsiblePanel
from app.ui.widgets.main_mixer_layout import MainMixerLayout
from app.ui.widgets.title_bar import CustomTitleBar

_MASTER_WAVEFORM_PLACEHOLDER = (
    "\u25ac\u25ac\u2580\u2584\u2580\u2588\u2580\u2584\u2580\u25ac  MASTER L  \u25ac\u25ac\u25ac  "
    "MASTER R  \u25ac\u2580\u2584\u2580\u2588\u2580\u2584\u2580\u25ac\u25ac"
)

HELP_GUIDE_HTML = """
<style>
    body  { background:#0d1b2a; color:#dde1e7; font-family:'Segoe UI',Arial,sans-serif; font-size:12px; }
    h2    { color:#e94560; border-bottom:1px solid #0f3460; padding-bottom:4px; margin-top:18px; }
    h3    { color:#64b5f6; margin-top:12px; margin-bottom:4px; }
    p     { margin:4px 0 8px 0; }
    ul    { margin:4px 0 8px 16px; }
    li    { margin-bottom:3px; }
    code  { background:#0f3460; color:#80cbc4; padding:1px 4px; border-radius:3px; }
    kbd   { background:#0f3460; border:1px solid #1a4080; border-radius:3px;
                    padding:1px 5px; font-size:11px; }
    .tip  { background:#0f3460; border-left:3px solid #e94560; padding:6px 10px; margin:8px 0; }
</style>

<h2>Echo Pro - User Guide</h2>
<p>Welcome to <b>Echo Pro</b>, an integrated digital audio workstation for recording,
mixing, voice cloning, and AI-assisted music generation.</p>

<h2>Getting Started</h2>
<h3>First Launch</h3>
<ul>
    <li>On first launch the <b>First Run Setup</b> dialog helps you verify audio drivers and
            install optional AI backends (Demucs for stem separation, music generation models).</li>
    <li>You can rerun setup at any time via <b>Tools -> Install / Update Dependencies</b>.</li>
</ul>
<h3>Creating a Project</h3>
<ul>
    <li>Use the hover-labeled top toolbar icons to create, open, save, or browse projects.</li>
    <li>The <b>+</b> button starts a fresh project.</li>
    <li>The folder button opens a previously saved <code>.json</code> project file.</li>
    <li>The disk button writes the current project to disk, and the search button opens the project browser.</li>
</ul>

<h2>Home Tab</h2>
<p>The Home tab is your main mixing and arrangement workspace.</p>
<h3>Master Stereo Output</h3>
<p>Shows a symbolic stereo waveform for the master bus. A live level meter is available
after playback.</p>
<h3>Project Actions</h3>
<p>Use the hover-labeled icon buttons in this panel to add, rename, delete, reorder, mute,
solo, and arm tracks. Type a name in the text box first, then use the <b>+</b> button to add
the track.</p>
<h3>Audio and Track Tools</h3>
<ul>
    <li><b>Clip import icon button</b> - enter a track index and optional start time, then use the
            hover-labeled folder button to browse for a WAV/MP3/FLAC/OGG file.</li>
    <li><b>Track volume icon button</b> - enter a track index and a dB value (e.g. <code>-6</code>,
            <code>0</code>, <code>+3</code>) and use the hover-labeled speaker button to apply it.</li>
    <li><b>Transport icon buttons</b> - use the hover labels on the play, stop, jump-start, and jump-end buttons to control playback from the current Home-tab playhead.</li>
</ul>
<h3>Stem Splitting (Demucs)</h3>
<ul>
    <li><b>Choose Source Audio</b> - select the full mix you want Demucs to split into stems.</li>
    <li><b>Demucs Model</b> - switch between the balanced 4-stem, fine-tuned 4-stem, and 6-stem presets before starting the split.</li>
    <li><b>Backend and status area</b> - confirms whether Demucs/ffmpeg are ready and keeps recent launch, progress, and completion messages visible.</li>
    <li><b>Run Demucs Split</b> - starts the split for the selected source and adds the resulting stems to the current project.</li>
</ul>
<div class="tip"><b>Tip:</b> All sections on the Home tab can be collapsed with the
<b>▼ / ▶</b> toggle button on their header bar, giving you more room for the waveform
editor and mixer. The waveform and mixer panels are separated by a draggable splitter -
drag it to resize.</div>
<h3>Waveforms (Timeline)</h3>
<ul>
    <li>Each track row shows its clips with a waveform preview.</li>
    <li><b>Left-click</b> a clip to select it; selected clips are highlighted in yellow.</li>
    <li><b>Drag</b> a selected clip to move it along the timeline.</li>
    <li><b>Right-click</b> on an empty part of a track row to add a new clip at that
            position - a file browser will open automatically.</li>
    <li><b>Right-click</b> on an existing clip to select or delete it.</li>
    <li>Press <kbd>Del</kbd> or <kbd>Backspace</kbd> to delete the selected clip.</li>
    <li>Click-drag on an empty area of the currently selected track to define a
            <b>comp range</b> for take comping.</li>
    <li>The red vertical line shows the current playhead position used by the Home-tab transport controls.</li>
</ul>
<h3>Studio Mixer</h3>
<p>Each track has its own vertical channel strip containing:</p>
<ul>
    <li><b>7-band EQ sliders</b> (40 Hz - 16 kHz, +/-12 dB)</li>
    <li><b>Vertical gain fader</b> (-60 dB to +6 dB)</li>
    <li><b>Pan knob</b> (left <-> right)</li>
    <li><b>Punch / Mute / Solo</b> buttons</li>
    <li><b>Stereo L/R level meters</b></li>
</ul>
<p>Scroll horizontally to see all channel strips when you have many tracks.</p>

<h2>Recording Tab</h2>
<h3>Audio Devices</h3>
<ul>
    <li>Select your <b>Input</b> (microphone/interface) and <b>Output</b> (speakers/headphones)
            from the dropdowns.</li>
    <li>Choose a <b>Sample Rate</b> (44.1 kHz, 48 kHz, 88.2 kHz, or 96 kHz).</li>
    <li>Use the hover-labeled refresh and speaker buttons to re-scan or test the selected audio devices.</li>
</ul>
<h3>Recording Controls</h3>
<ul>
    <li>Use the hover-labeled icon buttons to arm tracks, apply BPM, time signature, and count-in settings.</li>
    <li>Select a target track in the <b>Arm track</b> field and use the record transport button to start recording.</li>
    <li>Use the stop transport button to finish. Each recording becomes a <em>take</em>.</li>
    <li>Enable <b>Punch In / Punch Out</b> to record only within a defined time range.</li>
</ul>
<h3>Take Review</h3>
<p>After recording you can listen to each take, mark one as active, or comp multiple takes
together using the <b>Comp Range</b> tool in the timeline. The take review and comp/recovery action rows now use hover-labeled icon buttons for refresh, audition, rating, keeper/mute, and recovery operations.</p>

<h2>Voice FX Tab</h2>
<h3>Voice Manager</h3>
<p>Click <b>Manage Voices</b> to open the Voice Manager dialog:</p>
<ul>
    <li>Enter a <b>profile name</b>.</li>
    <li>Choose a <b>clip duration</b> (longer recordings improve model accuracy).</li>
    <li>Optionally paste a <b>speaking script</b> to read aloud during recording.</li>
    <li>Click <b>Record</b> to capture your voice, or <b>Import Audio File</b> to use an
            existing WAV/MP3.</li>
</ul>
<h3>Applying Voice Effects</h3>
<ul>
    <li>Select a voice profile from the editable <b>Voice Profile</b> combo box (or type
            a custom name).</li>
    <li>Choose the target clip and click <b>Apply Voice Effect</b>.</li>
</ul>

<h2>Music Tab</h2>
<ul>
    <li>Enter a text <b>prompt</b> describing the style or mood of the music.</li>
    <li>Set the desired <b>duration</b> in seconds (10-30 s recommended).</li>
    <li>Click <b>Generate Music</b>. A progress dialog will appear while the AI backend
            creates the clip.</li>
    <li>Use <b>Plan Song Sections</b> to have the AI suggest a multi-section arrangement.</li>
    <li>Generated clips are automatically added to the project for mixing.</li>
</ul>

<h2>Tools Tab</h2>
<ul>
    <li><b>Split Song into Stems</b> - reuses the selected Home-tab source audio when available, or prompts for one before running Demucs.</li>
    <li><b>Install / Update Dependencies</b> - re-runs the installer for AI backends.</li>
</ul>

<h2>Keyboard Shortcuts</h2>
<ul>
    <li><kbd>Del</kbd> / <kbd>Backspace</kbd> - delete selected timeline clip</li>
    <li><b>Left-click drag</b> on a clip - move clip along the timeline</li>
    <li><b>Right-click</b> on timeline - context menu (add clip / delete clip)</li>
    <li><b>▼ / ▶</b> buttons - collapse / expand any panel on the Home tab</li>
</ul>

<h2>Tips &amp; Best Practices</h2>
<ul>
    <li>Record longer voice samples (30 s or more) for better voice cloning quality.</li>
    <li>Use a phonetically rich script in the Voice Manager for more accurate models.</li>
    <li>Keep individual track volumes near 0 dB and adjust the master output instead to
            avoid clipping.</li>
    <li>Use <b>Solo</b> to listen to a single track in isolation while mixing.</li>
    <li>Stem separation works best on full-mix stereo WAV files at 44.1 kHz or 48 kHz.</li>
    <li>Save your project frequently - use <kbd>Ctrl+S</kbd> if your OS forwards it,
            or click the <b>Save</b> button in the toolbar.</li>
</ul>
"""


def build_ui(window) -> None:
    root = QVBoxLayout()
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    # Custom title bar spans the full window width with no outer margins.
    window._title_bar = CustomTitleBar(window)
    root.addWidget(window._title_bar)

    # Wrap all existing content in a padded widget below the title bar.
    content = QWidget()
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(10, 6, 10, 8)
    content_layout.setSpacing(8)

    header = QHBoxLayout()
    header.setSpacing(8)
    window.project_name_label = QLabel("Project: Untitled")
    window.project_name_label.setStyleSheet("font-size:13px; font-weight:bold; color:#E2E2E5;")
    header.addWidget(window.project_name_label)
    header.addStretch()

    for symbol, slot, tip in [
        ("+", window.new_project, "Create new project"),
        ("\U0001f4c2", window.open_project, "Open project"),
        ("\U0001f4be", window.save_project_dialog, "Save project"),
        ("\U0001f50d", window.browse_projects, "Browse projects"),
    ]:
        button = QPushButton(symbol)
        window._configure_symbol_button(button, symbol, tip, width=36)
        button.clicked.connect(slot)
        header.addWidget(button)

    content_layout.addLayout(header)

    window.tabs = QTabWidget()
    # Add Mixer tab as the first/primary tab (item 1.4 - main DAW layout)
    # Wired with TimelineSyncController (Group 2.1) as single source of truth
    window.main_mixer_view = MainMixerLayout(timeline_controller=window.timeline_controller)
    window.mixer_transport_bar = TransportBar()
    window.mixer_transport_bar.record_button.clicked.connect(window.start_recording_session)
    window.mixer_transport_bar.stop_button.clicked.connect(window.stop_recording_session)
    window.mixer_transport_bar.undo_button.clicked.connect(window.undo_last_recording_take)
    window.mixer_transport_bar.redo_button.clicked.connect(window.redo_last_recording_take)
    window.mixer_transport_bar.click_button.clicked.connect(window.toggle_metronome)
    window.mixer_transport_bar.stop_button.setEnabled(False)
    window.main_mixer_view.set_transport_bar(window.mixer_transport_bar)
    window.tabs.addTab(window.main_mixer_view, "Mixer")
    window.tabs.addTab(wrap_scroll(window, build_overview_tab(window)), "Home")
    window.tabs.addTab(wrap_scroll(window, build_recording_tab(window)), "Recording")
    window.tabs.addTab(window._build_demucs_tab(), "Stem Separation")
    window.tabs.addTab(wrap_scroll(window, build_voice_tab(window)), "Voice FX")
    window.tabs.addTab(wrap_scroll(window, window._build_ace_step_tab()), "AI Generation (ACE-Step)")
    window.tabs.addTab(wrap_scroll(window, window._build_mastering_chain_tab()), "Mastering")
    window.tabs.addTab(window._build_midi_mapping_tab(), "MIDI Mapping")
    window.tabs.addTab(window._build_settings_tab(), "Settings")
    window.tabs.addTab(wrap_scroll(window, window._build_tools_tab()), "Tools")
    window.tabs.addTab(window._build_help_tab(), "Help")
    content_layout.addWidget(window.tabs, stretch=1)

    root.addWidget(content, stretch=1)

    container = QWidget()
    container.setLayout(root)
    window.setCentralWidget(container)


def wrap_scroll(_window, content: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setWidget(content)
    return scroll


def build_overview_tab(window) -> QWidget:
    tab = QWidget()
    layout = QVBoxLayout(tab)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(8)

    # Master stereo waveform display
    master_content = QWidget()
    master_layout = QVBoxLayout(master_content)
    master_layout.setContentsMargins(4, 4, 4, 4)
    master_wave_frame = QFrame()
    master_wave_frame.setFrameShape(QFrame.StyledPanel)
    master_wave_frame.setFixedHeight(46)
    master_wave_frame.setStyleSheet(
        "QFrame { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
        "stop:0 #0a1020, stop:0.48 #102848, stop:0.52 #102848, stop:1 #0a1020);"
        " border:1px solid #1a4080; border-radius:4px; }"
    )
    master_wave_lbl = QLabel(_MASTER_WAVEFORM_PLACEHOLDER)
    master_wave_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    master_wave_lbl.setStyleSheet("color:#22ee44; font-family: monospace; font-size:11px; letter-spacing:2px;")
    master_wave_lbl.setToolTip("Master stereo waveform display (live view available after playback)")
    master_layout_inner = QVBoxLayout(master_wave_frame)
    master_layout_inner.addWidget(master_wave_lbl)
    master_layout.addWidget(master_wave_frame)
    layout.addWidget(CollapsiblePanel("Master Stereo Output", master_content))

    project_content = QWidget()
    project_layout = QHBoxLayout(project_content)
    project_layout.setSpacing(8)
    project_layout.setContentsMargins(4, 4, 4, 4)
    window.track_name_input = QLineEdit()
    window.track_name_input.setPlaceholderText("Track name")
    window.track_name_input.setFixedWidth(180)
    window.track_name_input.setToolTip("Enter a name for the new or selected track")
    project_layout.addWidget(window.track_name_input)
    for symbol, slot, tip in [
        ("+", window.add_track, "Add track"),
        ("\u270e", window.rename_selected_track, "Rename selected track"),
        ("\u2715", window.delete_selected_track, "Delete selected track"),
        ("\u2191", lambda: window.move_selected_track(-1), "Move selected track up"),
        ("\u2193", lambda: window.move_selected_track(1), "Move selected track down"),
        ("\U0001f507", window.toggle_selected_track_mute, "Toggle mute on selected track"),
        ("\u25ce", window.toggle_selected_track_solo, "Toggle solo on selected track"),
        ("\u23fa", window.toggle_arm_selected_track, "Arm or disarm selected track for recording"),
    ]:
        button = QPushButton(symbol)
        window._configure_symbol_button(button, symbol, tip, width=36)
        button.clicked.connect(slot)
        project_layout.addWidget(button)
    project_layout.addStretch()
    layout.addWidget(CollapsiblePanel("Project Actions", project_content))

    clip_content = QWidget()
    clip_layout = QGridLayout(clip_content)
    clip_layout.setSpacing(8)
    clip_layout.setContentsMargins(4, 4, 4, 4)
    window.clip_track_index_input = QLineEdit()
    window.clip_track_index_input.setPlaceholderText("Track index")
    window.clip_track_index_input.setFixedWidth(90)
    window.clip_track_index_input.setToolTip("Zero-based index of the track to add the clip to")
    clip_layout.addWidget(QLabel("Clip Track"), 0, 0)
    clip_layout.addWidget(window.clip_track_index_input, 0, 1)
    window.clip_start_sec_input = QLineEdit()
    window.clip_start_sec_input.setPlaceholderText("Start sec")
    window.clip_start_sec_input.setFixedWidth(90)
    window.clip_start_sec_input.setToolTip("Start position of the clip in seconds")
    clip_layout.addWidget(QLabel("Start"), 0, 2)
    clip_layout.addWidget(window.clip_start_sec_input, 0, 3)
    add_clip_btn = QPushButton("Add Clip from File")
    add_clip_btn.setToolTip("Browse for an audio file and add it as a clip")
    add_clip_btn.clicked.connect(window.add_clip_from_file)
    window._configure_symbol_button(add_clip_btn, "\U0001f4c2", "Add clip from file")
    clip_layout.addWidget(add_clip_btn, 0, 4)

    window.volume_track_index_input = QLineEdit()
    window.volume_track_index_input.setPlaceholderText("Track index")
    window.volume_track_index_input.setFixedWidth(90)
    window.volume_track_index_input.setToolTip("Zero-based index of the track to adjust volume for")
    clip_layout.addWidget(QLabel("Volume Track"), 1, 0)
    clip_layout.addWidget(window.volume_track_index_input, 1, 1)
    window.volume_db_input = QLineEdit()
    window.volume_db_input.setPlaceholderText("dB")
    window.volume_db_input.setFixedWidth(90)
    window.volume_db_input.setToolTip("Volume level in decibels (e.g. -6, 0, +3)")
    clip_layout.addWidget(QLabel("Volume dB"), 1, 2)
    clip_layout.addWidget(window.volume_db_input, 1, 3)
    set_vol_btn = QPushButton("Set Track Volume")
    set_vol_btn.setToolTip("Apply the specified volume to the selected track")
    set_vol_btn.clicked.connect(window.set_track_volume)
    window._configure_symbol_button(set_vol_btn, "\U0001f50a", "Set track volume")
    clip_layout.addWidget(set_vol_btn, 1, 4)

    window.play_project_btn = QPushButton("Play")
    window.play_project_btn.setToolTip("Play back all tracks in the current project from the current playhead")
    window.play_project_btn.clicked.connect(window.play_current_project)
    window.stop_project_btn = QPushButton("Stop")
    window.stop_project_btn.setToolTip("Stop project playback")
    window.stop_project_btn.clicked.connect(window.stop_current_project_playback)
    window.stop_project_btn.setEnabled(False)
    window.jump_to_transport_start_btn = QPushButton("Jump to Start")
    window.jump_to_transport_start_btn.setToolTip("Jump to the start of the current selection, selected clip, or project")
    window.jump_to_transport_start_btn.clicked.connect(window.jump_to_transport_start)
    window.jump_to_transport_end_btn = QPushButton("Jump to End")
    window.jump_to_transport_end_btn.setToolTip("Jump to the end of the current selection, selected clip, or project")
    window.jump_to_transport_end_btn.clicked.connect(window.jump_to_transport_end)
    window.playback_position_label = QLabel("Playhead 0.00s")
    window.playback_position_label.setToolTip("Current project playhead position")
    window._configure_symbol_button(window.play_project_btn, "\u25b6", "Play project")
    window._configure_symbol_button(window.stop_project_btn, "\u25a0", "Stop playback")
    window._configure_symbol_button(window.jump_to_transport_start_btn, "\u23ee", "Jump to start")
    window._configure_symbol_button(window.jump_to_transport_end_btn, "\u23ed", "Jump to end")
    clip_layout.addWidget(window.play_project_btn, 2, 1)
    clip_layout.addWidget(window.stop_project_btn, 2, 2)
    clip_layout.addWidget(window.jump_to_transport_start_btn, 2, 3)
    clip_layout.addWidget(window.jump_to_transport_end_btn, 2, 4)
    clip_layout.addWidget(window.playback_position_label, 2, 5)
    layout.addWidget(CollapsiblePanel("Audio and Track Tools", clip_content))

    stems_content = QWidget()
    stems_layout = QGridLayout(stems_content)
    stems_layout.setSpacing(8)
    stems_layout.setContentsMargins(4, 4, 4, 4)

    window.stem_backend_label = QLabel()
    window.stem_backend_label.setWordWrap(True)
    stems_layout.addWidget(window.stem_backend_label, 0, 0, 1, 4)

    stems_layout.addWidget(QLabel("Source Audio"), 1, 0)
    window.stem_source_input = QLineEdit()
    window.stem_source_input.setPlaceholderText("Choose a mix to split with Demucs")
    window.stem_source_input.setReadOnly(True)
    window.stem_source_input.setMinimumWidth(320)
    window.stem_source_input.setToolTip("Selected mix that Demucs will separate into stems")
    stems_layout.addWidget(window.stem_source_input, 1, 1, 1, 2)

    choose_stem_source_btn = QPushButton("Choose Source Audio")
    choose_stem_source_btn.setToolTip("Browse for the song or mix that should be split into stems")
    choose_stem_source_btn.clicked.connect(window.choose_stem_source_audio)
    stems_layout.addWidget(choose_stem_source_btn, 1, 3)

    stems_layout.addWidget(QLabel("Demucs Model"), 2, 0)
    window.stem_model_combo = QComboBox()
    window.stem_model_combo.setToolTip("Choose the Demucs model preset used for the split")
    for model_name, model_label in DEMUCS_MODEL_OPTIONS:
        window.stem_model_combo.addItem(f"{model_name} - {model_label}", model_name)
    default_model_index = window.stem_model_combo.findData(DEFAULT_DEMUCS_MODEL)
    if default_model_index >= 0:
        window.stem_model_combo.setCurrentIndex(default_model_index)
    stems_layout.addWidget(window.stem_model_combo, 2, 1)

    window.stem_output_label = QLabel("Output folder: choose source audio to preview the stem folder.")
    window.stem_output_label.setWordWrap(True)
    stems_layout.addWidget(window.stem_output_label, 2, 2, 1, 2)

    window.stem_split_btn = QPushButton("Run Demucs Split")
    window.stem_split_btn.setToolTip("Start splitting the selected source audio into stems")
    window.stem_split_btn.clicked.connect(window.run_selected_stem_split)
    stems_layout.addWidget(window.stem_split_btn, 3, 0)

    window.stem_status_label = QLabel("Choose source audio to enable Demucs splitting.")
    window.stem_status_label.setWordWrap(True)
    stems_layout.addWidget(window.stem_status_label, 3, 1, 1, 3)

    window.stem_activity_view = QTextEdit()
    window.stem_activity_view.setReadOnly(True)
    window.stem_activity_view.setMaximumHeight(110)
    window.stem_activity_view.setToolTip("Recent Demucs activity, progress, and completion messages")
    stems_layout.addWidget(window.stem_activity_view, 4, 0, 1, 4)

    window._refresh_stem_section_state()
    window._append_stem_activity("Stem splitting is idle.", reset=True)
    layout.addWidget(CollapsiblePanel("Stem Splitting (Demucs)", stems_content))

    tracks_content = QWidget()
    tracks_layout = QVBoxLayout(tracks_content)
    tracks_layout.setContentsMargins(4, 4, 4, 4)
    window.track_list = QListWidget()
    window.track_list.setMaximumHeight(120)
    window.track_list.setToolTip("List of all tracks in the project — click to select")
    window.track_list.currentRowChanged.connect(window.on_track_selection_changed)
    tracks_layout.addWidget(window.track_list)
    layout.addWidget(CollapsiblePanel("Tracks", tracks_content))

    # Waveforms + Mixer in a resizable splitter
    wave_content = QWidget()
    wave_layout = QVBoxLayout(wave_content)
    wave_layout.setContentsMargins(4, 4, 4, 4)
    window.timeline = TimelineWidget(window.current_project)
    window.timeline.on_zoom_request = window._on_timeline_zoom_request
    window.timeline.setMinimumHeight(360)
    window.timeline.on_project_changed = window._on_timeline_project_changed
    window.timeline.on_comp_range_selected = window.on_timeline_comp_range_selected
    window.timeline.on_time_range_changed = window._on_timeline_time_range_changed
    window.timeline.on_automation_points_changed = window._on_timeline_automation_points_changed
    window.timeline.on_clip_fade_changed = window._on_timeline_clip_fade_changed
    window.timeline.on_track_double_click = window._on_timeline_track_double_click
    window.timeline.on_add_clip_at = window._on_timeline_add_clip_at
    window.timeline.on_clip_action = window._handle_timeline_clip_action
    window.timeline.on_track_selected = window._on_timeline_track_selected
    window.timeline_scroll = QScrollArea()
    window.timeline_scroll.setWidgetResizable(False)
    window.timeline_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
    window.timeline_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
    window.timeline_scroll.setMinimumHeight(380)
    window.timeline_scroll.setWidget(window.timeline)
    window._connect_timeline_controller_bridge()

    wave_controls = QHBoxLayout()
    wave_controls.setSpacing(8)

    zoom_out_btn = QPushButton("-")
    zoom_out_btn.setFixedWidth(30)
    zoom_out_btn.setToolTip("Zoom out timeline (Ctrl+-)")
    zoom_out_btn.setShortcut("Ctrl+-")
    zoom_out_btn.clicked.connect(window.zoom_timeline_out)
    wave_controls.addWidget(zoom_out_btn)

    zoom_in_btn = QPushButton("+")
    zoom_in_btn.setFixedWidth(30)
    zoom_in_btn.setToolTip("Zoom in timeline (Ctrl+=)")
    zoom_in_btn.setShortcut("Ctrl+=")
    zoom_in_btn.clicked.connect(window.zoom_timeline_in)
    wave_controls.addWidget(zoom_in_btn)

    zoom_reset_btn = QPushButton("100%")
    zoom_reset_btn.setFixedWidth(56)
    zoom_reset_btn.setToolTip("Reset timeline zoom (Ctrl+0)")
    zoom_reset_btn.setShortcut("Ctrl+0")
    zoom_reset_btn.clicked.connect(window.reset_timeline_zoom)
    wave_controls.addWidget(zoom_reset_btn)

    window.timeline_zoom_label = QLabel("Zoom 100%")
    window.timeline_zoom_label.setStyleSheet("color:#aab4be; font-size:10px;")
    wave_controls.addWidget(window.timeline_zoom_label)
    wave_controls.addStretch()
    wave_layout.addLayout(wave_controls)

    wave_hint = QLabel(
        "Right-click to add clips. Del/Backspace deletes clips. Ctrl+Scroll zooms around the cursor. "
        "Alt+click edits selection start; Shift+click edits selection end. "
        "Select a clip and drag edge fade handles or use right-click Fade Settings..."
    )
    wave_hint.setStyleSheet("color:#aab4be; font-style:italic; font-size:10px;")
    wave_layout.addWidget(wave_hint)
    wave_layout.addWidget(window.timeline_scroll)
    wave_panel = CollapsiblePanel("Waveforms", wave_content)

    # Studio Mixer - horizontal channel strips
    mixer_content = QWidget()
    mixer_layout_outer = QVBoxLayout(mixer_content)
    mixer_layout_outer.setContentsMargins(4, 4, 4, 4)
    mixer_header = QLabel("Vertical channel strips - scroll horizontally to view all channels")
    mixer_header.setStyleSheet("color:#aab4be; font-style:italic;")
    mixer_layout_outer.addWidget(mixer_header)
    window.mixer_scroll = QScrollArea()
    window.mixer_scroll.setWidgetResizable(True)
    window.mixer_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    window.mixer_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
    window.mixer_scroll.setMinimumHeight(400)
    window.mixer_inner = QWidget()
    window.mixer_layout = QHBoxLayout(window.mixer_inner)
    window.mixer_layout.setContentsMargins(4, 4, 4, 4)
    window.mixer_layout.setSpacing(6)
    window.mixer_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
    window.mixer_empty_label = QLabel("Add or load tracks to populate the mixer board.")
    window.mixer_empty_label.setStyleSheet("padding:12px; color:#dde1e7; background:#0d1b2a; border:1px solid #1a4080;")
    window.mixer_layout.addWidget(window.mixer_empty_label)
    window.mixer_layout.addStretch()
    window.mixer_scroll.setWidget(window.mixer_inner)
    mixer_layout_outer.addWidget(window.mixer_scroll)
    mixer_panel = CollapsiblePanel("Studio Mixer", mixer_content)

    splitter = QSplitter(Qt.Orientation.Horizontal)
    splitter.addWidget(mixer_panel)
    splitter.addWidget(wave_panel)
    splitter.setStretchFactor(0, 0)
    splitter.setStretchFactor(1, 1)
    splitter.setSizes([280, 1080])
    layout.addWidget(splitter, stretch=1)

    return tab


def on_timeline_add_clip_at(window, track_index: int, start_ms: int) -> None:
    """Handle a request from the timeline to add a clip at a given position."""
    if track_index < 0 or track_index >= len(window.current_project.tracks):
        QMessageBox.warning(window, "Add Clip", "No valid track at that position.")
        return
    filename, _ = QFileDialog.getOpenFileName(
        window,
        "Choose audio file for clip",
        "",
        "Audio Files (*.wav *.mp3 *.flac *.ogg);;All Files (*)",
    )
    if not filename:
        return
    file_path = Path(filename)
    if not file_path.exists():
        QMessageBox.warning(window, "Input error", "Selected file does not exist.")
        return
    try:
        length_ms = get_audio_length_ms(str(file_path))
        window._mark_project_edit(f"Add clip at {start_ms / 1000.0:.2f}s")
        clip = Clip(
            id=window.next_clip_id,
            track_index=track_index,
            file_path=str(file_path),
            start_ms=start_ms,
            length_ms=length_ms,
        )
        window.current_project.clips.append(clip)
        window.next_clip_id += 1
        window.refresh_timeline()
        window.update_status(f"Added clip on track {track_index} at {start_ms / 1000:.2f}s from {file_path.name}")
    except Exception as error:
        QMessageBox.critical(window, "Error", f"Failed to add clip:\n{error}")


def build_recording_tab(window) -> QWidget:
    tab = QWidget()
    layout = QVBoxLayout(tab)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(8)

    device_group = QGroupBox("Audio Devices and Checks")
    device_layout = QHBoxLayout(device_group)
    device_layout.setSpacing(8)
    window.input_device_combo = QComboBox()
    window.input_device_combo.setToolTip("Select the audio input device for recording")
    window.output_device_combo = QComboBox()
    window.output_device_combo.setToolTip("Select the audio output device for playback")
    device_layout.addWidget(QLabel("Input"))
    device_layout.addWidget(window.input_device_combo)
    device_layout.addWidget(QLabel("Output"))
    device_layout.addWidget(window.output_device_combo)

    device_layout.addWidget(QLabel("Sample Rate"))
    window.sample_rate_combo = QComboBox()
    for sr_label, sr_value in [("44.1 kHz", 44100), ("48 kHz", 48000), ("88.2 kHz", 88200), ("96 kHz", 96000)]:
        window.sample_rate_combo.addItem(sr_label, sr_value)
    window.sample_rate_combo.setToolTip("Recording sample rate (applies to new sessions)")
    window.sample_rate_combo.currentIndexChanged.connect(window._on_sample_rate_changed)
    device_layout.addWidget(window.sample_rate_combo)

    for symbol, slot, tip in [
        ("\u21bb", window.refresh_audio_device_selectors, "Refresh audio devices"),
        ("\U0001f50a", window.test_audio_devices, "Test audio devices"),
    ]:
        button = QPushButton(symbol)
        window._configure_symbol_button(button, symbol, tip)
        button.clicked.connect(slot)
        device_layout.addWidget(button)
    device_layout.addStretch()
    layout.addWidget(device_group)

    transport_group = QGroupBox("Transport")
    transport_layout = QHBoxLayout(transport_group)
    transport_layout.setSpacing(8)
    window.transport_bar = TransportBar()
    window.transport_bar.record_button.clicked.connect(window.start_recording_session)
    window.transport_bar.stop_button.clicked.connect(window.stop_recording_session)
    window.transport_bar.undo_button.clicked.connect(window.undo_last_recording_take)
    window.transport_bar.redo_button.clicked.connect(window.redo_last_recording_take)
    window.transport_bar.click_button.clicked.connect(window.toggle_metronome)
    window.transport_bar.stop_button.setEnabled(False)
    transport_layout.addWidget(window.transport_bar)
    window.record_track_input = QLineEdit()
    window.record_track_input.setPlaceholderText("Arm track")
    window.record_track_input.setFixedWidth(90)
    window.record_track_input.setToolTip("Track index to arm for recording (0-based)")
    transport_layout.addWidget(window.record_track_input)
    for symbol, slot, tip in [
        ("\u23fa", window.arm_recording_track, "Arm selected recording track"),
        ("\u25c9", window.arm_all_recording_tracks, "Arm all tracks for recording"),
        ("\u2298", window.clear_armed_recording_tracks, "Clear all armed recording tracks"),
    ]:
        button = QPushButton(symbol)
        window._configure_symbol_button(button, symbol, tip)
        button.clicked.connect(slot)
        transport_layout.addWidget(button)
    window.record_tempo_input = QLineEdit()
    window.record_tempo_input.setPlaceholderText("BPM")
    window.record_tempo_input.setFixedWidth(80)
    window.record_tempo_input.setToolTip("Recording tempo in beats per minute")
    transport_layout.addWidget(window.record_tempo_input)
    tempo_btn = QPushButton("\u23f1")
    window._configure_symbol_button(tempo_btn, "\u23f1", "Set recording tempo")
    tempo_btn.clicked.connect(window.set_recording_tempo)
    transport_layout.addWidget(tempo_btn)
    window.record_time_sig_input = QLineEdit()
    window.record_time_sig_input.setPlaceholderText("4/4")
    window.record_time_sig_input.setFixedWidth(70)
    window.record_time_sig_input.setToolTip("Time signature for recording (e.g. 4/4, 3/4, 6/8)")
    transport_layout.addWidget(window.record_time_sig_input)
    time_btn = QPushButton("\u2263")
    window._configure_symbol_button(time_btn, "\u2263", "Set recording time signature")
    time_btn.clicked.connect(window.set_recording_time_signature)
    transport_layout.addWidget(time_btn)
    window.record_count_in_input = QLineEdit()
    window.record_count_in_input.setPlaceholderText("Count-in")
    window.record_count_in_input.setFixedWidth(80)
    window.record_count_in_input.setToolTip("Number of count-in bars before recording starts")
    transport_layout.addWidget(window.record_count_in_input)
    count_btn = QPushButton("\u231b")
    window._configure_symbol_button(count_btn, "\u231b", "Set recording count-in")
    count_btn.clicked.connect(window.set_recording_count_in)
    transport_layout.addWidget(count_btn)
    layout.addWidget(transport_group)

    window.punch_loop_widget = TransportPunchLoopWidget()
    window.pre_roll_bar_input = window.punch_loop_widget.pre_roll_bar_input
    window.post_roll_bar_input = window.punch_loop_widget.post_roll_bar_input
    window.punch_mode_combo = window.punch_loop_widget.punch_mode_combo
    window.punch_in_bar_input = window.punch_loop_widget.punch_in_bar_input
    window.punch_out_bar_input = window.punch_loop_widget.punch_out_bar_input
    window.loop_mode_combo = window.punch_loop_widget.loop_mode_combo
    window.loop_start_bar_input = window.punch_loop_widget.loop_start_bar_input
    window.loop_end_bar_input = window.punch_loop_widget.loop_end_bar_input
    window.punch_mode_combo.currentIndexChanged.connect(window.on_punch_mode_changed)
    window.loop_mode_combo.currentIndexChanged.connect(window.on_loop_mode_changed)
    window.punch_loop_widget.set_roll_btn.clicked.connect(window.set_recording_pre_post_roll)
    window.punch_loop_widget.set_punch_btn.clicked.connect(window.set_recording_punch_range)
    window.punch_loop_widget.set_loop_btn.clicked.connect(window.set_recording_loop_range)
    layout.addWidget(window.punch_loop_widget)

    status_group = QGroupBox("Recording Status")
    status_layout = QVBoxLayout(status_group)
    window.recording_status_label = QLabel("Recording: idle")
    status_layout.addWidget(window.recording_status_label)
    window.recording_diagnostics_widget = RecordingDiagnosticsWidget()
    status_layout.addWidget(window.recording_diagnostics_widget)
    layout.addWidget(status_group)

    takes_group = QGroupBox("Take Review")
    takes_layout = QVBoxLayout(takes_group)
    header = QHBoxLayout()
    header.setSpacing(8)
    window.take_track_combo = QComboBox()
    window.take_track_combo.currentIndexChanged.connect(window.refresh_take_review_list)
    window.take_sort_combo = QComboBox()
    window.take_sort_combo.addItem("Newest First", "newest")
    window.take_sort_combo.addItem("Oldest First", "oldest")
    window.take_sort_combo.currentIndexChanged.connect(window.on_take_review_preferences_changed)
    window.take_filter_combo = QComboBox()
    window.take_filter_combo.addItem("All Takes", "all")
    window.take_filter_combo.addItem("Clipped Only", "clipped")
    window.take_filter_combo.addItem("Active Only", "active")
    window.take_filter_combo.currentIndexChanged.connect(window.on_take_review_preferences_changed)
    window.take_view_mode_combo = QComboBox()
    window.take_view_mode_combo.addItem("Expanded", "expanded")
    window.take_view_mode_combo.addItem("Compact", "compact")
    window.take_view_mode_combo.currentIndexChanged.connect(window.on_take_review_preferences_changed)
    window.take_loop_combo = QComboBox()
    window.take_loop_combo.addItem("One-Shot", False)
    window.take_loop_combo.addItem("Loop", True)
    window.take_loop_combo.currentIndexChanged.connect(window.on_take_review_preferences_changed)
    window.hide_inactive_take_clips_btn = QPushButton("\U0001f441")
    window.hide_inactive_take_clips_btn.setCheckable(True)
    window._configure_symbol_button(window.hide_inactive_take_clips_btn, "\U0001f441", "Hide inactive takes")
    window.hide_inactive_take_clips_btn.toggled.connect(window.on_hide_inactive_take_clips_toggled)
    for widget in [QLabel("Track"), window.take_track_combo, window.take_sort_combo, window.take_filter_combo, window.take_view_mode_combo, window.take_loop_combo, window.hide_inactive_take_clips_btn]:
        header.addWidget(widget)
    refresh_takes_btn = QPushButton("\u21bb")
    window._configure_symbol_button(refresh_takes_btn, "\u21bb", "Refresh takes")
    refresh_takes_btn.clicked.connect(window.refresh_take_review_list)
    header.addWidget(refresh_takes_btn)
    header.addStretch()
    takes_layout.addLayout(header)

    window.take_list_widget = TakeListWidget()
    window.take_review_list = window.take_list_widget.list_widget
    window.take_list_widget.on_item_double_clicked(window.audition_selected_take)
    takes_layout.addWidget(window.take_list_widget)

    take_actions = QGridLayout()
    take_actions.setHorizontalSpacing(8)
    take_actions.setVerticalSpacing(8)
    for index, (symbol, slot, tip) in enumerate([
        ("\u2713", window.set_selected_take_active, "Set selected take as active"),
        ("\u25b6", window.audition_selected_take, "Audition selected take"),
        ("\u25b7", window.audition_active_take, "Audition active take"),
        ("\u25a0", window.stop_take_audition, "Stop take audition"),
        ("\u2715", window.delete_selected_take, "Delete selected take"),
        ("\u2605", window.toggle_selected_take_keeper, "Toggle keeper on selected take"),
        ("\U0001f507", window.toggle_selected_take_muted, "Toggle mute on selected take"),
        ("-", lambda: window.rate_selected_take(-1), "Lower selected take rating"),
        ("+", lambda: window.rate_selected_take(1), "Raise selected take rating"),
        ("\U0001f3c6", window.use_best_take_for_selected_track, "Use best take for selected track"),
    ]):
        button = QPushButton(symbol)
        window._configure_symbol_button(button, symbol, tip)
        button.clicked.connect(slot)
        take_actions.addWidget(button, index // 5, index % 5)
    takes_layout.addLayout(take_actions)
    layout.addWidget(takes_group, stretch=1)

    comp_group = QGroupBox("Comping and Recovery")
    comp_layout = QGridLayout(comp_group)
    window.comp_start_sec_input = QLineEdit()
    window.comp_end_sec_input = QLineEdit()
    window.recovery_history_combo = QComboBox()
    comp_layout.addWidget(QLabel("Comp Start"), 0, 0)
    comp_layout.addWidget(window.comp_start_sec_input, 0, 1)
    comp_layout.addWidget(QLabel("Comp End"), 0, 2)
    comp_layout.addWidget(window.comp_end_sec_input, 0, 3)
    button_row = QHBoxLayout()
    button_row.setSpacing(8)
    for symbol, slot, tip in [
        ("\u239a", window.create_comp_region_from_selection, "Create comp region from selection"),
        ("\u21a6", window.assign_selected_take_to_comp_region, "Assign selected take to comp region"),
        ("\u232b", window.clear_comp_region_from_selection, "Clear comp region"),
        ("\u21bb", window.refresh_recovery_history, "Refresh recovery history"),
        ("\u21ba", window.restore_selected_recovery_snapshot, "Restore selected recovery snapshot"),
    ]:
        button = QPushButton(symbol)
        window._configure_symbol_button(button, symbol, tip)
        button.clicked.connect(slot)
        button_row.addWidget(button)
    button_row.addStretch()
    comp_layout.addLayout(button_row, 1, 0, 1, 4)
    comp_layout.addWidget(QLabel("Recovery History"), 2, 0)
    comp_layout.addWidget(window.recovery_history_combo, 2, 1, 1, 3)
    layout.addWidget(comp_group)

    meters_group = QGroupBox("Input Levels")
    meters_layout = QVBoxLayout(meters_group)
    window.meter_container = QVBoxLayout()
    window._build_recording_meters()
    meters_layout.addLayout(window.meter_container)
    layout.addWidget(meters_group)

    return tab


def build_voice_tab(window) -> QWidget:
    tab = QWidget()
    layout = QVBoxLayout(tab)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(8)

    effect_group = QGroupBox("Voice Conversion")
    effect_layout = QGridLayout(effect_group)
    window.voice_track_index_input = QLineEdit()
    window.voice_track_index_input.setToolTip("Zero-based track index containing the clip to process")
    window.voice_clip_id_input = QLineEdit()
    window.voice_clip_id_input.setToolTip("Numeric ID of the clip to apply voice conversion to")

    # Editable ComboBox pre-populated with available voice profiles
    window.voice_profile_combo = QComboBox()
    window.voice_profile_combo.setEditable(True)
    window.voice_profile_combo.setToolTip("Select an existing voice profile or type a name")
    populate_voice_profile_combo(window)
    # Expose as voice_profile_name_input so the base class apply_voice_effect_to_clip works
    window.voice_profile_name_input = window.voice_profile_combo.lineEdit()

    effect_layout.addWidget(QLabel("Track"), 0, 0)
    effect_layout.addWidget(window.voice_track_index_input, 0, 1)
    effect_layout.addWidget(QLabel("Clip ID"), 0, 2)
    effect_layout.addWidget(window.voice_clip_id_input, 0, 3)
    effect_layout.addWidget(QLabel("Voice Profile"), 1, 0)
    effect_layout.addWidget(window.voice_profile_combo, 1, 1, 1, 3)
    apply_btn = QPushButton("Apply Voice Effect")
    apply_btn.setToolTip("Apply the selected voice conversion to the specified clip")
    apply_btn.clicked.connect(window.apply_voice_effect_to_clip)
    manage_btn = QPushButton("Manage Voices")
    manage_btn.setToolTip("Open the Voice Manager to record or import voice profiles")
    manage_btn.clicked.connect(window.open_voice_manager)
    effect_layout.addWidget(apply_btn, 2, 2)
    effect_layout.addWidget(manage_btn, 2, 3)
    layout.addWidget(effect_group)
    return tab


def populate_voice_profile_combo(window) -> None:
    """Refresh the voice profile ComboBox from stored profiles."""
    current_text = window.voice_profile_combo.currentText()
    window.voice_profile_combo.blockSignals(True)
    window.voice_profile_combo.clear()
    for profile in load_voice_profiles():
        window.voice_profile_combo.addItem(profile.name)
    window.voice_profile_combo.blockSignals(False)
    if current_text:
        idx = window.voice_profile_combo.findText(current_text)
        if idx >= 0:
            window.voice_profile_combo.setCurrentIndex(idx)
        else:
            window.voice_profile_combo.setCurrentText(current_text)


def build_ace_step_tab(self) -> QWidget:
    tab = QWidget()
    root = QHBoxLayout(tab)
    root.setContentsMargins(10, 10, 10, 10)
    root.setSpacing(10)

    style_suggestions = [
        "ambient", "cinematic", "dreamy", "dark", "epic", "groovy",
        "lofi", "minimal", "modern", "orchestral", "uplifting", "warm",
    ]
    instrument_suggestions = [
        "piano", "strings", "guitar", "bass", "drums", "synth",
        "pad", "lead", "choir", "brass", "percussion", "vocal",
    ]

    style_tags: list[str] = []
    instrument_tags: list[str] = []

    def clear_layout(layout: QHBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def rebuild_tag_row(layout: QHBoxLayout, values: list[str], remover_factory) -> None:
        clear_layout(layout)
        if not values:
            placeholder = QLabel("No tags yet")
            placeholder.setStyleSheet("color:#8aa0b3; font-style:italic;")
            layout.addWidget(placeholder)
            layout.addStretch()
            return
        for index, value in enumerate(values):
            chip = QFrame()
            chip.setStyleSheet(
                "QFrame { background:#0f3460; border:1px solid #1d537c; border-radius:11px; }"
            )
            chip_layout = QHBoxLayout(chip)
            chip_layout.setContentsMargins(8, 2, 6, 2)
            chip_layout.setSpacing(4)
            label = QLabel(value)
            label.setStyleSheet("color:#dde1e7; font-size:11px;")
            remove_btn = QPushButton("×")
            remove_btn.setFixedSize(18, 18)
            remove_btn.setStyleSheet(
                "QPushButton { border:none; background:transparent; color:#9ecbff; font-weight:700; }"
                "QPushButton:hover { color:#ff9ea8; }"
            )
            remove_btn.clicked.connect(remover_factory(index))
            chip_layout.addWidget(label)
            chip_layout.addWidget(remove_btn)
            layout.addWidget(chip)
        layout.addStretch()

    def configure_chip_completer(input_combo: QComboBox, suggestions: list[str]) -> None:
        completer = QCompleter(suggestions, input_combo)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        input_combo.setCompleter(completer)

        def trigger_popup() -> None:
            line_edit = input_combo.lineEdit()
            if line_edit is None:
                return
            prefix = line_edit.text().strip()
            if not prefix:
                popup = completer.popup()
                if popup is not None:
                    popup.hide()
                return
            completer.setCompletionPrefix(prefix)
            completer.complete()

        line_edit = input_combo.lineEdit()
        if line_edit is not None:
            line_edit.textEdited.connect(lambda _text: trigger_popup())

    def add_style_tag() -> None:
        value = self.ace_style_input.currentText().strip()
        if not value:
            return
        if value.lower() not in {item.lower() for item in style_tags}:
            style_tags.append(value)
            rebuild_tag_row(self.ace_style_chip_layout, style_tags, lambda idx: lambda: remove_style_tag(idx))
        self.ace_style_input.setCurrentText("")

    def add_instrument_tag() -> None:
        value = self.ace_instrument_input.currentText().strip()
        if not value:
            return
        if value.lower() not in {item.lower() for item in instrument_tags}:
            instrument_tags.append(value)
            rebuild_tag_row(self.ace_instrument_chip_layout, instrument_tags, lambda idx: lambda: remove_instrument_tag(idx))
        self.ace_instrument_input.setCurrentText("")

    def remove_style_tag(index: int) -> None:
        if 0 <= index < len(style_tags):
            del style_tags[index]
            rebuild_tag_row(self.ace_style_chip_layout, style_tags, lambda idx: lambda: remove_style_tag(idx))

    def remove_instrument_tag(index: int) -> None:
        if 0 <= index < len(instrument_tags):
            del instrument_tags[index]
            rebuild_tag_row(self.ace_instrument_chip_layout, instrument_tags, lambda idx: lambda: remove_instrument_tag(idx))

    def clear_style_tags() -> None:
        style_tags.clear()
        rebuild_tag_row(self.ace_style_chip_layout, style_tags, lambda idx: lambda: remove_style_tag(idx))

    def clear_instrument_tags() -> None:
        instrument_tags.clear()
        rebuild_tag_row(self.ace_instrument_chip_layout, instrument_tags, lambda idx: lambda: remove_instrument_tag(idx))

    def toggle_instrument_inputs() -> None:
        locked = self.ace_no_specific_instruments_checkbox.isChecked()
        self.ace_instrument_input.setEnabled(not locked)
        clear_instr_btn.setEnabled(not locked)
        if locked:
            clear_instrument_tags()

    def refresh_vram_indicator() -> None:
        capability = get_music_backend_capability()
        if self.ace_force_cpu_checkbox.isChecked():
            self.ace_vram_indicator.setText("Force CPU")
            self.ace_vram_indicator.setStyleSheet("color:#f7bd60; font-weight:600;")
        elif capability["ready"]:
            self.ace_vram_indicator.setText("Ready")
            self.ace_vram_indicator.setStyleSheet("color:#7fe0b5; font-weight:600;")
        else:
            self.ace_vram_indicator.setText("Needs setup")
            self.ace_vram_indicator.setStyleSheet("color:#f36f9f; font-weight:600;")
        self.ace_model_badge_label.setText(capability["reason"] or "Local ACE-Step backend available")

    def refresh_models() -> None:
        discovered_models: list[tuple[str, str, str]] = []
        if ACE_MODELS_DIR.exists():
            for path in sorted(ACE_MODELS_DIR.iterdir(), key=lambda item: item.name.lower()):
                if path.name == "current":
                    continue
                if path.is_dir():
                    discovered_models.append((f"{path.name} [folder]", str(path), "folder"))
                elif path.suffix.lower() in {".ckpt", ".pt", ".safetensors"}:
                    discovered_models.append((f"{path.stem} [file]", str(path), "file"))
        if not discovered_models:
            discovered_models.append(("No installed ACE-Step models found", "", "missing"))

        self.ace_model_combo.blockSignals(True)
        self.ace_model_combo.clear()
        for label, value, kind in discovered_models:
            self.ace_model_combo.addItem(label, {"path": value, "kind": kind})
        self.ace_model_combo.blockSignals(False)

        discovered_loras: list[str] = []
        if ACE_MODELS_DIR.exists():
            for path in sorted(ACE_MODELS_DIR.rglob("*"), key=lambda item: item.name.lower()):
                if path.is_file() and ("lora" in path.name.lower() or path.suffix.lower() in {".safetensors", ".pt"}):
                    discovered_loras.append(str(path))

        self.ace_lora_combo.blockSignals(True)
        self.ace_lora_combo.clear()
        self.ace_lora_combo.addItem("None", "")
        for entry in discovered_loras:
            self.ace_lora_combo.addItem(Path(entry).stem, entry)
        self.ace_lora_combo.blockSignals(False)
        self.ace_lora_completer.model().setStringList([self.ace_lora_combo.itemText(i) for i in range(self.ace_lora_combo.count())])
        refresh_vram_indicator()

    def sync_legacy_generation_fields() -> None:
        self.gen_style.setText(", ".join(style_tags) or self.ace_style_input.currentText().strip() or "ambient")
        self.gen_genre.setText(", ".join(instrument_tags))
        self.gen_mood.setText(self.ace_prompt_input.toPlainText().strip())
        self.gen_lyrics.setText(self.ace_lyrics_input.toPlainText().strip())
        self.gen_duration.setText(str(int(self.ace_duration_spin.value())))
        self.cloud_enabled.setText("no")

    def refresh_ela_state() -> None:
        has_lyrics = bool(self.ace_lyrics_input.toPlainText().strip())
        self.ace_ela_spin.setEnabled(has_lyrics)
        self.ace_ela_spin.setStyleSheet("" if has_lyrics else "color:#8aa0b3; background:#1a1d22;")

    def refresh_generation_estimate() -> None:
        duration_sec = int(self.ace_duration_spin.value())
        steps = int(self.ace_steps_spin.value())
        batch = int(self.ace_batch_spin.value())
        rough_seconds = max(5, int((duration_sec * steps * batch) / 18))
        minutes, seconds = divmod(rough_seconds, 60)
        self.ace_estimated_time_label.setText(f"Est. time: ~{minutes}m {seconds:02d}s")

    def sync_duration_slider(value: int) -> None:
        if self.ace_duration_slider.value() != value:
            self.ace_duration_slider.blockSignals(True)
            self.ace_duration_slider.setValue(value)
            self.ace_duration_slider.blockSignals(False)
        if self.ace_duration_spin.value() != value:
            self.ace_duration_spin.blockSignals(True)
            self.ace_duration_spin.setValue(value)
            self.ace_duration_spin.blockSignals(False)
        refresh_generation_estimate()

    def sync_duration_spin(value: int) -> None:
        if self.ace_duration_spin.value() != value:
            self.ace_duration_spin.blockSignals(True)
            self.ace_duration_spin.setValue(value)
            self.ace_duration_spin.blockSignals(False)
        if self.ace_duration_slider.value() != value:
            self.ace_duration_slider.blockSignals(True)
            self.ace_duration_slider.setValue(value)
            self.ace_duration_slider.blockSignals(False)
        refresh_generation_estimate()

    def sync_reference_strength_slider(value: int) -> None:
        strength = value / 100.0
        if abs(self.ace_audio_reference_strength.value() - strength) > 0.0001:
            self.ace_audio_reference_strength.blockSignals(True)
            self.ace_audio_reference_strength.setValue(strength)
            self.ace_audio_reference_strength.blockSignals(False)

    def sync_reference_strength_spin(value: float) -> None:
        slider_value = int(round(value * 100.0))
        if self.ace_audio_reference_strength_slider.value() != slider_value:
            self.ace_audio_reference_strength_slider.blockSignals(True)
            self.ace_audio_reference_strength_slider.setValue(slider_value)
            self.ace_audio_reference_strength_slider.blockSignals(False)

    def generate_from_ace_step() -> None:
        sync_legacy_generation_fields()
        reference_info = self._ace_step_reference_trim_metadata(validate=True)
        if reference_info is None:
            return
        seed_value = self._ace_step_seed_value()
        self._set_ace_step_processing_state(True)
        self._append_ace_step_log("[info] Starting ACE-Step generation...")
        QApplication.processEvents()
        try:
            generation_payload = {
                "audio_reference": {
                    **reference_info,
                    "influence_strength": float(self.ace_audio_reference_strength.value()) if hasattr(self, "ace_audio_reference_strength") else 0.5,
                }
            }
            result = self.generate_single_clip(seed=seed_value, generation_metadata=generation_payload)
            if result is None:
                self._append_ace_step_log("[error] Generation failed.")
                return
            result_metadata = dict(getattr(result, "metadata", {}) or {})
            output_format_raw = str(result_metadata.get("output_format", "wav") or "wav").strip().lower()
            output_sample_rate = int(result_metadata.get("output_sample_rate", 0) or 0)
            output_format = output_format_raw.upper()
            summary = f"{self.gen_style.text().strip()} / {self.gen_genre.text().strip() or 'reference-free'} / {output_format}"
            self._ace_step_results.append(
                {
                    "label": summary,
                    "audio_path": str(result.audio_path),
                    "duration_ms": int(getattr(result, "duration_ms", 0) or 0),
                    "seed": getattr(result, "used_seed", None),
                    "prompt": self.ace_prompt_input.toPlainText().strip(),
                    "lyrics": self.ace_lyrics_input.toPlainText().strip(),
                    "style_tags": list(style_tags),
                    "instrument_tags": list(instrument_tags),
                    "favorite": False,
                    "loop": False,
                    "volume": 0.7,
                    "output_format": output_format_raw,
                    "output_sample_rate": output_sample_rate,
                    "metadata": result_metadata,
                }
            )
            self._refresh_ace_step_results()
            self._append_ace_step_log("[info] Generation request completed.")
        finally:
            self._set_ace_step_processing_state(False)

    left_panel = QFrame()
    left_panel.setFrameShape(QFrame.Shape.StyledPanel)
    left_panel.setFixedWidth(330)
    left_layout = QVBoxLayout(left_panel)
    left_layout.setContentsMargins(10, 10, 10, 10)
    left_layout.setSpacing(8)

    heading = QLabel("AI Generation (ACE-Step)")
    heading.setStyleSheet("font-size:15px; font-weight:700; color:#dfe9f3;")
    left_layout.addWidget(heading)

    model_group = QGroupBox("Model Selection")
    model_layout = QVBoxLayout(model_group)
    model_row = QHBoxLayout()
    self.ace_model_combo = QComboBox()
    model_row.addWidget(self.ace_model_combo, stretch=1)
    refresh_models_btn = QPushButton("Refresh")
    refresh_models_btn.clicked.connect(refresh_models)
    model_row.addWidget(refresh_models_btn)
    model_layout.addLayout(model_row)
    badge_row = QHBoxLayout()
    self.ace_model_badge_label = QLabel("Scanning model folders...")
    self.ace_model_badge_label.setStyleSheet("color:#8aa0b3; font-size:11px;")
    badge_row.addWidget(self.ace_model_badge_label)
    self.ace_vram_indicator = QLabel("Ready")
    self.ace_vram_indicator.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    badge_row.addWidget(self.ace_vram_indicator, stretch=1)
    model_layout.addLayout(badge_row)
    lora_row = QHBoxLayout()
    self.ace_lora_combo = QComboBox()
    self.ace_lora_combo.setEditable(True)
    self.ace_lora_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    self.ace_lora_completer = QCompleter([], self.ace_lora_combo)
    self.ace_lora_combo.setCompleter(self.ace_lora_completer)
    lora_row.addWidget(self.ace_lora_combo, stretch=1)
    add_lora_btn = QPushButton("+ Add Custom LoRA...")
    add_lora_btn.clicked.connect(self._add_custom_ace_lora)
    lora_row.addWidget(add_lora_btn)
    model_layout.addLayout(lora_row)
    self.ace_force_cpu_checkbox = QCheckBox("Force CPU")
    self.ace_force_cpu_checkbox.toggled.connect(refresh_vram_indicator)
    model_layout.addWidget(self.ace_force_cpu_checkbox)
    left_layout.addWidget(model_group)

    self.ace_output_format_combo = QComboBox()
    self.ace_output_format_combo.addItems(["wav", "flac", "mp3"])
    self.ace_output_sample_rate_combo = QComboBox()
    for label, value in [("44.1 kHz", 44100), ("48 kHz", 48000), ("96 kHz", 96000)]:
        self.ace_output_sample_rate_combo.addItem(label, value)
    self.ace_normalize_checkbox = QCheckBox("Normalize output")
    self.ace_normalize_checkbox.setChecked(True)

    output_group = QGroupBox("Output")
    output_layout = QGridLayout(output_group)
    output_layout.addWidget(QLabel("Format"), 0, 0)
    output_layout.addWidget(self.ace_output_format_combo, 0, 1)
    output_layout.addWidget(QLabel("Sample Rate"), 1, 0)
    output_layout.addWidget(self.ace_output_sample_rate_combo, 1, 1)
    output_layout.addWidget(self.ace_normalize_checkbox, 2, 0, 1, 2)
    left_layout.addWidget(output_group)
    left_layout.addStretch()

    center_panel = QFrame()
    center_panel.setFrameShape(QFrame.Shape.StyledPanel)
    center_layout = QVBoxLayout(center_panel)
    center_layout.setContentsMargins(10, 10, 10, 10)
    center_layout.setSpacing(8)

    tag_group = QGroupBox("Style Tags and Instruments")
    tag_layout = QGridLayout(tag_group)
    self.ace_style_input = QComboBox()
    self.ace_style_input.setEditable(True)
    self.ace_style_input.addItems(style_suggestions)
    configure_chip_completer(self.ace_style_input, style_suggestions)
    style_line_edit = self.ace_style_input.lineEdit()
    if style_line_edit is not None:
        style_line_edit.setPlaceholderText("Type a style tag and press Enter")
        style_line_edit.returnPressed.connect(add_style_tag)
    tag_layout.addWidget(QLabel("Style"), 0, 0)
    tag_layout.addWidget(self.ace_style_input, 0, 1)
    clear_style_btn = QPushButton("Clear All")
    clear_style_btn.clicked.connect(clear_style_tags)
    tag_layout.addWidget(clear_style_btn, 0, 2)

    style_scroll = QScrollArea()
    style_scroll.setWidgetResizable(True)
    style_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    style_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    style_scroll.setMinimumHeight(44)
    style_scroll.setMaximumHeight(54)
    style_host = QWidget()
    self.ace_style_chip_layout = QHBoxLayout(style_host)
    self.ace_style_chip_layout.setContentsMargins(0, 0, 0, 0)
    self.ace_style_chip_layout.setSpacing(6)
    style_scroll.setWidget(style_host)
    tag_layout.addWidget(style_scroll, 1, 0, 1, 3)
    self.ace_style_chip_hint = QLabel("Visible lane capped for roughly 12 chips; scroll to view additional chips.")
    self.ace_style_chip_hint.setStyleSheet("color:#8aa0b3; font-size:10px;")
    tag_layout.addWidget(self.ace_style_chip_hint, 2, 0, 1, 3)

    self.ace_instrument_input = QComboBox()
    self.ace_instrument_input.setEditable(True)
    self.ace_instrument_input.addItems(instrument_suggestions)
    configure_chip_completer(self.ace_instrument_input, instrument_suggestions)
    instrument_line_edit = self.ace_instrument_input.lineEdit()
    if instrument_line_edit is not None:
        instrument_line_edit.setPlaceholderText("Type an instrument tag and press Enter")
        instrument_line_edit.returnPressed.connect(add_instrument_tag)
    tag_layout.addWidget(QLabel("Instruments"), 3, 0)
    tag_layout.addWidget(self.ace_instrument_input, 3, 1)
    clear_instr_btn = QPushButton("Clear All")
    clear_instr_btn.clicked.connect(clear_instrument_tags)
    tag_layout.addWidget(clear_instr_btn, 3, 2)

    instrument_scroll = QScrollArea()
    instrument_scroll.setWidgetResizable(True)
    instrument_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    instrument_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    instrument_scroll.setMinimumHeight(44)
    instrument_scroll.setMaximumHeight(54)
    instrument_host = QWidget()
    self.ace_instrument_chip_layout = QHBoxLayout(instrument_host)
    self.ace_instrument_chip_layout.setContentsMargins(0, 0, 0, 0)
    self.ace_instrument_chip_layout.setSpacing(6)
    instrument_scroll.setWidget(instrument_host)
    tag_layout.addWidget(instrument_scroll, 4, 0, 1, 3)
    self.ace_instrument_chip_hint = QLabel("Visible lane capped for roughly 12 chips; scroll to view additional chips.")
    self.ace_instrument_chip_hint.setStyleSheet("color:#8aa0b3; font-size:10px;")
    tag_layout.addWidget(self.ace_instrument_chip_hint, 5, 0, 1, 3)

    self.ace_no_specific_instruments_checkbox = QCheckBox("No specific instruments")
    self.ace_no_specific_instruments_checkbox.toggled.connect(lambda _checked: toggle_instrument_inputs())
    tag_layout.addWidget(self.ace_no_specific_instruments_checkbox, 6, 0, 1, 3)
    center_layout.addWidget(tag_group)

    audio_ref_group = QGroupBox("Audio Reference")
    audio_ref_layout = QGridLayout(audio_ref_group)
    self.ace_audio_reference_source_combo = QComboBox()
    self.ace_audio_reference_source_combo.addItems(["None", "Upload", "Active Track", "Last Demucs Stem"])
    audio_ref_layout.addWidget(QLabel("Source"), 0, 0)
    audio_ref_layout.addWidget(self.ace_audio_reference_source_combo, 0, 1)
    self.ace_audio_reference_source_combo.currentIndexChanged.connect(self._refresh_ace_audio_reference_preview)
    self.ace_audio_reference_browse_btn = QPushButton("Browse...")
    self.ace_audio_reference_browse_btn.clicked.connect(self._choose_ace_audio_reference_upload)
    audio_ref_layout.addWidget(self.ace_audio_reference_browse_btn, 0, 2)
    self.ace_audio_reference_thumbnail = QLabel("No audio reference selected")
    self.ace_audio_reference_thumbnail.setMinimumHeight(54)
    self.ace_audio_reference_thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.ace_audio_reference_thumbnail.setStyleSheet("border:1px dashed #45607c; color:#8aa0b3; padding:6px;")
    audio_ref_layout.addWidget(self.ace_audio_reference_thumbnail, 1, 0, 1, 2)
    self.ace_audio_reference_strength = QDoubleSpinBox()
    self.ace_audio_reference_strength.setRange(0.0, 1.0)
    self.ace_audio_reference_strength.setSingleStep(0.05)
    self.ace_audio_reference_strength.setValue(0.5)
    audio_ref_layout.addWidget(QLabel("Influence"), 2, 0)
    audio_ref_layout.addWidget(self.ace_audio_reference_strength, 2, 1)
    self.ace_audio_reference_strength_slider = QSlider(Qt.Orientation.Horizontal)
    self.ace_audio_reference_strength_slider.setRange(0, 100)
    self.ace_audio_reference_strength_slider.setValue(50)
    self.ace_audio_reference_strength_slider.valueChanged.connect(sync_reference_strength_slider)
    self.ace_audio_reference_strength.valueChanged.connect(sync_reference_strength_spin)
    audio_ref_layout.addWidget(self.ace_audio_reference_strength_slider, 2, 2)
    self.ace_audio_reference_start = QLineEdit("0.0")
    self.ace_audio_reference_end = QLineEdit("0.0")
    audio_ref_layout.addWidget(QLabel("Start"), 3, 0)
    audio_ref_layout.addWidget(self.ace_audio_reference_start, 3, 1)
    audio_ref_layout.addWidget(QLabel("End"), 4, 0)
    audio_ref_layout.addWidget(self.ace_audio_reference_end, 4, 1)
    self.ace_audio_reference_start.textChanged.connect(lambda _text: self._refresh_ace_audio_reference_preview())
    self.ace_audio_reference_end.textChanged.connect(lambda _text: self._refresh_ace_audio_reference_preview())
    center_layout.addWidget(audio_ref_group)

    generation_group = QGroupBox("Generation Settings")
    generation_layout = QGridLayout(generation_group)
    self.ace_duration_spin = QSpinBox(); self.ace_duration_spin.setRange(5, 300); self.ace_duration_spin.setValue(30)
    self.ace_duration_slider = QSlider(Qt.Orientation.Horizontal)
    self.ace_duration_slider.setRange(5, 300)
    self.ace_duration_slider.setValue(30)
    self.ace_duration_slider.valueChanged.connect(sync_duration_slider)
    self.ace_duration_spin.valueChanged.connect(sync_duration_spin)
    self.ace_steps_spin = QSpinBox(); self.ace_steps_spin.setRange(10, 150); self.ace_steps_spin.setValue(40)
    self.ace_cfg_spin = QDoubleSpinBox(); self.ace_cfg_spin.setRange(1.0, 20.0); self.ace_cfg_spin.setSingleStep(0.1); self.ace_cfg_spin.setValue(7.5)
    self.ace_seed_input = QLineEdit(); self.ace_seed_input.setPlaceholderText("Random")
    self.ace_randomize_seed_btn = QPushButton("🎲")
    self.ace_randomize_seed_btn.clicked.connect(lambda: self._ace_step_randomize_seed())
    self.ace_lock_seed_checkbox = QCheckBox("Lock seed")
    self.ace_scheduler_combo = QComboBox(); self.ace_scheduler_combo.addItems(["Euler", "Euler Ancestral", "DPM++ 2M", "DPM++ SDE", "DDIM", "PNDM"])
    self.ace_erg_spin = QDoubleSpinBox(); self.ace_erg_spin.setRange(0.0, 2.0); self.ace_erg_spin.setSingleStep(0.1)
    self.ace_ela_spin = QDoubleSpinBox(); self.ace_ela_spin.setRange(0.0, 2.0); self.ace_ela_spin.setSingleStep(0.1)
    self.ace_batch_spin = QSpinBox(); self.ace_batch_spin.setRange(1, 8); self.ace_batch_spin.setValue(1)
    self.ace_estimated_time_label = QLabel("Est. time: ~0m 00s")
    self.ace_estimated_time_label.setStyleSheet("color:#8aa0b3; font-size:11px;")
    generation_layout.addWidget(QLabel("Duration (s)"), 0, 0); generation_layout.addWidget(self.ace_duration_spin, 0, 1)
    generation_layout.addWidget(QLabel("Steps"), 0, 2); generation_layout.addWidget(self.ace_steps_spin, 0, 3)
    generation_layout.addWidget(self.ace_duration_slider, 1, 0, 1, 6)
    generation_layout.addWidget(QLabel("CFG"), 2, 0); generation_layout.addWidget(self.ace_cfg_spin, 2, 1)
    generation_layout.addWidget(QLabel("Seed"), 2, 2); generation_layout.addWidget(self.ace_seed_input, 2, 3); generation_layout.addWidget(self.ace_randomize_seed_btn, 2, 4); generation_layout.addWidget(self.ace_lock_seed_checkbox, 2, 5)
    generation_layout.addWidget(QLabel("Scheduler"), 3, 0); generation_layout.addWidget(self.ace_scheduler_combo, 3, 1)
    generation_layout.addWidget(QLabel("ERG"), 3, 2); generation_layout.addWidget(self.ace_erg_spin, 3, 3)
    generation_layout.addWidget(QLabel("ELA"), 3, 4); generation_layout.addWidget(self.ace_ela_spin, 3, 5)
    generation_layout.addWidget(QLabel("Batch"), 4, 0); generation_layout.addWidget(self.ace_batch_spin, 4, 1)
    generation_layout.addWidget(QLabel("Output"), 4, 2); generation_layout.addWidget(self.ace_output_format_combo, 4, 3)
    generation_layout.addWidget(self.ace_estimated_time_label, 4, 4, 1, 2)
    self.ace_duration_spin.valueChanged.connect(lambda: refresh_generation_estimate())
    self.ace_steps_spin.valueChanged.connect(lambda: refresh_generation_estimate())
    self.ace_batch_spin.valueChanged.connect(lambda: refresh_generation_estimate())
    center_layout.addWidget(generation_group)

    prompt_group = QGroupBox("Prompt Area")
    prompt_layout = QVBoxLayout(prompt_group)
    self.ace_prompt_input = QTextEdit()
    self.ace_prompt_input.setPlaceholderText("Describe the track, mood, arrangement, and production direction...")
    self.ace_prompt_input.setMinimumHeight(120)
    prompt_layout.addWidget(self.ace_prompt_input)
    self.ace_prompt_input.textChanged.connect(refresh_generation_estimate)
    negative_content = QWidget(); negative_layout = QVBoxLayout(negative_content); negative_layout.setContentsMargins(4, 4, 4, 4)
    self.ace_negative_prompt_input = QTextEdit(); self.ace_negative_prompt_input.setPlaceholderText("Optional negative prompt..."); self.ace_negative_prompt_input.setMinimumHeight(72)
    negative_layout.addWidget(self.ace_negative_prompt_input)
    prompt_layout.addWidget(CollapsiblePanel("Negative Prompt", negative_content, collapsed=True))
    lyrics_content = QWidget(); lyrics_layout = QVBoxLayout(lyrics_content); lyrics_layout.setContentsMargins(4, 4, 4, 4)
    self.ace_lyrics_input = QTextEdit(); self.ace_lyrics_input.setPlaceholderText("Optional lyrics or line-numbered lyric notes..."); self.ace_lyrics_input.setMinimumHeight(100)
    lyrics_layout.addWidget(self.ace_lyrics_input)
    self.ace_lyrics_input.textChanged.connect(lambda: (refresh_ela_state(), refresh_generation_estimate()))
    prompt_layout.addWidget(CollapsiblePanel("Lyrics", lyrics_content, collapsed=True))
    self.ace_generate_btn = QPushButton("Generate")
    self.ace_generate_btn.clicked.connect(generate_from_ace_step)
    prompt_layout.addWidget(self.ace_generate_btn)
    center_layout.addWidget(prompt_group)

    log_group = QGroupBox("Activity Log")
    log_layout = QVBoxLayout(log_group)
    log_toolbar = QHBoxLayout()
    self.ace_activity_state_label = QLabel("Idle")
    self.ace_activity_state_label.setStyleSheet("color:#8aa0b3; font-weight:600;")
    log_toolbar.addWidget(self.ace_activity_state_label)
    log_toolbar.addStretch()
    copy_log_btn = QPushButton("Copy")
    copy_log_btn.clicked.connect(self._copy_ace_step_log)
    log_toolbar.addWidget(copy_log_btn)
    save_log_btn = QPushButton("Save")
    save_log_btn.clicked.connect(self._save_ace_step_log)
    log_toolbar.addWidget(save_log_btn)
    clear_log_btn = QPushButton("Clear")
    clear_log_btn.clicked.connect(self._clear_ace_step_log)
    log_toolbar.addWidget(clear_log_btn)
    log_layout.addLayout(log_toolbar)
    self.ace_activity_log = QTextEdit()
    self.ace_activity_log.setReadOnly(True)
    self.ace_activity_log.setMinimumHeight(110)
    self.ace_activity_log.setStyleSheet("font-family:Consolas, monospace; font-size:11px;")
    log_layout.addWidget(self.ace_activity_log)
    center_layout.addWidget(log_group)
    center_layout.addStretch()

    right_panel = QFrame()
    right_panel.setFrameShape(QFrame.Shape.StyledPanel)
    right_panel.setFixedWidth(320)
    right_layout = QVBoxLayout(right_panel)
    right_layout.setContentsMargins(10, 10, 10, 10)
    right_layout.setSpacing(8)

    results_group = QGroupBox("Results")
    results_layout = QVBoxLayout(results_group)
    self.ace_results_list = QListWidget()
    self.ace_results_list.addItem("Generated results will appear here.")
    results_layout.addWidget(self.ace_results_list)
    right_layout.addWidget(results_group)

    transfer_group = QGroupBox("Transfer")
    transfer_layout = QVBoxLayout(transfer_group)
    self.ace_transfer_to_demucs_btn = QPushButton("Send to Demucs")
    self.ace_transfer_to_demucs_btn.clicked.connect(self._send_ace_step_result_to_demucs)
    transfer_layout.addWidget(self.ace_transfer_to_demucs_btn)
    self.ace_transfer_main_tracks_checkbox = QCheckBox("Send to Main Tracks")
    self.ace_transfer_main_tracks_checkbox.setChecked(True)
    transfer_layout.addWidget(self.ace_transfer_main_tracks_checkbox)
    self.ace_transfer_insert_combo = QComboBox(); self.ace_transfer_insert_combo.addItem("Append at end", "append"); self.ace_transfer_insert_combo.addItem("Insert at top", "top")
    transfer_layout.addWidget(self.ace_transfer_insert_combo)
    self.ace_transfer_auto_color_checkbox = QCheckBox("Auto color-code stems"); self.ace_transfer_auto_color_checkbox.setChecked(True)
    transfer_layout.addWidget(self.ace_transfer_auto_color_checkbox)
    self.ace_transfer_copy_checkbox = QCheckBox("Copy to project folder"); self.ace_transfer_copy_checkbox.setChecked(True)
    transfer_layout.addWidget(self.ace_transfer_copy_checkbox)
    self.ace_transfer_subfolder_input = QLineEdit("generated")
    transfer_layout.addWidget(self.ace_transfer_subfolder_input)
    self.ace_transfer_btn = QPushButton("Transfer")
    self.ace_transfer_btn.clicked.connect(self._transfer_ace_step_result)
    transfer_layout.addWidget(self.ace_transfer_btn)
    self.ace_transfer_insert_combo.currentIndexChanged.connect(lambda _index: self._sync_transfer_options_between_ace_and_stems("ace"))
    self.ace_transfer_auto_color_checkbox.toggled.connect(lambda _checked: self._sync_transfer_options_between_ace_and_stems("ace"))
    self.ace_transfer_copy_checkbox.toggled.connect(lambda _checked: self._sync_transfer_options_between_ace_and_stems("ace"))
    self.ace_transfer_subfolder_input.textChanged.connect(lambda _text: self._sync_transfer_options_between_ace_and_stems("ace"))
    right_layout.addWidget(transfer_group)

    results_actions = QGridLayout()
    for index, label in enumerate(["Play", "Loop", "★", "Regenerate Same", "Regenerate New", "Vary Subtle", "Vary Strong"]):
        button = QPushButton(label)
        if label == "Regenerate Same":
            button.setToolTip("Regenerate using the selected result seed and prompt.")
            button.clicked.connect(lambda _=False: self._ace_step_run_quick_action("same"))
        elif label == "Regenerate New":
            button.setToolTip("Regenerate with a fresh seed and the current prompt.")
            button.clicked.connect(lambda _=False: self._ace_step_run_quick_action("new"))
        elif label == "Vary Subtle":
            button.setToolTip("Regenerate with a lighter prompt variation.")
            button.clicked.connect(lambda _=False: self._ace_step_run_quick_action("subtle"))
        elif label == "Vary Strong":
            button.setToolTip("Regenerate with a stronger prompt variation.")
            button.clicked.connect(lambda _=False: self._ace_step_run_quick_action("strong"))
        elif label == "Play":
            button.setToolTip("Play the selected ACE-Step result.")
            button.clicked.connect(lambda _=False: self._toggle_ace_step_result_playback())
        elif label == "Loop":
            button.setToolTip("Toggle loop for the selected ACE-Step result.")
            button.clicked.connect(lambda _=False: self._toggle_ace_step_result_loop())
        elif label == "★":
            button.setToolTip("Toggle favorite for the selected ACE-Step result.")
            button.clicked.connect(lambda _=False: self._toggle_ace_step_result_favorite())
        else:
            button.setToolTip("Result actions are available per generated card above.")
            button.clicked.connect(lambda _=False, name=label: self.update_status(f"ACE-Step action pending: {name}"))
        results_actions.addWidget(button, index // 2, index % 2)
    right_layout.addLayout(results_actions)
    right_layout.addStretch()

    root.addWidget(left_panel)
    root.addWidget(center_panel, stretch=1)
    root.addWidget(right_panel)

    self.gen_style = QLineEdit()
    self.gen_genre = QLineEdit()
    self.gen_mood = QLineEdit()
    self.gen_lyrics = QLineEdit()
    self.gen_duration = QLineEdit()
    self.cloud_enabled = QLineEdit("no")

    refresh_models()
    rebuild_tag_row(self.ace_style_chip_layout, style_tags, lambda idx: lambda: remove_style_tag(idx))
    rebuild_tag_row(self.ace_instrument_chip_layout, instrument_tags, lambda idx: lambda: remove_instrument_tag(idx))
    self._refresh_ace_audio_reference_preview()
    self._refresh_ace_step_results()
    toggle_instrument_inputs()
    refresh_ela_state()
    refresh_generation_estimate()
    self._set_ace_step_processing_state(False)
    self._append_ace_step_log("ACE-Step workspace ready. Begin with a prompt or tag set.")
    return tab


def build_mastering_chain_tab(self, eq_curve_widget_cls, lufs_history_widget_cls) -> QWidget:
    tab = QWidget()
    root = QVBoxLayout(tab)
    root.setContentsMargins(10, 10, 10, 10)
    root.setSpacing(10)

    header = QHBoxLayout()
    title = QLabel("Mastering Chain")
    title.setStyleSheet("font-size:16px; font-weight:700; color:#dfe9f3;")
    header.addWidget(title)
    header.addStretch()
    self.mastering_target_combo = QComboBox()
    self.mastering_target_combo.addItems(["Spotify -14", "YouTube -16", "EBU R128 -23", "ATSC -24", "Custom"])
    self.mastering_target_combo.currentTextChanged.connect(self._on_mastering_target_changed)
    header.addWidget(QLabel("Target"))
    header.addWidget(self.mastering_target_combo)
    self.mastering_open_fx_btn = QPushButton("Open Master FX")
    self.mastering_open_fx_btn.clicked.connect(self.open_master_effects_chain)
    header.addWidget(self.mastering_open_fx_btn)
    root.addLayout(header)

    chain_scroll = QScrollArea()
    chain_scroll.setWidgetResizable(True)
    chain_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    chain_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    chain_scroll.setMinimumHeight(390)
    chain_host = QWidget()
    chain_layout = QHBoxLayout(chain_host)
    chain_layout.setContentsMargins(2, 2, 2, 2)
    chain_layout.setSpacing(8)

    def make_card(title_text: str, subtitle: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet(
            "QFrame { background:#122133; border:1px solid #27405a; border-radius:10px; }"
        )
        card.setMinimumWidth(220)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(8)
        card_title = QLabel(title_text)
        card_title.setStyleSheet("font-size:13px; font-weight:700; color:#e5edf5;")
        card_layout.addWidget(card_title)
        card_subtitle = QLabel(subtitle)
        card_subtitle.setWordWrap(True)
        card_subtitle.setStyleSheet("color:#8aa0b3; font-size:11px;")
        card_layout.addWidget(card_subtitle)
        return card, card_layout

    def make_bypass_button(block_key: str) -> QPushButton:
        button = QPushButton("Bypass")
        button.setCheckable(True)
        button.setStyleSheet(
            "QPushButton:checked { background:#4b1620; color:#ff9ea8; border:1px solid #c44b63; }"
        )

        def toggle_bypass(checked: bool) -> None:
            state = self._mastering_chain_state()
            state[f"{block_key}_bypassed"] = bool(checked)
            if block_key == "eq":
                self.set_master_eq_enabled(not bool(checked))
            elif block_key == "limiter":
                self.set_master_limiter_threshold_db(int(state.get("limiter_threshold_db", -3)))
                self._save_mastering_chain_state(state)
            else:
                self._save_mastering_chain_state(state)
            self._refresh_mastering_chain_page()

        button.toggled.connect(toggle_bypass)
        return button

    input_card, input_layout = make_card("Input Trim", "Trim the source before the chain enters the master path.")
    self.master_input_trim_slider = QSlider(Qt.Orientation.Horizontal)
    self.master_input_trim_slider.setRange(-24, 24)
    self.master_input_trim_value = QLabel("0 dB")
    self.master_input_trim_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    self.master_input_trim_bypass = make_bypass_button("input_trim")
    self.master_input_trim_slider.valueChanged.connect(lambda value: self._on_mastering_input_trim_changed(int(value)))
    input_layout.addWidget(self.master_input_trim_slider)
    input_row = QHBoxLayout()
    input_row.addWidget(QLabel("Value"))
    input_row.addWidget(self.master_input_trim_value)
    input_layout.addLayout(input_row)
    input_layout.addWidget(self.master_input_trim_bypass)
    chain_layout.addWidget(input_card)
    chain_layout.addWidget(QLabel("→"))

    eq_card, eq_layout = make_card("4-Band Parametric EQ", "Visual curve with four editable control points.")
    self.master_eq_curve = eq_curve_widget_cls()
    eq_layout.addWidget(self.master_eq_curve)
    eq_grid = QGridLayout()
    self.master_eq_low_slider = QSlider(Qt.Orientation.Horizontal)
    self.master_eq_low_mid_slider = QSlider(Qt.Orientation.Horizontal)
    self.master_eq_high_mid_slider = QSlider(Qt.Orientation.Horizontal)
    self.master_eq_high_slider = QSlider(Qt.Orientation.Horizontal)
    for slider in [self.master_eq_low_slider, self.master_eq_low_mid_slider, self.master_eq_high_mid_slider, self.master_eq_high_slider]:
        slider.setRange(-12, 12)
    self.master_eq_low_slider.valueChanged.connect(lambda value: self._on_mastering_eq_band_changed(0, int(value)))
    self.master_eq_low_mid_slider.valueChanged.connect(lambda value: self._on_mastering_eq_band_changed(1, int(value)))
    self.master_eq_high_mid_slider.valueChanged.connect(lambda value: self._on_mastering_eq_band_changed(2, int(value)))
    self.master_eq_high_slider.valueChanged.connect(lambda value: self._on_mastering_eq_band_changed(3, int(value)))
    band_rows = [
        (0, "Low", self.master_eq_low_slider),
        (1, "Low-Mid", self.master_eq_low_mid_slider),
        (2, "High-Mid", self.master_eq_high_mid_slider),
        (3, "High", self.master_eq_high_slider),
    ]
    for row, label_text, slider in band_rows:
        eq_grid.addWidget(QLabel(label_text), row, 0)
        eq_grid.addWidget(slider, row, 1)
    eq_layout.addLayout(eq_grid)
    self.master_eq_bypass = make_bypass_button("eq")
    eq_layout.addWidget(self.master_eq_bypass)
    chain_layout.addWidget(eq_card)
    chain_layout.addWidget(QLabel("→"))

    comp_card, comp_layout = make_card("Compressor", "Threshold, ratio, attack, release, knee, and makeup gain.")
    comp_form = QGridLayout()
    self.master_comp_threshold = QSpinBox(); self.master_comp_threshold.setRange(-24, 0)
    self.master_comp_ratio = QDoubleSpinBox(); self.master_comp_ratio.setRange(1.0, 20.0); self.master_comp_ratio.setSingleStep(0.1)
    self.master_comp_attack = QSpinBox(); self.master_comp_attack.setRange(1, 200)
    self.master_comp_release = QSpinBox(); self.master_comp_release.setRange(10, 1000)
    self.master_comp_knee = QDoubleSpinBox(); self.master_comp_knee.setRange(0.0, 24.0); self.master_comp_knee.setSingleStep(0.5)
    self.master_comp_makeup = QSpinBox(); self.master_comp_makeup.setRange(-12, 12)
    self.master_comp_threshold.valueChanged.connect(lambda value: self._on_mastering_compressor_changed("compressor_threshold_db", int(value)))
    self.master_comp_ratio.valueChanged.connect(lambda value: self._on_mastering_compressor_changed("compressor_ratio", float(value)))
    self.master_comp_attack.valueChanged.connect(lambda value: self._on_mastering_compressor_changed("compressor_attack_ms", int(value)))
    self.master_comp_release.valueChanged.connect(lambda value: self._on_mastering_compressor_changed("compressor_release_ms", int(value)))
    self.master_comp_knee.valueChanged.connect(lambda value: self._on_mastering_compressor_changed("compressor_knee_db", float(value)))
    self.master_comp_makeup.valueChanged.connect(lambda value: self._on_mastering_compressor_changed("compressor_makeup_db", int(value)))
    comp_rows = [
        (0, "Threshold", self.master_comp_threshold),
        (1, "Ratio", self.master_comp_ratio),
        (2, "Attack", self.master_comp_attack),
        (3, "Release", self.master_comp_release),
        (4, "Knee", self.master_comp_knee),
        (5, "Makeup", self.master_comp_makeup),
    ]
    for row, label_text, widget in comp_rows:
        comp_form.addWidget(QLabel(label_text), row, 0)
        comp_form.addWidget(widget, row, 1)
    comp_layout.addLayout(comp_form)
    comp_meter_row = QGridLayout()
    self.master_comp_input_vu = QProgressBar()
    self.master_comp_input_vu.setRange(0, 100)
    self.master_comp_input_vu.setFormat("%p%")
    self.master_comp_gr_vu = QProgressBar()
    self.master_comp_gr_vu.setRange(0, 100)
    self.master_comp_gr_vu.setFormat("%p%")
    self.master_comp_input_vu_label = QLabel("Input: -70.0 LUFS")
    self.master_comp_gr_label = QLabel("GR: 0.0 dB")
    comp_meter_row.addWidget(QLabel("Input VU"), 0, 0)
    comp_meter_row.addWidget(self.master_comp_input_vu, 0, 1)
    comp_meter_row.addWidget(self.master_comp_input_vu_label, 1, 1)
    comp_meter_row.addWidget(QLabel("Gain Reduction"), 2, 0)
    comp_meter_row.addWidget(self.master_comp_gr_vu, 2, 1)
    comp_meter_row.addWidget(self.master_comp_gr_label, 3, 1)
    comp_layout.addLayout(comp_meter_row)
    self.master_comp_bypass = make_bypass_button("compressor")
    comp_layout.addWidget(self.master_comp_bypass)
    chain_layout.addWidget(comp_card)
    chain_layout.addWidget(QLabel("→"))

    widener_card, widener_layout = make_card("Stereo Widener", "Width control from mono to expanded stereo.")
    self.master_widener_slider = QSlider(Qt.Orientation.Horizontal)
    self.master_widener_slider.setRange(0, 200)
    self.master_widener_value = QLabel("100%")
    self.master_widener_slider.valueChanged.connect(lambda value: self._on_mastering_widener_changed(int(value)))
    widener_layout.addWidget(self.master_widener_slider)
    widener_row = QHBoxLayout()
    widener_row.addWidget(QLabel("Width"))
    widener_row.addWidget(self.master_widener_value)
    widener_layout.addLayout(widener_row)
    self.master_widener_bypass = make_bypass_button("widener")
    widener_layout.addWidget(self.master_widener_bypass)
    chain_layout.addWidget(widener_card)
    chain_layout.addWidget(QLabel("→"))

    limiter_card, limiter_layout = make_card("Limiter", "Final ceiling, threshold, and release with live peak readout.")
    self.master_limiter_threshold_slider = QSlider(Qt.Orientation.Horizontal)
    self.master_limiter_threshold_slider.setRange(-24, 0)
    self.master_limiter_ceiling_slider = QSlider(Qt.Orientation.Horizontal)
    self.master_limiter_ceiling_slider.setRange(-12, 0)
    self.master_limiter_release = QSpinBox(); self.master_limiter_release.setRange(10, 500)
    self.master_limiter_threshold_value = QLabel("-3 dB")
    self.master_limiter_ceiling_value = QLabel("-1 dB")
    self.master_limiter_release.valueChanged.connect(lambda value: self._on_mastering_limiter_changed("limiter_release_ms", int(value)))
    self.master_limiter_threshold_slider.valueChanged.connect(lambda value: self._on_mastering_limiter_changed("limiter_threshold_db", int(value)))
    self.master_limiter_ceiling_slider.valueChanged.connect(lambda value: self._on_mastering_limiter_changed("limiter_ceiling_db", int(value)))
    limiter_layout.addWidget(self.master_limiter_threshold_slider)
    limiter_row = QGridLayout()
    limiter_row.addWidget(QLabel("Threshold"), 0, 0)
    limiter_row.addWidget(self.master_limiter_threshold_value, 0, 1)
    limiter_row.addWidget(QLabel("Ceiling"), 1, 0)
    limiter_row.addWidget(self.master_limiter_ceiling_value, 1, 1)
    limiter_row.addWidget(QLabel("Release"), 2, 0)
    limiter_row.addWidget(self.master_limiter_release, 2, 1)
    limiter_layout.addLayout(limiter_row)
    self.master_limiter_clip_label = QLabel("Clip LED: idle")
    self.master_limiter_true_peak_label = QLabel("True peak: -∞ dB")
    limiter_layout.addWidget(self.master_limiter_clip_label)
    limiter_layout.addWidget(self.master_limiter_true_peak_label)
    self.master_limiter_bypass = make_bypass_button("limiter")
    limiter_layout.addWidget(self.master_limiter_bypass)
    chain_layout.addWidget(limiter_card)
    chain_layout.addWidget(QLabel("→"))

    output_card, output_layout = make_card("Output", "Target alignment and current loudness summary.")
    self.master_output_target_label = QLabel("Target: Spotify -14")
    self.master_output_integrated_label = QLabel("Integrated: -70.0 LUFS-I")
    self.master_output_short_term_label = QLabel("Short-term: -70.0 LUFS-S")
    self.master_output_momentary_label = QLabel("Momentary: -70.0 LUFS-M")
    self.master_output_lra_label = QLabel("LU Range: 0.0 LU")
    output_layout.addWidget(self.master_output_target_label)
    output_layout.addWidget(self.master_output_integrated_label)
    output_layout.addWidget(self.master_output_short_term_label)
    output_layout.addWidget(self.master_output_momentary_label)
    output_layout.addWidget(self.master_output_lra_label)
    self.master_output_bypass = make_bypass_button("output")
    output_layout.addWidget(self.master_output_bypass)
    chain_layout.addWidget(output_card)

    chain_scroll.setWidget(chain_host)
    root.addWidget(chain_scroll)

    lufs_group = QGroupBox("LUFS Meter Panel")
    lufs_layout = QVBoxLayout(lufs_group)
    lufs_summary = QGridLayout()
    self.master_lufs_integrated_label = QLabel("-70.0 LUFS-I")
    self.master_lufs_short_term_label = QLabel("-70.0 LUFS-S")
    self.master_lufs_momentary_label = QLabel("-70.0 LUFS-M")
    self.master_lufs_range_label = QLabel("0.0 LU")
    self.master_lufs_true_peak_label = QLabel("-∞ dBTP")
    for label in [
        self.master_lufs_integrated_label,
        self.master_lufs_short_term_label,
        self.master_lufs_momentary_label,
        self.master_lufs_range_label,
        self.master_lufs_true_peak_label,
    ]:
        label.setStyleSheet("color:#00F0FF; font-family:Consolas, monospace; font-size:13px;")
    lufs_summary.addWidget(QLabel("Integrated"), 0, 0)
    lufs_summary.addWidget(self.master_lufs_integrated_label, 0, 1)
    lufs_summary.addWidget(QLabel("Short-term"), 0, 2)
    lufs_summary.addWidget(self.master_lufs_short_term_label, 0, 3)
    lufs_summary.addWidget(QLabel("Momentary"), 1, 0)
    lufs_summary.addWidget(self.master_lufs_momentary_label, 1, 1)
    lufs_summary.addWidget(QLabel("LU Range"), 1, 2)
    lufs_summary.addWidget(self.master_lufs_range_label, 1, 3)
    lufs_summary.addWidget(QLabel("True Peak"), 2, 0)
    lufs_summary.addWidget(self.master_lufs_true_peak_label, 2, 1)
    self.master_lufs_target_value = QLabel("Target: Spotify -14")
    self.master_lufs_target_value.setStyleSheet("color:#f2b84b; font-family:Consolas, monospace;")
    lufs_summary.addWidget(self.master_lufs_target_value, 2, 2, 1, 2)
    lufs_layout.addLayout(lufs_summary)
    self.master_lufs_chart = lufs_history_widget_cls()
    lufs_layout.addWidget(self.master_lufs_chart)
    root.addWidget(lufs_group)

    self._refresh_mastering_chain_page()
    return tab


def build_tools_tab(self) -> QWidget:
    tab = QWidget()
    layout = QVBoxLayout(tab)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(8)

    tools_group = QGroupBox("Project Tools")
    tools_layout = QVBoxLayout(tools_group)
    open_demucs_btn = QPushButton("Open Stem Separation Tab")
    open_demucs_btn.setToolTip("Jump to the full-page Demucs workspace")
    open_demucs_btn.clicked.connect(lambda: self._switch_to_tab("Stem Separation"))
    tools_layout.addWidget(open_demucs_btn)
    open_ace_btn = QPushButton("Open AI Generation Tab")
    open_ace_btn.setToolTip("Jump to the full-page ACE-Step workspace")
    open_ace_btn.clicked.connect(lambda: self._switch_to_tab("AI Generation (ACE-Step)"))
    tools_layout.addWidget(open_ace_btn)
    layout.addWidget(tools_group)

    layout.addStretch()
    return tab


def build_demucs_tab(self, stem_source_drop_zone_cls) -> QWidget:
    tab = QWidget()
    root = QHBoxLayout(tab)
    root.setContentsMargins(10, 10, 10, 10)
    root.setSpacing(10)

    left_panel = QFrame()
    left_panel.setFrameShape(QFrame.Shape.StyledPanel)
    left_panel.setFixedWidth(360)
    left_layout = QVBoxLayout(left_panel)
    left_layout.setContentsMargins(10, 10, 10, 10)
    left_layout.setSpacing(10)

    heading = QLabel("Stem Separation (Demucs)")
    heading.setStyleSheet("font-size:15px; font-weight:700; color:#dfe9f3;")
    left_layout.addWidget(heading)

    self.stem_source_drop_zone = stem_source_drop_zone_cls(self._on_stem_source_dropped, self)
    left_layout.addWidget(self.stem_source_drop_zone)

    source_row = QHBoxLayout()
    self.stem_source_input = QLineEdit()
    self.stem_source_input.setReadOnly(True)
    self.stem_source_input.setPlaceholderText("Drop a file above or choose source audio")
    source_row.addWidget(self.stem_source_input)
    choose_btn = QPushButton("Browse...")
    choose_btn.clicked.connect(self.choose_stem_source_audio)
    source_row.addWidget(choose_btn)
    left_layout.addLayout(source_row)

    model_row = QHBoxLayout()
    model_row.addWidget(QLabel("Separation Model"))
    model_row.addStretch()
    manage_models_btn = QPushButton("Manage Models...")
    manage_models_btn.setFlat(True)
    manage_models_btn.setStyleSheet("color:#79c6ff;")
    manage_models_btn.clicked.connect(self._show_demucs_model_manager_placeholder)
    model_row.addWidget(manage_models_btn)
    left_layout.addLayout(model_row)

    self.stem_model_combo = QComboBox()
    for model_name, model_label in DEMUCS_MODEL_OPTIONS:
        self.stem_model_combo.addItem(f"{model_name} - {model_label}", model_name)
    default_model_index = self.stem_model_combo.findData(DEFAULT_DEMUCS_MODEL)
    if default_model_index >= 0:
        self.stem_model_combo.setCurrentIndex(default_model_index)
    left_layout.addWidget(self.stem_model_combo)

    device_row = QHBoxLayout()
    device_row.addWidget(QLabel("Device"))
    self.stem_device_combo = QComboBox()
    self.stem_device_combo.addItem("Auto-detect", "auto")
    self.stem_device_combo.addItem("CUDA (GPU)", "cuda")
    self.stem_device_combo.addItem("CPU", "cpu")
    self.stem_device_combo.currentIndexChanged.connect(self._refresh_stem_device_indicator)
    device_row.addWidget(self.stem_device_combo, stretch=1)
    self.stem_vram_indicator = QLabel("Auto-detect")
    self.stem_vram_indicator.setToolTip("Device readiness indicator")
    device_row.addWidget(self.stem_vram_indicator)
    left_layout.addLayout(device_row)

    self.stem_force_cpu_checkbox = QCheckBox("Force CPU")
    self.stem_force_cpu_checkbox.toggled.connect(self._refresh_stem_device_indicator)
    left_layout.addWidget(self.stem_force_cpu_checkbox)

    shifts_row = QHBoxLayout()
    shifts_row.addWidget(QLabel("Shifts"))
    self.stem_shifts_spin = QSpinBox()
    self.stem_shifts_spin.setRange(1, 8)
    self.stem_shifts_spin.setValue(2)
    self.stem_shifts_spin.setToolTip("Number of equivariant shifts (quality vs speed)")
    shifts_row.addWidget(self.stem_shifts_spin)
    shifts_row.addWidget(QLabel("Two-stem mode"))
    self.stem_two_stem_combo = QComboBox()
    self.stem_two_stem_combo.addItem("Off", "off")
    self.stem_two_stem_combo.addItem("Vocals", "vocals")
    self.stem_two_stem_combo.addItem("Instrumental", "instrumental")
    shifts_row.addWidget(self.stem_two_stem_combo)
    left_layout.addLayout(shifts_row)

    output_group = QGroupBox("Output Settings")
    output_layout = QGridLayout(output_group)
    output_layout.addWidget(QLabel("Format"), 0, 0)
    self.stem_output_format_combo = QComboBox()
    self.stem_output_format_combo.addItems(["wav", "flac", "mp3"])
    output_layout.addWidget(self.stem_output_format_combo, 0, 1)

    output_layout.addWidget(QLabel("Sample Rate"), 1, 0)
    self.stem_output_sample_rate_combo = QComboBox()
    for label, value in [("44.1 kHz", 44100), ("48 kHz", 48000), ("96 kHz", 96000)]:
        self.stem_output_sample_rate_combo.addItem(label, value)
    output_layout.addWidget(self.stem_output_sample_rate_combo, 1, 1)

    self.stem_normalize_checkbox = QCheckBox("Normalize output")
    self.stem_normalize_checkbox.setChecked(True)
    output_layout.addWidget(self.stem_normalize_checkbox, 2, 0, 1, 2)
    left_layout.addWidget(output_group)

    self.stem_output_label = QLabel("Output folder: choose source audio to preview the stem folder.")
    self.stem_output_label.setWordWrap(True)
    self.stem_output_label.setStyleSheet("color:#8aa0b3; font-size:11px;")
    left_layout.addWidget(self.stem_output_label)

    self.stem_split_btn = QPushButton("Separate")
    self.stem_split_btn.clicked.connect(self.run_selected_stem_split)
    left_layout.addWidget(self.stem_split_btn)

    self.stem_cancel_btn = QPushButton("Cancel")
    self.stem_cancel_btn.setVisible(False)
    self.stem_cancel_btn.setStyleSheet(
        "QPushButton {"
        " background:#5a2121;"
        " color:#ffeaea;"
        " border:1px solid #a85050;"
        " border-radius:6px;"
        " padding:8px 12px;"
        " font-weight:600;"
        "}"
        "QPushButton:hover { background:#6d2727; }"
        "QPushButton:pressed { background:#4a1b1b; }"
    )
    self.stem_cancel_btn.clicked.connect(self.cancel_selected_stem_split)
    left_layout.addWidget(self.stem_cancel_btn)
    left_layout.addStretch()

    center_panel = QFrame()
    center_panel.setFrameShape(QFrame.Shape.StyledPanel)
    center_layout = QVBoxLayout(center_panel)
    center_layout.setContentsMargins(10, 10, 10, 10)
    center_layout.setSpacing(8)

    self.stem_backend_label = QLabel()
    self.stem_backend_label.setWordWrap(True)
    center_layout.addWidget(self.stem_backend_label)

    self.stem_status_label = QLabel("Choose source audio to enable Demucs splitting.")
    self.stem_status_label.setWordWrap(True)
    center_layout.addWidget(self.stem_status_label)

    progress_group = QGroupBox("Progress")
    progress_layout = QVBoxLayout(progress_group)
    progress_layout.setSpacing(6)

    self.stem_progress_state_label = QLabel("Idle")
    self.stem_progress_state_label.setStyleSheet("color:#a9c4da; font-weight:600;")
    progress_layout.addWidget(self.stem_progress_state_label)

    self.stem_overall_progress = QProgressBar()
    self.stem_overall_progress.setRange(0, 100)
    self.stem_overall_progress.setValue(0)
    self.stem_overall_progress.setFormat("%p%")
    progress_layout.addWidget(self.stem_overall_progress)

    time_row = QHBoxLayout()
    self.stem_elapsed_label = QLabel("Elapsed: 0s")
    self.stem_eta_label = QLabel("ETA: --")
    self.stem_elapsed_label.setStyleSheet("color:#8aa0b3;")
    self.stem_eta_label.setStyleSheet("color:#8aa0b3;")
    time_row.addWidget(self.stem_elapsed_label)
    time_row.addStretch()
    time_row.addWidget(self.stem_eta_label)
    progress_layout.addLayout(time_row)

    per_stem_grid = QGridLayout()
    per_stem_grid.setHorizontalSpacing(8)
    per_stem_grid.setVerticalSpacing(5)
    self.stem_per_stem_bars = {}
    for idx, stem_name in enumerate(["vocals", "drums", "bass", "guitar", "piano", "other"]):
        label = QLabel(stem_name.title())
        label.setStyleSheet("color:#b8cad9; font-size:11px;")
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setTextVisible(False)
        per_stem_grid.addWidget(label, idx, 0)
        per_stem_grid.addWidget(bar, idx, 1)
        self.stem_per_stem_bars[stem_name] = bar
    progress_layout.addLayout(per_stem_grid)
    center_layout.addWidget(progress_group)

    log_group = QGroupBox("Activity Log")
    log_layout = QVBoxLayout(log_group)
    log_toolbar = QHBoxLayout()
    log_toolbar.addWidget(QLabel("Filter"))
    self.stem_log_filter_combo = QComboBox()
    self.stem_log_filter_combo.addItem("All", "all")
    self.stem_log_filter_combo.addItem("Info", "info")
    self.stem_log_filter_combo.addItem("Warnings", "warn")
    self.stem_log_filter_combo.addItem("Errors", "error")
    self.stem_log_filter_combo.currentIndexChanged.connect(self._on_stem_log_filter_changed)
    log_toolbar.addWidget(self.stem_log_filter_combo)
    copy_log_btn = QPushButton("Copy")
    copy_log_btn.clicked.connect(self._copy_stem_log)
    log_toolbar.addWidget(copy_log_btn)
    save_log_btn = QPushButton("Save")
    save_log_btn.clicked.connect(self._save_stem_log)
    log_toolbar.addWidget(save_log_btn)
    clear_log_btn = QPushButton("Clear")
    clear_log_btn.clicked.connect(self._clear_stem_log)
    log_toolbar.addWidget(clear_log_btn)
    log_toolbar.addStretch()
    log_layout.addLayout(log_toolbar)

    self.stem_activity_view = QTextEdit()
    self.stem_activity_view.setReadOnly(True)
    self.stem_activity_view.setMinimumHeight(150)
    self.stem_activity_view.setStyleSheet("font-family:Consolas, monospace; font-size:11px;")
    self.stem_activity_view.setToolTip("Recent Demucs activity, progress, and completion messages")
    log_layout.addWidget(self.stem_activity_view)
    center_layout.addWidget(log_group)

    preview_group = QGroupBox("Output Preview")
    preview_layout = QVBoxLayout(preview_group)
    self.stem_preview_rows_layout = QVBoxLayout()
    preview_layout.addLayout(self.stem_preview_rows_layout)
    center_layout.addWidget(preview_group, stretch=1)

    right_panel = QFrame()
    right_panel.setFrameShape(QFrame.Shape.StyledPanel)
    right_panel.setFixedWidth(300)
    right_layout = QVBoxLayout(right_panel)
    right_layout.setContentsMargins(10, 10, 10, 10)
    right_layout.setSpacing(8)
    right_layout.addWidget(QLabel("Transfer Options"))

    send_group = QGroupBox("Send to Main Tracks")
    send_layout = QVBoxLayout(send_group)
    send_mode_row = QHBoxLayout()
    send_mode_row.addWidget(QLabel("Insert Position"))
    self.stem_transfer_insert_combo = QComboBox()
    self.stem_transfer_insert_combo.addItem("Append at end", "append")
    self.stem_transfer_insert_combo.addItem("Insert at top", "top")
    self.stem_transfer_insert_combo.currentIndexChanged.connect(lambda _index: self._sync_transfer_options_between_ace_and_stems("stems"))
    send_mode_row.addWidget(self.stem_transfer_insert_combo)
    send_layout.addLayout(send_mode_row)
    self.stem_transfer_auto_color_checkbox = QCheckBox("Auto color-code stems")
    self.stem_transfer_auto_color_checkbox.setChecked(True)
    self.stem_transfer_auto_color_checkbox.toggled.connect(lambda _checked: self._sync_transfer_options_between_ace_and_stems("stems"))
    send_layout.addWidget(self.stem_transfer_auto_color_checkbox)
    right_layout.addWidget(send_group)

    save_group = QGroupBox("Save to Project Folder")
    save_layout = QVBoxLayout(save_group)
    self.stem_transfer_save_checkbox = QCheckBox("Copy selected stems to project folder")
    self.stem_transfer_save_checkbox.setChecked(True)
    self.stem_transfer_save_checkbox.toggled.connect(lambda _checked: self._sync_transfer_options_between_ace_and_stems("stems"))
    save_layout.addWidget(self.stem_transfer_save_checkbox)
    self.stem_transfer_target_label = QLabel("Project folder: --")
    self.stem_transfer_target_label.setWordWrap(True)
    self.stem_transfer_target_label.setStyleSheet("color:#8aa0b3; font-size:11px;")
    save_layout.addWidget(self.stem_transfer_target_label)
    subfolder_row = QHBoxLayout()
    subfolder_row.addWidget(QLabel("Subfolder"))
    self.stem_transfer_subfolder_input = QLineEdit("stems")
    self.stem_transfer_subfolder_input.textChanged.connect(lambda _text: self._sync_transfer_options_between_ace_and_stems("stems"))
    subfolder_row.addWidget(self.stem_transfer_subfolder_input)
    save_layout.addLayout(subfolder_row)
    right_layout.addWidget(save_group)

    checklist_group = QGroupBox("Stem Outputs")
    checklist_layout = QVBoxLayout(checklist_group)
    self.stem_transfer_checklist = QListWidget()
    self.stem_transfer_checklist.setAlternatingRowColors(True)
    self.stem_transfer_checklist.setMinimumHeight(170)
    checklist_layout.addWidget(self.stem_transfer_checklist)
    right_layout.addWidget(checklist_group)

    self.stem_to_ace_btn = QPushButton("→ Transfer to ACE-Step")
    self.stem_to_ace_btn.clicked.connect(self._send_selected_stem_to_ace_step)
    self.stem_to_ace_btn.setEnabled(False)
    right_layout.addWidget(self.stem_to_ace_btn)

    self.stem_transfer_btn = QPushButton("Transfer")
    self.stem_transfer_btn.setEnabled(False)
    self.stem_transfer_btn.clicked.connect(self._transfer_selected_stems_to_project)
    self.stem_transfer_btn.setStyleSheet(
        "QPushButton {"
        " background:#00d6e6;"
        " color:#041016;"
        " font-weight:700;"
        " border:1px solid #00f0ff;"
        " border-radius:6px;"
        " padding:8px 12px;"
        "}"
        "QPushButton:hover { background:#1ce8f5; }"
        "QPushButton:disabled { background:#2a3038; color:#8e98a6; border-color:#3a4655; }"
    )
    right_layout.addWidget(self.stem_transfer_btn)
    right_layout.addStretch()

    root.addWidget(left_panel)
    root.addWidget(center_panel, stretch=1)
    root.addWidget(right_panel)

    self._refresh_stem_section_state()
    self._sync_transfer_options_between_ace_and_stems("ace")
    self._set_stem_processing_state(False)
    self._reset_stem_progress_ui(state_text="Idle")
    self._populate_stem_transfer_checklist()
    self._refresh_stem_preview_rows()
    self._append_stem_activity("Stem separation workspace ready.", reset=True)

    return tab


def build_help_tab(self) -> QWidget:
    """Build the built-in user's guide tab."""
    tab = QWidget()
    root = QVBoxLayout(tab)
    root.setContentsMargins(10, 10, 10, 10)
    root.setSpacing(8)

    search_row = QHBoxLayout()
    search_lbl = QLabel("Search:")
    search_row.addWidget(search_lbl)
    self._help_search = QLineEdit()
    self._help_search.setPlaceholderText("Type to search the guide…")
    self._help_search.setToolTip("Filter the guide to show only sections matching your search term")
    self._help_search.textChanged.connect(lambda query: filter_help_text(self, query))
    search_row.addWidget(self._help_search, stretch=1)
    clear_btn = QPushButton("Clear")
    clear_btn.setFixedWidth(60)
    clear_btn.setToolTip("Clear the search filter")
    clear_btn.clicked.connect(self._help_search.clear)
    search_row.addWidget(clear_btn)
    root.addLayout(search_row)

    self._help_view = QTextEdit()
    self._help_view.setReadOnly(True)
    self._help_view.setStyleSheet(
        "QTextEdit { background:#0d1b2a; color:#dde1e7; border:1px solid #0f3460; "
        "font-size:12px; line-height:1.4; }"
    )
    self._help_full_html = HELP_GUIDE_HTML
    self._help_view.setHtml(self._help_full_html)
    root.addWidget(self._help_view, stretch=1)
    return tab


def filter_help_text(self, query: str) -> None:
    query = query.strip()
    if not query:
        self._help_view.setHtml(self._help_full_html)
        return
    lower_q = query.lower()
    sections = re.split(r'(?=<h[23])', self._help_full_html)
    matching = [s for s in sections if lower_q in s.lower()]
    if matching:
        self._help_view.setHtml("".join(matching))
    else:
        self._help_view.setHtml(
            f'<p style="color:#e94560;">No sections found matching "<b>{query}</b>". '
            f'Try a different keyword.</p>'
        )


def build_midi_mapping_tab(self) -> QWidget:
    """Build Group 10 MIDI mapping page with device panel, mappings grid, and learn console."""
    tab = QWidget()
    root = QHBoxLayout(tab)
    root.setContentsMargins(8, 8, 8, 8)
    root.setSpacing(10)

    left_panel = QFrame()
    left_panel.setFrameShape(QFrame.Shape.StyledPanel)
    left_panel.setFixedWidth(250)
    left_layout = QVBoxLayout(left_panel)
    left_layout.setContentsMargins(10, 10, 10, 10)
    left_layout.setSpacing(8)
    left_layout.addWidget(QLabel("MIDI Inputs"))
    self.midi_device_list = QListWidget()
    self.midi_device_list.setToolTip("Available MIDI input devices")
    self.midi_device_list.currentRowChanged.connect(self._on_midi_device_selection_changed)
    left_layout.addWidget(self.midi_device_list, stretch=1)

    channel_row = QHBoxLayout()
    channel_row.addWidget(QLabel("Channel"))
    self.midi_channel_combo = QComboBox()
    self.midi_channel_combo.addItem("All", -1)
    for channel in range(1, 17):
        self.midi_channel_combo.addItem(f"{channel}", channel - 1)
    self.midi_channel_combo.currentIndexChanged.connect(self._on_midi_channel_filter_changed)
    channel_row.addWidget(self.midi_channel_combo, stretch=1)
    left_layout.addLayout(channel_row)

    self.midi_device_status_dot = QLabel("●")
    self.midi_device_status_dot.setStyleSheet("color:#f0b55a; font-size:18px;")
    self.midi_device_status_label = QLabel("No MIDI device selected")
    self.midi_device_status_label.setStyleSheet("color:#8aa0b3;")
    status_row = QHBoxLayout()
    status_row.addWidget(self.midi_device_status_dot)
    status_row.addWidget(self.midi_device_status_label, stretch=1)
    left_layout.addLayout(status_row)

    refresh_btn = QPushButton("Refresh MIDI Devices")
    refresh_btn.clicked.connect(self._refresh_midi_devices)
    left_layout.addWidget(refresh_btn)

    center_panel = QFrame()
    center_panel.setFrameShape(QFrame.Shape.StyledPanel)
    center_layout = QVBoxLayout(center_panel)
    center_layout.setContentsMargins(10, 10, 10, 10)
    center_layout.setSpacing(8)
    center_layout.addWidget(QLabel("Mappings"))
    self.midi_mapping_table = QTableWidget(0, 8)
    self.midi_mapping_table.setHorizontalHeaderLabels([
        "Parameter",
        "Current Value",
        "CC",
        "Channel",
        "Min",
        "Max",
        "Curve",
        "Learn",
    ])
    self.midi_mapping_table.verticalHeader().setVisible(False)
    self.midi_mapping_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    self.midi_mapping_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    self.midi_mapping_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    self.midi_mapping_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
    self.midi_mapping_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
    self.midi_mapping_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
    self.midi_mapping_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
    self.midi_mapping_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
    self.midi_mapping_table.itemChanged.connect(self._on_midi_mapping_item_changed)
    center_layout.addWidget(self.midi_mapping_table, stretch=1)

    right_panel = QFrame()
    right_panel.setFrameShape(QFrame.Shape.StyledPanel)
    right_panel.setFixedWidth(320)
    right_layout = QVBoxLayout(right_panel)
    right_layout.setContentsMargins(10, 10, 10, 10)
    right_layout.setSpacing(8)
    right_layout.addWidget(QLabel("MIDI Learn Console"))
    self.midi_learn_banner = QLabel("MIDI Learn Inactive")
    self.midi_learn_banner.setStyleSheet("background:#3a4553; color:#c9d5e2; padding:6px; border-radius:6px; font-weight:600;")
    right_layout.addWidget(self.midi_learn_banner)
    self.midi_learn_toggle_btn = QPushButton("Enable MIDI Learn")
    self.midi_learn_toggle_btn.setCheckable(True)
    self.midi_learn_toggle_btn.toggled.connect(self._toggle_midi_learn_mode)
    right_layout.addWidget(self.midi_learn_toggle_btn)
    self.midi_learn_confirmation_label = QLabel("No mapping captured yet.")
    self.midi_learn_confirmation_label.setWordWrap(True)
    self.midi_learn_confirmation_label.setStyleSheet("color:#8aa0b3;")
    right_layout.addWidget(self.midi_learn_confirmation_label)
    self.midi_console_view = QPlainTextEdit()
    self.midi_console_view.setReadOnly(True)
    self.midi_console_view.setStyleSheet("font-family:Consolas, monospace; font-size:11px;")
    right_layout.addWidget(self.midi_console_view, stretch=1)

    root.addWidget(left_panel)
    root.addWidget(center_panel, stretch=1)
    root.addWidget(right_panel)

    self._initialize_midi_mapping_state()
    self._refresh_midi_mapping_table()
    self._refresh_midi_devices()
    self._start_midi_input_worker()

    return tab


class _ModelDropZone(QFrame):
    """Drag-and-drop zone used by the Settings model-manager tabs."""

    def __init__(self, title: str, on_drop_paths, parent=None):
        super().__init__(parent)
        self._on_drop_paths = on_drop_paths
        self.setAcceptDrops(True)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame { border:2px dashed #2b4d68; border-radius:8px; background:#111d2a; }"
            "QFrame[dragActive='true'] { border-color:#00f0ff; background:#122838; }"
        )
        self.setProperty("dragActive", False)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(4)
        heading = QLabel(title)
        heading.setStyleSheet("color:#dce7ef; font-weight:700;")
        root.addWidget(heading)
        hint = QLabel("Drop model files or folders here to install")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#8aa0b3;")
        root.addWidget(hint)

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            self.setProperty("dragActive", True)
            self.style().unpolish(self)
            self.style().polish(self)
            event.acceptProposedAction()
            return
        event.ignore()

    def dragLeaveEvent(self, event) -> None:  # type: ignore[override]
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        event.accept()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        urls = event.mimeData().urls()
        paths = [Path(url.toLocalFile()) for url in urls if url.isLocalFile()]
        if paths and callable(self._on_drop_paths):
            self._on_drop_paths(paths)
            event.acceptProposedAction()
            return
        event.ignore()


def _build_model_manager_subtab(window, kind: str, title: str) -> QWidget:
    tab = QWidget()
    layout = QVBoxLayout(tab)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(8)

    actions_row = QHBoxLayout()
    add_folder_btn = QPushButton("Add from Folder...")
    add_folder_btn.clicked.connect(lambda: window._settings_add_model_from_folder(kind))
    actions_row.addWidget(add_folder_btn)

    url_input = QLineEdit()
    url_input.setPlaceholderText("https://.../model-file")
    actions_row.addWidget(url_input, stretch=1)
    download_btn = QPushButton("Download")
    download_btn.clicked.connect(lambda: window._settings_download_model_from_url(kind))
    actions_row.addWidget(download_btn)
    layout.addLayout(actions_row)

    progress = QProgressBar()
    progress.setRange(0, 100)
    progress.setValue(0)
    progress.setFormat("Download progress: %p%")
    layout.addWidget(progress)

    table = QTableWidget(0, 7)
    table.setHorizontalHeaderLabels(["Name", "Type/Stems", "File Size", "Date Added", "Set Default", "Remove", "Source"])
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
    table.itemSelectionChanged.connect(lambda: window._settings_on_model_selection_changed(kind))
    layout.addWidget(table, stretch=1)

    drop_zone = _ModelDropZone(
        f"{title} Drop Zone",
        on_drop_paths=lambda dropped: window._settings_install_model_from_paths(kind, dropped),
    )
    drop_zone.setMinimumHeight(76)
    layout.addWidget(drop_zone)

    details = QPlainTextEdit()
    details.setReadOnly(True)
    details.setPlaceholderText("Select a model row to view metadata and usage notes.")
    details.setMaximumHeight(130)
    layout.addWidget(details)

    if not hasattr(window, "_settings_model_tables"):
        window._settings_model_tables = {}
    if not hasattr(window, "_settings_model_url_inputs"):
        window._settings_model_url_inputs = {}
    if not hasattr(window, "_settings_model_progress_bars"):
        window._settings_model_progress_bars = {}
    if not hasattr(window, "_settings_model_details"):
        window._settings_model_details = {}

    window._settings_model_tables[kind] = table
    window._settings_model_url_inputs[kind] = url_input
    window._settings_model_progress_bars[kind] = progress
    window._settings_model_details[kind] = details

    return tab


def build_settings_tab(window) -> QWidget:
    """Build Group 11 Settings page with left-nav sections and functional controls."""
    tab = QWidget()
    root = QHBoxLayout(tab)
    root.setContentsMargins(8, 8, 8, 8)
    root.setSpacing(10)

    nav = QListWidget()
    nav.setFixedWidth(200)
    nav.addItems([
        "Audio Engine",
        "Model Manager",
        "Appearance",
        "Keyboard Shortcuts",
        "Project Defaults",
        "About",
    ])
    root.addWidget(nav)

    stack = QStackedWidget()

    # Audio Engine
    audio_page = QWidget()
    audio_layout = QVBoxLayout(audio_page)
    audio_group = QGroupBox("Audio Engine")
    audio_form = QGridLayout(audio_group)
    window.settings_audio_backend_combo = QComboBox()
    window.settings_audio_backend_combo.addItems(["WASAPI Exclusive", "WASAPI Shared", "ASIO", "JACK/PipeWire"])
    window.settings_audio_input_combo = QComboBox()
    window.settings_audio_output_combo = QComboBox()
    window.settings_audio_sample_rate_combo = QComboBox()
    for rate in [44100, 48000, 96000, 192000]:
        window.settings_audio_sample_rate_combo.addItem(f"{rate} Hz", int(rate))
    window.settings_audio_buffer_combo = QComboBox()
    for buffer_size in [64, 128, 256, 512, 1024]:
        window.settings_audio_buffer_combo.addItem(str(buffer_size), int(buffer_size))
    window.settings_audio_bit_depth_combo = QComboBox()
    for depth in [16, 24, 32]:
        window.settings_audio_bit_depth_combo.addItem(f"{depth}-bit", int(depth))
    window.settings_audio_latency_label = QLabel("Latency: --")
    window.settings_audio_driver_status_label = QLabel("Driver status: Unknown")
    window.settings_audio_driver_status_label.setStyleSheet("color:#8aa0b3;")

    audio_form.addWidget(QLabel("Backend"), 0, 0)
    audio_form.addWidget(window.settings_audio_backend_combo, 0, 1)
    audio_form.addWidget(QLabel("Input Device"), 1, 0)
    audio_form.addWidget(window.settings_audio_input_combo, 1, 1)
    audio_form.addWidget(QLabel("Output Device"), 2, 0)
    audio_form.addWidget(window.settings_audio_output_combo, 2, 1)
    audio_form.addWidget(QLabel("Sample Rate"), 3, 0)
    audio_form.addWidget(window.settings_audio_sample_rate_combo, 3, 1)
    audio_form.addWidget(QLabel("Buffer Size"), 4, 0)
    audio_form.addWidget(window.settings_audio_buffer_combo, 4, 1)
    audio_form.addWidget(QLabel("Bit Depth"), 5, 0)
    audio_form.addWidget(window.settings_audio_bit_depth_combo, 5, 1)
    audio_form.addWidget(window.settings_audio_latency_label, 6, 0, 1, 2)
    audio_form.addWidget(window.settings_audio_driver_status_label, 7, 0, 1, 2)

    controls = QHBoxLayout()
    refresh_btn = QPushButton("Refresh Devices")
    refresh_btn.clicked.connect(window._settings_refresh_audio_devices)
    controls.addWidget(refresh_btn)
    test_btn = QPushButton("Test Tone")
    test_btn.clicked.connect(window._settings_play_test_tone)
    controls.addWidget(test_btn)
    apply_btn = QPushButton("Apply Audio Settings")
    apply_btn.clicked.connect(window._settings_apply_audio_engine)
    controls.addWidget(apply_btn)
    controls.addStretch()
    audio_form.addLayout(controls, 8, 0, 1, 2)

    for combo in [
        window.settings_audio_input_combo,
        window.settings_audio_output_combo,
        window.settings_audio_sample_rate_combo,
        window.settings_audio_buffer_combo,
    ]:
        combo.currentIndexChanged.connect(window._settings_refresh_audio_engine_status)

    audio_layout.addWidget(audio_group)
    audio_layout.addStretch()
    stack.addWidget(audio_page)

    # Model Manager
    model_page = QWidget()
    model_layout = QVBoxLayout(model_page)
    model_tabs = QTabWidget()
    model_tabs.addTab(_build_model_manager_subtab(window, "demucs", "Demucs Models"), "Demucs Models")
    model_tabs.addTab(_build_model_manager_subtab(window, "ace", "ACE-Step Models"), "ACE-Step Models")
    model_layout.addWidget(model_tabs)
    stack.addWidget(model_page)

    # Appearance
    appearance_page = QWidget()
    appearance_layout = QVBoxLayout(appearance_page)
    appearance_group = QGroupBox("Appearance")
    appearance_form = QGridLayout(appearance_group)
    window.settings_theme_combo = QComboBox()
    window.settings_theme_combo.addItems(["Dark Studio", "High Contrast", "Light Prototype"])
    window.settings_accent_input = QLineEdit("#00F0FF")
    window.settings_font_size_combo = QComboBox()
    window.settings_font_size_combo.addItems(["Small", "Medium", "Large"])
    window.settings_waveform_color_mode_combo = QComboBox()
    window.settings_waveform_color_mode_combo.addItems(["Per-track", "Single color"])
    window.settings_animation_speed_combo = QComboBox()
    window.settings_animation_speed_combo.addItems(["Full", "Reduced", "None"])
    appearance_form.addWidget(QLabel("Theme"), 0, 0)
    appearance_form.addWidget(window.settings_theme_combo, 0, 1)
    appearance_form.addWidget(QLabel("Accent Color"), 1, 0)
    appearance_form.addWidget(window.settings_accent_input, 1, 1)
    appearance_form.addWidget(QLabel("Font Size"), 2, 0)
    appearance_form.addWidget(window.settings_font_size_combo, 2, 1)
    appearance_form.addWidget(QLabel("Waveform Color Mode"), 3, 0)
    appearance_form.addWidget(window.settings_waveform_color_mode_combo, 3, 1)
    appearance_form.addWidget(QLabel("Animation Speed"), 4, 0)
    appearance_form.addWidget(window.settings_animation_speed_combo, 4, 1)
    appearance_apply_btn = QPushButton("Apply Appearance")
    appearance_apply_btn.clicked.connect(window._settings_apply_appearance)
    appearance_form.addWidget(appearance_apply_btn, 5, 0, 1, 2)
    appearance_layout.addWidget(appearance_group)
    appearance_layout.addStretch()
    stack.addWidget(appearance_page)

    # Keyboard Shortcuts
    shortcut_page = QWidget()
    shortcut_layout = QVBoxLayout(shortcut_page)
    search_row = QHBoxLayout()
    search_row.addWidget(QLabel("Search"))
    window.settings_shortcut_search_input = QLineEdit()
    window.settings_shortcut_search_input.setPlaceholderText("Filter actions...")
    window.settings_shortcut_search_input.textChanged.connect(window._settings_refresh_shortcuts_table)
    search_row.addWidget(window.settings_shortcut_search_input, stretch=1)
    reset_shortcuts_btn = QPushButton("Reset All to Defaults")
    reset_shortcuts_btn.clicked.connect(window._settings_reset_shortcuts_to_defaults)
    search_row.addWidget(reset_shortcuts_btn)
    shortcut_layout.addLayout(search_row)
    window.settings_shortcuts_table = QTableWidget(0, 2)
    window.settings_shortcuts_table.setHorizontalHeaderLabels(["Action", "Shortcut"])
    window.settings_shortcuts_table.verticalHeader().setVisible(False)
    window.settings_shortcuts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    window.settings_shortcuts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
    window.settings_shortcuts_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    window.settings_shortcuts_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    window.settings_shortcuts_table.itemChanged.connect(window._settings_on_shortcut_item_changed)
    shortcut_layout.addWidget(window.settings_shortcuts_table, stretch=1)
    shortcut_layout.addWidget(QLabel("Edit shortcut cells directly. Changes update settings mapping and can be wired globally in Group 12."))
    stack.addWidget(shortcut_page)

    # Project Defaults
    defaults_page = QWidget()
    defaults_layout = QVBoxLayout(defaults_page)
    defaults_group = QGroupBox("Project Defaults")
    defaults_form = QGridLayout(defaults_group)
    window.settings_default_project_folder_input = QLineEdit()
    browse_default_folder_btn = QPushButton("Browse...")
    browse_default_folder_btn.clicked.connect(window._settings_browse_default_project_folder)
    folder_row = QHBoxLayout()
    folder_row.addWidget(window.settings_default_project_folder_input, stretch=1)
    folder_row.addWidget(browse_default_folder_btn)
    window.settings_default_sample_rate_combo = QComboBox()
    for rate in [44100, 48000, 96000, 192000]:
        window.settings_default_sample_rate_combo.addItem(f"{rate} Hz", int(rate))
    window.settings_default_bpm_spin = QSpinBox()
    window.settings_default_bpm_spin.setRange(30, 300)
    window.settings_default_autosave_interval_spin = QSpinBox()
    window.settings_default_autosave_interval_spin.setRange(0, 120)
    window.settings_default_autosave_interval_spin.setSuffix(" min")
    window.settings_default_autosave_location_input = QLineEdit()
    defaults_form.addWidget(QLabel("Default Project Folder"), 0, 0)
    defaults_form.addLayout(folder_row, 0, 1)
    defaults_form.addWidget(QLabel("Default Sample Rate"), 1, 0)
    defaults_form.addWidget(window.settings_default_sample_rate_combo, 1, 1)
    defaults_form.addWidget(QLabel("Default BPM"), 2, 0)
    defaults_form.addWidget(window.settings_default_bpm_spin, 2, 1)
    defaults_form.addWidget(QLabel("Auto-save Interval"), 3, 0)
    defaults_form.addWidget(window.settings_default_autosave_interval_spin, 3, 1)
    defaults_form.addWidget(QLabel("Auto-save Location"), 4, 0)
    defaults_form.addWidget(window.settings_default_autosave_location_input, 4, 1)
    save_defaults_btn = QPushButton("Save Project Defaults")
    save_defaults_btn.clicked.connect(window._settings_save_project_defaults)
    defaults_form.addWidget(save_defaults_btn, 5, 0, 1, 2)
    defaults_layout.addWidget(defaults_group)
    defaults_layout.addStretch()
    stack.addWidget(defaults_page)

    # About
    about_page = QWidget()
    about_layout = QVBoxLayout(about_page)
    about_text = QTextEdit()
    about_text.setReadOnly(True)
    about_text.setHtml(
        "<h2>EchoApp / Echo Pro</h2>"
        "<p><b>Version:</b> 1.0.1</p>"
        "<p><b>Build Date:</b> 03 August 2026</p>"
        "<p><b>Repository:</b> github.com/misears/EchoApp</p>"
        "<p><b>License:</b> See repository license information.</p>"
    )
    about_layout.addWidget(about_text)
    stack.addWidget(about_page)

    root.addWidget(stack, stretch=1)

    window.settings_nav_list = nav
    window.settings_stack = stack
    nav.currentRowChanged.connect(stack.setCurrentIndex)
    nav.setCurrentRow(0)

    window._initialize_settings_state()
    window._refresh_settings_page()

    return tab
