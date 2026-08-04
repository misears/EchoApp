# ── COLOR TOKENS (UX §1.7) ──────────────────────────────────────────────────
# Depth layers
C_L0 = "#121214"       # window base / absolute floor
C_L1 = "#16161A"       # panel interior surfaces
C_L2 = "#1E1E22"       # raised panels, card backgrounds
C_L3 = "#2D2D32"       # controls, buttons, knobs / all borders

# Semantic accent colors
C_CYAN   = "#00F0FF"   # DAW Cyan — accent / active state
C_RED    = "#FF3366"   # Record Red — record armed
C_AMBER  = "#FFB830"   # Warning Amber — loop, warnings
C_GREEN  = "#39D353"   # Success Green — confirmation

# Text hierarchy
C_TEXT   = "#E2E2E5"   # primary text
C_MUTED  = "#909095"   # labels
C_DIM    = "#6A6A73"   # section titles

# Derived bevel / shadow tokens (not in §1.7 palette; required for 3D bevel)
C_EDGE_LIGHT   = "#3A3A42"   # button / panel highlight edge
C_EDGE_DARK    = "#090910"   # button / panel shadow edge
C_HANDLE_LIGHT = "#4A4A52"   # slider handle highlight edge
C_HANDLE_DARK  = "#0A0A0C"   # slider handle shadow edge
C_PANEL_TOP    = "#2A2A30"   # raised-panel top / left highlight
C_SHADOW       = "#0D0D10"   # deep inset shadow
C_INPUT_BG     = "#0E0E10"   # recessed input / status-bar background
C_BTN_TOP      = "#252528"   # button gradient resting top stop
C_BTN_BOT      = "#1A1A1E"   # button gradient resting bottom stop
C_TAB_IDLE     = "#1A1A1E"   # tab background (not selected)
C_TAB_BORDER   = "#232328"   # tab border

# ── TYPOGRAPHY TOKENS (UX §1.5) ─────────────────────────────────────────────
FONT_UI    = "'Segoe UI', 'Helvetica Neue', Arial, sans-serif"
FONT_MONO  = "Consolas"
FONT_LABEL = "11px"    # labels / general UI
FONT_VALUE = "12px"    # active values (bold)
FONT_SECT  = "10px"    # section titles (uppercase in code, not QSS)
FONT_MONO_SIZE = "12px"  # numeric readouts (BPM, ms, dB)

# ── NOTE: QSS limitations ────────────────────────────────────────────────────
# box-shadow, transition, and text-transform are unsupported in Qt QSS.
# Glow states use border-color. Animated states (record pulse, transport active)
# are driven from Python via dynamic setStyleSheet/setProperty calls.

DARK_STYLE = f"""
/* ── BASE SURFACES ─────────────────────────────────────────────────────── */
QMainWindow, QDialog {{
    background-color: {C_L0};
    color: {C_TEXT};
    font-family: {FONT_UI};
    font-size: {FONT_LABEL};
}}

QWidget {{
    background-color: {C_L1};
    color: {C_TEXT};
    font-family: {FONT_UI};
    font-size: {FONT_LABEL};
}}

QLabel {{
    background: transparent;
    color: {C_MUTED};
    font-size: {FONT_LABEL};
}}

/* ── GROUP BOX ─────────────────────────────────────────────────────────── */
QGroupBox {{
    border: 1px solid {C_L3};
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 12px;
    color: {C_DIM};
    font-size: {FONT_SECT};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 8px;
    padding: 0 4px;
    color: {C_DIM};
    font-size: {FONT_SECT};
}}

/* ── TABS ──────────────────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {C_L2};
    background-color: {C_L1};
    border-radius: 4px;
}}

QTabBar::tab {{
    background-color: {C_TAB_IDLE};
    color: #8A8A93;
    padding: 8px 16px;
    border: 1px solid {C_TAB_BORDER};
    border-bottom: none;
    margin-right: 2px;
    font-size: {FONT_LABEL};
}}

QTabBar::tab:selected {{
    background-color: {C_TAB_BORDER};
    color: #FFFFFF;
    border-top: 2px solid {C_CYAN};
}}

QTabBar::tab:hover:!selected {{
    background-color: {C_L2};
    color: {C_TEXT};
}}

/* ── BUTTONS — 3D BEVEL ────────────────────────────────────────────────── */
QPushButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {C_BTN_TOP}, stop:1 {C_BTN_BOT});
    color: {C_TEXT};
    border-top: 1px solid {C_EDGE_LIGHT};
    border-left: 1px solid {C_EDGE_LIGHT};
    border-right: 1px solid {C_EDGE_DARK};
    border-bottom: 2px solid {C_EDGE_DARK};
    border-radius: 4px;
    padding: 5px 12px;
    font-size: {FONT_LABEL};
}}

QPushButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {C_L3}, stop:1 #222226);
    color: #FFFFFF;
}}

/* Gradient flips and content shifts 1px right+down on press */
QPushButton:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {C_BTN_BOT}, stop:1 {C_BTN_TOP});
    border-top: 2px solid {C_EDGE_DARK};
    border-left: 2px solid {C_EDGE_DARK};
    border-right: 1px solid {C_EDGE_LIGHT};
    border-bottom: 1px solid {C_EDGE_LIGHT};
    padding-top: 6px;
    padding-left: 13px;
}}

/* Active/checked = cyan border glow */
QPushButton:checked {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {C_BTN_BOT}, stop:1 {C_BTN_TOP});
    border: 1px solid {C_CYAN};
    color: {C_CYAN};
}}

QPushButton:disabled {{
    background: {C_L1};
    color: {C_EDGE_LIGHT};
    border: 1px solid {C_L2};
}}

/* ── CHANNEL STRIP BUTTONS ─────────────────────────────────────────────── */
QPushButton[channelBtn="mute"],
QPushButton[channelBtn="solo"],
QPushButton[channelBtn="punch"] {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {C_BTN_TOP}, stop:1 {C_BTN_BOT});
    color: {C_MUTED};
    border-top: 1px solid {C_EDGE_LIGHT};
    border-left: 1px solid {C_EDGE_LIGHT};
    border-right: 1px solid {C_EDGE_DARK};
    border-bottom: 2px solid {C_EDGE_DARK};
    border-radius: 4px;
    font-weight: bold;
    padding: 3px 6px;
}}

/* Mute active = Record Red glow */
QPushButton[channelBtn="mute"]:checked {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1A0810, stop:1 #0E0608);
    border: 1px solid {C_RED};
    color: {C_RED};
}}

/* Solo active = Success Green glow */
QPushButton[channelBtn="solo"]:checked {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #0A1A0A, stop:1 #061006);
    border: 1px solid {C_GREEN};
    color: {C_GREEN};
}}

/* Punch/Arm active = Warning Amber glow */
QPushButton[channelBtn="punch"]:checked {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1A1200, stop:1 #0E0A00);
    border: 1px solid {C_AMBER};
    color: {C_AMBER};
}}

/* ── SLIDERS — horizontal ──────────────────────────────────────────────── */
QSlider::groove:horizontal {{
    border: 1px solid {C_L3};
    border-top-color: {C_SHADOW};
    border-left-color: {C_SHADOW};
    height: 4px;
    background: {C_BTN_BOT};
    border-radius: 2px;
}}

QSlider::sub-page:horizontal {{
    background: {C_CYAN};
    border-radius: 2px;
}}

/* Weighted capsule handle with center-notch gradient */
QSlider::handle:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {C_EDGE_LIGHT}, stop:0.47 {C_L3},
        stop:0.53 {C_L2}, stop:1 {C_L2});
    border-top: 1px solid {C_HANDLE_LIGHT};
    border-left: 1px solid {C_HANDLE_LIGHT};
    border-right: 1px solid {C_HANDLE_DARK};
    border-bottom: 1px solid {C_HANDLE_DARK};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 3px;
}}

/* ── SLIDERS — vertical ────────────────────────────────────────────────── */
QSlider::groove:vertical {{
    border: 1px solid {C_L3};
    border-top-color: {C_SHADOW};
    border-left-color: {C_SHADOW};
    width: 4px;
    background: {C_BTN_BOT};
    border-radius: 2px;
}}

QSlider::sub-page:vertical {{
    background: {C_CYAN};
    border-radius: 2px;
}}

QSlider::handle:vertical {{
    background: qlineargradient(x1:0, y1:1, x2:1, y2:0,
        stop:0 {C_EDGE_LIGHT}, stop:0.47 {C_L3},
        stop:0.53 {C_L2}, stop:1 {C_L2});
    border-top: 1px solid {C_HANDLE_LIGHT};
    border-left: 1px solid {C_HANDLE_LIGHT};
    border-right: 1px solid {C_HANDLE_DARK};
    border-bottom: 1px solid {C_HANDLE_DARK};
    width: 18px;
    height: 14px;
    margin: 0 -7px;
    border-radius: 3px;
}}

/* ── TEXT INPUTS ───────────────────────────────────────────────────────── */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {C_INPUT_BG};
    color: {C_TEXT};
    border: 1px solid {C_L3};
    border-top-color: {C_SHADOW};
    border-left-color: {C_SHADOW};
    border-radius: 4px;
    padding: 4px 6px;
    selection-background-color: {C_CYAN};
    selection-color: {C_L0};
    font-size: {FONT_LABEL};
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {C_CYAN};
}}

/* ── COMBO BOX ─────────────────────────────────────────────────────────── */
QComboBox {{
    background-color: {C_L2};
    border: 1px solid {C_L3};
    border-radius: 4px;
    padding: 4px 8px;
    color: {C_TEXT};
    font-size: {FONT_LABEL};
}}

QComboBox:hover {{ border-color: {C_EDGE_LIGHT}; }}
QComboBox:focus {{ border-color: {C_CYAN}; }}

QComboBox::drop-down {{
    border: none;
    width: 18px;
}}

QComboBox QAbstractItemView {{
    background-color: {C_L2};
    border: 1px solid {C_L3};
    selection-background-color: {C_L3};
    selection-color: {C_CYAN};
    color: {C_TEXT};
    outline: none;
}}

/* ── LIST WIDGET ───────────────────────────────────────────────────────── */
QListWidget {{
    background-color: {C_L1};
    border: 1px solid {C_L3};
    border-radius: 4px;
    color: {C_TEXT};
    outline: none;
}}

QListWidget::item {{ padding: 4px 8px; }}
QListWidget::item:selected {{ background-color: {C_L3}; color: {C_CYAN}; }}
QListWidget::item:hover {{ background-color: {C_L2}; }}

/* ── SCROLL BARS ───────────────────────────────────────────────────────── */
QScrollArea {{ border: none; background: transparent; }}

QScrollBar:vertical {{
    background: {C_L0};
    width: 8px;
    border-radius: 4px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {C_L3};
    border-radius: 4px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{ background: {C_EDGE_LIGHT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QScrollBar:horizontal {{
    background: {C_L0};
    height: 8px;
    border-radius: 4px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background: {C_L3};
    border-radius: 4px;
    min-width: 20px;
}}

QScrollBar::handle:horizontal:hover {{ background: {C_EDGE_LIGHT}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── STATUS BAR ────────────────────────────────────────────────────────── */
QStatusBar {{
    background-color: {C_INPUT_BG};
    color: {C_MUTED};
    border-top: 1px solid {C_L3};
    font-size: {FONT_LABEL};
}}

/* ── MENU BAR & MENUS ──────────────────────────────────────────────────── */
QMenuBar {{
    background-color: {C_L0};
    color: {C_MUTED};
    border-bottom: 1px solid {C_L2};
    font-size: {FONT_LABEL};
}}

QMenuBar::item:selected {{ background-color: {C_L2}; color: {C_TEXT}; }}

QMenu {{
    background-color: {C_L2};
    border: 1px solid {C_L3};
    color: {C_TEXT};
    font-size: {FONT_LABEL};
}}

QMenu::item:selected {{ background-color: {C_L3}; color: {C_CYAN}; }}

QMenu::separator {{
    height: 1px;
    background: {C_L3};
    margin: 2px 8px;
}}

/* ── TOOLTIP ───────────────────────────────────────────────────────────── */
QToolTip {{
    background-color: {C_L2};
    color: {C_TEXT};
    border: 1px solid {C_L3};
    padding: 4px 8px;
    font-size: {FONT_LABEL};
}}

/* ── PROGRESS BAR ──────────────────────────────────────────────────────── */
QProgressBar {{
    background: {C_BTN_BOT};
    border: 1px solid {C_L3};
    border-top-color: {C_SHADOW};
    border-radius: 3px;
    height: 16px;
    text-align: center;
    color: {C_TEXT};
    font-size: {FONT_SECT};
}}

QProgressBar::chunk {{
    background: {C_CYAN};
    border-radius: 2px;
}}

/* ── SPIN BOX ──────────────────────────────────────────────────────────── */
QSpinBox, QDoubleSpinBox {{
    background-color: {C_L2};
    border: 1px solid {C_L3};
    border-radius: 4px;
    padding: 3px 6px;
    color: {C_TEXT};
    font-size: {FONT_LABEL};
}}

QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {C_CYAN}; }}

QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    background: {C_L3};
    border: none;
    width: 14px;
}}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {C_EDGE_LIGHT};
}}

/* ── CHECK BOX ─────────────────────────────────────────────────────────── */
QCheckBox {{
    color: {C_TEXT};
    font-size: {FONT_LABEL};
    spacing: 6px;
    background: transparent;
}}

QCheckBox::indicator {{
    width: 13px;
    height: 13px;
    border: 1px solid {C_L3};
    border-radius: 2px;
    background: {C_L2};
}}

QCheckBox::indicator:checked {{ background: {C_CYAN}; border-color: {C_CYAN}; }}
QCheckBox::indicator:hover {{ border-color: {C_EDGE_LIGHT}; }}

/* ── RADIO BUTTON ──────────────────────────────────────────────────────── */
QRadioButton {{
    color: {C_TEXT};
    font-size: {FONT_LABEL};
    spacing: 6px;
    background: transparent;
}}

QRadioButton::indicator {{
    width: 13px;
    height: 13px;
    border: 1px solid {C_L3};
    border-radius: 7px;
    background: {C_L2};
}}

QRadioButton::indicator:checked {{ background: {C_CYAN}; border-color: {C_CYAN}; }}

/* ── SPLITTER ──────────────────────────────────────────────────────────── */
QSplitter::handle {{ background: {C_L2}; }}
QSplitter::handle:vertical {{ height: 4px; }}
QSplitter::handle:horizontal {{ width: 4px; }}
QSplitter::handle:hover {{ background: {C_L3}; }}

/* ── RAISED PANEL FRAME ────────────────────────────────────────────────── */
QFrame[panelRole="raised"] {{
    background-color: {C_L2};
    border-top: 1px solid {C_PANEL_TOP};
    border-left: 1px solid {C_PANEL_TOP};
    border-right: 1px solid {C_SHADOW};
    border-bottom: 1px solid {C_SHADOW};
    border-radius: 4px;
}}
"""
