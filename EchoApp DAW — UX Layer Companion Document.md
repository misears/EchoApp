**INTERNAL DESIGN REFERENCE**

# EchoApp DAWUX Layer Companion Document

**Project:** EchoApp - PySide6 Digital Audio Workstation

**Repository:** github.com/misears/EchoApp

**Version:** 1.0.1 | **Date:** 03 August 2026

**Status:** All design decisions resolved and locked as of 03 August 2026

**Audience:** EchoApp development team - internal specification only

**LOCKED & FINAL - v1.0.1**

## Table of Contents

**1.** Design Language & Visual Identity

**2.** Screen 1 - Main Mixer / Arrangement View

**3.** Screen 2 - Demucs AI Stem Extraction Page

**4.** Screen 3 - ACE-Step AI Generation Page

**5.** Screen 4 - Mastering Chain Page

**6.** Screen 5 - MIDI Hardware Mapping Page

**7.** Screen 6 - Settings Page

**8.** Screen 7 - New Project Dialog

**9.** UI State Machine

**10.** Keyboard Shortcuts

**11.** Resolved Design Decisions

## 1\. Design Language & Visual Identity

Core Philosophy:

3D Materiality - NOT flat design. The app must feel like real studio hardware with physical depth and weight.

### 1.1 Depth Layer System

Five depth levels differentiate all surfaces. Each level is implemented via box-shadow, gradient, and border-lighting in QSS.

| **Level**   | **Name**             | **Hex Value**    | **Usage**                                    |
| ----------- | -------------------- | ---------------- | -------------------------------------------- |
| **Level 0** | Deepest Background   | #121214          | Window base / absolute floor                 |
| ---         | ---                  | ---              | ---                                          |
| **Level 1** | Panel Floor          | #16161A          | Panel interior surfaces                      |
| ---         | ---                  | ---              | ---                                          |
| **Level 2** | Raised Surfaces      | #1E1E22          | Raised panels, card backgrounds              |
| ---         | ---                  | ---              | ---                                          |
| **Level 3** | Interactive Elements | #2D2D32          | Controls, buttons, knobs                     |
| ---         | ---                  | ---              | ---                                          |
| **Level 4** | Active / Elevated    | Glow / highlight | Active state - glowing, highlighted controls |
| ---         | ---                  | ---              | ---                                          |

### 1.2 Button Behavior

All buttons use a 3D bevel system. Implementation details are as follows:

- **Resting state:** Light top-left edge #3A3A42, dark bottom-right edge #090910, gradient top #252528 to bottom #1A1A1E.
- **Pressed state:** Gradient flips direction; content visually shifts 1px down and 1px right.
- **Active / Armed state:** Glows cyan #00F0FF or record red #FF3366 via box-shadow.
- **Transition timing:** 80ms on all state transitions.

### 1.3 Slider Design

- **Groove:** Recessed channel with inset shadow.
- **Handle:** Weighted capsule - minimum 14px wide, center notch, gradient #3A3A42 to #1E1E22.
- **Orientation:** Vertical faders on channel strips; horizontal sliders on effect panels.
- **Filled track:** Glows #00F0FF (DAW Cyan).
- **Tooltip:** Displays current value on hover.

### 1.4 Panel Surfaces

- Top-edge highlight #2A2A30, bottom-shadow #0D0D10 - creates raised appearance.
- QGroupBox: 1px solid #2D2D32 border, 6px radius, 12px inner padding.

### 1.5 Typography

| **Role**                       | **Font** | **Size** | **Weight** | **Color**                                 |
| ------------------------------ | -------- | -------- | ---------- | ----------------------------------------- |
| Labels                         | Segoe UI | 11px     | Normal     | #909095                                   |
| ---                            | ---      | ---      | ---        | ---                                       |
| Active values                  | Segoe UI | 12px     | Bold       | #E2E2E5                                   |
| ---                            | ---      | ---      | ---        | ---                                       |
| Section titles                 | Segoe UI | 10px     | Normal     | #6A6A73 - uppercase, 1.5px letter-spacing |
| ---                            | ---      | ---      | ---        | ---                                       |
| Numeric readouts (BPM, ms, dB) | Consolas | 12px     | Normal     | #00F0FF                                   |
| ---                            | ---      | ---      | ---        | ---                                       |

### 1.6 Iconography

- Size: 16×16 or 20×20 SVG, thin-line Fluent-style.
- At rest: #6A6A73 | Hover: #E2E2E5 | Active: #00F0FF

### 1.7 Color Palette

| **Token**     | **Hex / Value**                         | **Usage**             |
| ------------- | --------------------------------------- | --------------------- |
| Background    | #121214                                 | Window base           |
| ---           | ---                                     | ---                   |
| Panel Floor   | #16161A                                 | Panel interior        |
| ---           | ---                                     | ---                   |
| Surface       | #1E1E22                                 | Raised panels         |
| ---           | ---                                     | ---                   |
| Raised        | #2D2D32                                 | Controls              |
| ---           | ---                                     | ---                   |
| DAW Cyan      | #00F0FF                                 | Accent / active state |
| ---           | ---                                     | ---                   |
| Record Red    | #FF3366                                 | Record armed          |
| ---           | ---                                     | ---                   |
| Warning Amber | #FFB830                                 | Loop, warnings        |
| ---           | ---                                     | ---                   |
| Success Green | #39D353                                 | Confirmation          |
| ---           | ---                                     | ---                   |
| Text Primary  | #E2E2E5                                 | Main text             |
| ---           | ---                                     | ---                   |
| Text Muted    | #909095                                 | Labels                |
| ---           | ---                                     | ---                   |
| Text Dim      | #6A6A73                                 | Section titles        |
| ---           | ---                                     | ---                   |
| Border        | #2D2D32                                 | All borders           |
| ---           | ---                                     | ---                   |
| Active Glow   | box-shadow: 0 0 8px rgba(0,240,255,0.4) | Focused controls      |
| ---           | ---                                     | ---                   |

### 1.8 Window Chrome

Custom frameless title bar - app waveform logo, "EchoApp" name, minimize / maximize / close buttons right-aligned. No standard Windows system title bar is displayed.

### 1.9 Ergonomic Layout Principles

- **Control groups never stretch to fill space.** Control clusters are fixed-width; window resize only expands the waveform / timeline area.
- **Mixing controls always LEFT of waveform.** Each channel strip (220px fixed) is the left companion of its corresponding waveform lane.
- **Grouped controls use fixed bounding boxes.** Transport buttons are 8px apart; the cluster is center-anchored and never justified to fill the bar.

## 2\. Screen 1 - Main Mixer / Arrangement View

Default resolution: **1440×900**. Minimum resolution: **1100×700**.

### 2.1 Layout Overview

┌─────────────────────────────────────────────────────────────────────┐ │ \[≡ EchoApp\] CUSTOM TITLE BAR \[_ □ ✕\] │ ├──────────┬──────────────────────────────────────────────────────────┤ │ │ File Edit View Project AI Tools Settings │ │ MASTER │ \[New\]\[Open\]\[Save\]\[Export\] \[Undo\]\[Redo\] BPM:\[120\] Vol │ │ SECTION ├──────────────────────────────────────────────────────────┤ │ 200px │ TIMELINE RULER ← → zoom │ │ ├────────────────────────────────────────┬─────────────────┤ │ \[FADER\] │ \[Channel Strip 220px\] | Waveform Lane │ SIDEBAR 260px │ │ \[VU \] │ \[Channel Strip 220px\] | Waveform Lane │ \[Browser\] │ │ \[LUFS \] │ \[Channel Strip 220px\] | Waveform Lane │ \[Sessions\] │ │ \[EQ \] │ \[+ Add Track \] │ │ ├──────────┴────────────────────────────────────────┴─────────────────┤ │ TRANSPORT BAR - 72px - \[Input▼\] \[Gain──\] |◄ ◄◄ ■ ► ● ►► ►| │ ├─────────────────────────────────────────────────────────────────────┤ │ STATUS: CPU ▓░ 24% RAM 3.2GB WASAPI 48kHz 256buf 4ms Proj\* │ └─────────────────────────────────────────────────────────────────────┘

### 2.2 Top Toolbar

- **Menus:** File, Edit, View, Project, AI Tools, Settings.
- **Quick-access icon buttons:** New Project, Open Project, Save, Export, Undo, Redo.
- **BPM display:** Editable; scroll-wheel nudges value. Positioned on right side of toolbar.
- **Master volume:** Circular knob (not a slider).
- **Time signature dropdown:** 4/4, 3/4, 6/8, 5/4, Custom.
- **Sample rate + bit depth readout:** Non-interactive display.

### 2.3 Left Master Section (200px fixed)

- Master output fader - vertical, minimum 200px stroke.
- Master VU meter - dual-channel bar graph (L+R).
- LUFS integrated reading - cyan monospace readout.
- Master EQ toggle button.
- Master limiter threshold knob.
- Master effects chain button.
- Label "MASTER" - uppercase, dim text color.
- Slightly lighter background than center arrangement area.

### 2.4 Timeline Ruler (28px)

- Displays either Bars:Beats or Seconds - toggle button switches mode.
- Cyan playhead spans full arrangement height.
- Click anywhere to reposition playhead.
- Scrolls in sync with track lanes.

### 2.5 Channel Strip (220px fixed, LEFT of waveform)

- Track name - double-click to edit inline.
- Color swatch - click to open color picker.
- Mute (M), Solo (S), Record Arm (R - glows Record Red when armed).
- Input source dropdown.
- Gain knob, Pan knob.
- Vertical fader - 3D weighted, main volume control.
- FX send knobs - Bus 1 and Bus 2.
- EQ mini-graph - click to open full EQ panel.
- Strip has raised panel background (Level 2 surface).

### 2.6 Waveform Lane (flexible width)

- Per-track color fill.
- Waveform fills lane height. Center divider line rendered.
- Slice markers displayed in magenta.
- Automation curve overlays in cyan with dot handles.
- Clips are rounded-corner rectangles labeled with filename.
- Hover tooltip shows duration + sample rate.
- Right-click context menu: Rename, Duplicate, Delete, Export Clip, Send to Demucs, Send to ACE-Step, Properties.

### 2.7 Add Track Button

\+ button at bottom of channel strip column. Opens a dialog with track type selection: Audio / AI Stem / MIDI / Bus.

### 2.8 Right Sidebar (260px, collapsible)

Two tabs:

- **Browser tab:** File tree view. Files are drag-and-droppable to the arrangement area. Hover shows name, duration, and sample rate.
- **Sessions tab:** List of sessions - name, date, duration. Right-click: Open, Export, Duplicate, Delete, Rename. Long names truncated with ellipsis; full name shown in tooltip after 500ms hover delay.

### 2.9 Transport Bar (72px, full width)

Background #1A1A1E, 1px top border #2D2D32. The bar never resizes. Three fixed clusters:

| **Cluster**        | **Position**                                   | **Contents**                                                                                                                                                                                                                                                                                                     |
| ------------------ | ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Left cluster**   | Fixed left                                     | Input device dropdown, input monitoring toggle, input gain slider (80px wide)                                                                                                                                                                                                                                    |
| ---                | ---                                            | ---                                                                                                                                                                                                                                                                                                              |
| **Center cluster** | Center-anchored, fixed-width - NEVER stretches | Buttons: \|◄ ◄◄ ■ ► ● ►► ►\| - each 36×36px with 3D bevel. Stop=gray, Play glows green when active, Record glows red when armed. Below buttons: seek bar (width of cluster only). Below seek bar: time display - BARS:BEATS:TICKS left, HH:MM:SS:MS right - both cyan monospace on recessed LCD-style dark panel |
| ---                | ---                                            | ---                                                                                                                                                                                                                                                                                                              |
| **Right cluster**  | Fixed right                                    | Loop toggle (glows amber when active), loop start/end numeric inputs, metronome toggle with BPM mirror, punch-in/punch-out toggles                                                                                                                                                                               |
| ---                | ---                                            | ---                                                                                                                                                                                                                                                                                                              |

### 2.10 Status Bar (24px)

Left to right: CPU bar + %, RAM usage, driver name, sample rate, buffer size, latency in ms (cyan), project name, save status dot (green = saved, amber = unsaved).

## 3\. Screen 2 - Demucs AI Stem Extraction Page

Accessed via **AI Tools → "Stem Separation (Demucs)"** OR clip right-click → "Send to Demucs". Renders as a full tab view with a tab bar to switch back to the Mixer.

### 3.1 Layout Overview

┌──────────────────────────────────────────────────────────────────┐ │ \[Mixer\] \[Stem Separation (Demucs)\] \[AI Generation (ACE-Step)\] │ ├─────────────────────────┬──────────────────────┬─────────────────┤ │ LEFT CONTROLS 320px │ CENTER - MAIN AREA │ RIGHT 300px │ │ │ │ TRANSFER │ │ \[Source Audio ▼\] │ \[Progress ▼\] │ OPTIONS │ │ Drop zone │ Overall bar │ │ │ Browse button │ Per-stem bars │ ◉ Send to │ │ │ │ Main Tracks │ │ \[Separation Model ▼\] │ \[Activity Log ▼\] │ │ │ Model dropdown │ Terminal window │ ○ Save to │ │ Device selector │ green/amber/red │ Folder │ │ Shifts spinner │ Copy/Save/Clear │ │ │ VRAM warning │ │ → Transfer to │ │ │ \[Output Preview ▼\] │ ACE-Step │ │ \[Output Settings ▼\] │ Stem waveforms │ │ │ Format dropdown │ Play buttons │ \[Output List\] │ │ Sample rate │ │ ☑ Vocals │ │ Normalize toggle │ │ ☑ Drums │ │ │ │ ☑ Bass │ │ \[Separate\] ← big btn │ │ ☑ Other │ │ \[Cancel\] │ │ \[Transfer ►\] │ └─────────────────────────┴──────────────────────┴─────────────────┘

### 3.2 Left Panel - Source Audio

- Large drag-and-drop zone - dashed border, dims on hover.
- Displays filename, duration, and waveform thumbnail once a file is loaded.
- Folder icon + Browse button. Full path shown in read-only field below.

### 3.3 Left Panel - Separation Model

- **Model dropdown:** Prefilled with htdemucs, htdemucs_ft, htdemucs_6s, demucs, demucs_extra, mdx, mdx_extra, mdx_q, mdx_extra_q. Each entry labeled with stem count (4 stems / 6 stems). Tooltip explains each model.
- "Manage Models…" link - navigates to Settings → Model Manager → Demucs tab.
- **Device selector:** CPU / CUDA GPU / MPS - auto-detected; unavailable options grayed.
- **Inline VRAM warning:** Color-coded green / amber / red based on pre-cached VRAM query. Never blocks the user from proceeding.
- "Force CPU" checkbox.
- **Shifts:** Integer spinner - default 1, maximum 10.
- Two-stem mode checkbox + stem-pair dropdown (vocals / drums / bass / guitar / piano / other).

### 3.4 Left Panel - Output Settings

- Format dropdown: WAV 32-bit, WAV 16-bit, FLAC, MP3 320.
- Sample rate: 44100 / 48000 / 96000 / Match Source.
- Normalize toggle.

### 3.5 Run Controls

- "Separate" button - full-width, 44px tall. Green glow when ready, amber pulsing during processing.
- "Cancel" button appears during processing only.

### 3.6 Center - Progress

- Overall progress bar - 16px height, recessed channel, cyan fill with glow, percentage label. States: Idle / Loading model… / Processing… / Complete.
- Per-stem progress bars - labeled per stem.
- Elapsed time and ETA readouts.

### 3.7 Center - Activity Log

QPlainTextEdit styled as a terminal. Background #0A0A0C, monospace 11px font. Color scheme: green = info (#39D353), amber = warnings (#FFB830), red = errors (#FF3366). Auto-scrolls. Timestamps in dim gray on every line. Toolbar: Copy Log, Save Log…, Clear, log level filter dropdown.

### 3.8 Center - Output Preview (post-completion)

Per-stem row containing: stem name, waveform thumbnail, duration, Play button, and volume knob.

### 3.9 Right Panel - Transfer Options

Two 3D selection tile cards styled as raised panels:

- **Card 1 - "Send to Main Tracks":** Mixer fader icon. Sub-options: insert at playhead / after last track / replace by stem name. Auto-color-code toggle.
- **Card 2 - "Save to Project Folder":** Folder icon. Output path field + Browse button. Subfolder pattern field (default: {project_name}/{source_filename}/stems/). "Also send to main tracks after saving" checkbox.

Below cards: outlined secondary button "→ Transfer to ACE-Step" - routes completed stems to ACE-Step page as source audio.

Output file checklist (post-completion): per-stem rows with checkbox, name, file size, and waveform icon. Primary "Transfer" button full-width with cyan glow.

## 4\. Screen 3 - ACE-Step AI Generation Page

Accessed via **AI Tools → "AI Audio Generation (ACE-Step)"**. Full tab, separate from the Demucs tab.

### 4.1 Layout Overview

┌───────────────────────────────────────────────────────────────────┐ │ \[Mixer\] \[Stem Separation (Demucs)\] \[AI Generation (ACE-Step)\] │ ├──────────────────────────┬────────────────────────────────────────┤ │ LEFT PARAMS - 420px │ RIGHT - PROMPTS & OUTPUT │ │ │ │ │ \[Model ▼\] │ \[Describe Your Audio ▼\] │ │ Model dropdown │ Main prompt textarea │ │ LoRA/adapter │ Negative prompt (collapsible) │ │ Manage Models… │ Lyrics field (collapsible) │ │ │ │ │ \[Style Tags ▼\] │ \[Generate\] ← full width 48px │ │ Tag pill input │ Progress bar + log (collapsible) │ │ Suggestions dropdown │ Cancel button │ │ │ │ │ \[Instruments ▼\] │ \[Generated Audio ▼\] │ │ Tag pill input │ Result cards (batch grid) │ │ │ ▶ Play ↺ Loop ★ Fave │ │ \[Audio Reference ▼\] │ Regenerate / Vary buttons │ │ Source dropdown │ │ │ Waveform thumbnail │ \[Transfer ▼\] │ │ Influence slider │ ◉ Send to Main Tracks │ │ Start/End time fields │ ○ Save to Project Folder │ │ │ → Send to Demucs │ │ \[Generation Settings ▼\] │ \[Transfer ►\] │ │ Duration slider+input │ │ │ Steps slider+input │ │ │ CFG scale slider │ │ │ Seed + randomize btn │ │ │ Lock seed checkbox │ │ │ Scheduler dropdown │ │ │ ERG weight slider │ │ │ ELA weight slider │ │ │ Batch count spinner │ │ │ Output format │ │ └──────────────────────────┴────────────────────────────────────────┘

### 4.2 Model Selection

- Dropdown prefilled with all ACE-Step checkpoint files found in the models directory (e.g., ACE-Step-v1, ACE-Step-v1-chinese-rap). Each entry shows a type badge: Music / Vocals / Rap / Instrumental.
- "Manage Models…" link → Settings → Model Manager → ACE-Step tab.
- LoRA/adapter secondary dropdown - None default; lists .safetensors files from models/lora/. "+ Add Custom LoRA…" option at bottom opens file browser.
- Inline VRAM warning - same green / amber / red system as Demucs page. Non-blocking.
- "Force CPU" checkbox.

### 4.3 Style Tags

Tag pill input - type a genre or style term, press Enter or comma to add as a pill badge. Suggestions populate as a dropdown while typing:

cinematic, hip-hop, lo-fi, ambient, rock, jazz, electronic, acoustic, orchestral, trap, funk, soul, metal, pop, folk, reggae, blues, country, RnB, punk, classical, synthwave, drill, afrobeats, bossa nova, latin, world.

Pills are individually removable (× per pill). Maximum 12 pills visible; overflow scrolls. "Clear All" link provided.

### 4.4 Instruments

Same pill system as Style Tags. Suggestions: guitar, bass, drums, piano, strings, brass, synth, organ, violin, cello, trumpet, saxophone, flute, choir, pads, percussion, arpeggio, 808, hi-hats, vocals. "No specific instruments" checkbox disables the field entirely.

### 4.5 Audio Reference

- Source dropdown: None / Upload File / Use Active Track / Use Stem from last Demucs run.
- Waveform thumbnail shown on selection.
- Influence Strength horizontal slider - range 0.0 to 1.0.
- Reference start and end time fields (HH:MM:SS format).

### 4.6 Generation Settings - Full Parameter Exposure

| **Parameter**        | **Control**              | **Range / Default**                                     | **Notes**                                     |
| -------------------- | ------------------------ | ------------------------------------------------------- | --------------------------------------------- |
| Duration             | Slider + number input    | 5-300s, step 1s                                         | Displayed as "0:30" format                    |
| ---                  | ---                      | ---                                                     | ---                                           |
| Steps                | Slider + number input    | 10-150, default 50                                      | "More steps = higher quality, slower"         |
| ---                  | ---                      | ---                                                     | ---                                           |
| Guidance Scale (CFG) | Slider + number input    | 1.0-20.0, step 0.1, default 7.5                         | "How closely AI follows prompt"               |
| ---                  | ---                      | ---                                                     | ---                                           |
| Seed                 | Number input + dice icon | 0-2147483647                                            | Dice randomizes; Lock seed checkbox           |
| ---                  | ---                      | ---                                                     | ---                                           |
| Scheduler / Sampler  | Dropdown                 | Euler, Euler Ancestral, DPM++ 2M, DPM++ SDE, DDIM, PNDM | Tooltip explains each option                  |
| ---                  | ---                      | ---                                                     | ---                                           |
| ERG weight           | Slider                   | 0.0-2.0, default 1.0                                    | Rhythm guidance weight                        |
| ---                  | ---                      | ---                                                     | ---                                           |
| ELA weight           | Slider                   | 0.0-2.0, default 1.0                                    | Lyric alignment - grayed if no lyrics entered |
| ---                  | ---                      | ---                                                     | ---                                           |
| Batch count          | Spinner                  | 1-8                                                     | Estimated total time shown below              |
| ---                  | ---                      | ---                                                     | ---                                           |
| Output format        | Dropdown                 | WAV 32-bit float, WAV 16-bit, FLAC, MP3 320kbps         |                                               |
| ---                  | ---                      | ---                                                     | ---                                           |

### 4.7 Prompts (Right Column)

- **Main textarea:** Minimum 5 lines. Placeholder: "Describe the sound, mood, energy, instrumentation…"
- **Negative prompt:** Collapsible. Placeholder: "e.g., distortion, noise, vocals, off-key…"
- **Lyrics field:** Collapsible, line-numbered. Tooltip: "Structured lyrics improve vocal generation with ELA guidance."

### 4.8 Generate Button

- Full right-column width, 48px tall.
- Idle state: green glow.
- Processing state: amber pulsing + spinner + "Generating…" + ETA sub-label.
- Real-time terminal log (collapsible) - same green / amber / red terminal styling as Demucs log.

### 4.9 Results

Grid of result cards. Each card displays: waveform thumbnail, duration, seed used, Play button, Loop button, star/favorite toggle. Quick-action row below: "Regenerate same seed", "Regenerate new seed", "Vary (subtle)", "Vary (strong)".

### 4.10 Transfer Options

Same three tile cards as Demucs - Send to Main Tracks, Save to Project Folder, Send to Demucs. Transfer button: full width, cyan glow.

## 5\. Screen 4 - Mastering Chain Page

Accessed via **Master Section → "Effects Chain" button** or **View → "Mastering Chain"**. Renders as a full-width panel or full tab.

### 5.1 Signal Chain Layout

Horizontal signal chain - raised 3D cards arranged left to right in signal flow order. Arrow connectors between each block. Each block has a bypass button in its top-right corner: red glow when bypassed, gray when active (gray = working, consistent with hardware convention).

| **Position** | **Block**              | **Controls**                                                                                                                   |
| ------------ | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| 1            | Input Trim             | Trim gain knob, input level meter                                                                                              |
| ---          | ---                    | ---                                                                                                                            |
| 2            | EQ - 4-Band Parametric | Visual frequency response curve. Four bands: Low Shelf, Low Mid, High Mid, High Shelf - each with Frequency, Gain, and Q knobs |
| ---          | ---                    | ---                                                                                                                            |
| 3            | Compressor             | Threshold, Ratio, Attack, Release, Knee, Makeup Gain knobs. Input / output gain reduction VU meters                            |
| ---          | ---                    | ---                                                                                                                            |
| 4            | Stereo Widener         | Width knob (0-200%), mono bass frequency crossover knob                                                                        |
| ---          | ---                    | ---                                                                                                                            |
| 5            | Limiter                | Threshold, Ceiling, Release knobs. Clip indicator LED (red flash on peak). True peak readout                                   |
| ---          | ---                    | ---                                                                                                                            |
| 6            | Output                 | Output level meter, output trim                                                                                                |
| ---          | ---                    | ---                                                                                                                            |

### 5.2 LUFS Meter Panel

Positioned on the right side of the chain area. All numeric readouts in cyan monospace.

| **Readout**     | **Description**                                               |
| --------------- | ------------------------------------------------------------- |
| Integrated LUFS | Full-program loudness. Color-coded against target (see below) |
| ---             | ---                                                           |
| Short-term LUFS | 3-second rolling average                                      |
| ---             | ---                                                           |
| Momentary LUFS  | 400ms rolling average                                         |
| ---             | ---                                                           |
| LU Range        | Dynamic range measure                                         |
| ---             | ---                                                           |
| True Peak       | Inter-sample peak in dBTP                                     |
| ---             | ---                                                           |

#### LUFS Target Presets

Dropdown labeled "Target: \[▼\]" above the LUFS meter panel:

- −14 LUFS - Spotify / Apple Music
- −16 LUFS - YouTube / SoundCloud
- −23 LUFS - EBU R128 Broadcast
- −24 LUFS - ATSC A/85 North American TV
- Custom - user-defined

The selected target renders as a dashed amber horizontal line on the LUFS history graph. The Integrated LUFS readout turns green within ±0.5 LU of target, amber within ±1 LU, and red further outside. A LUFS history scrolling line chart is displayed below the numeric readouts.

## 6\. Screen 5 - MIDI Hardware Mapping Page

Accessed via **Settings → MIDI Devices** or the MIDI icon in the toolbar. Three-panel layout.

### 6.1 Left Panel - Devices

- List of all detected MIDI input devices.
- Each row: device name, status dot (green = connected, gray = disconnected), channel dropdown (1-16 or All).
- "Refresh Devices" button at top of panel.

### 6.2 Center Panel - Mappings

Table with the following columns:

| **Column**     | **Content**                               |
| -------------- | ----------------------------------------- |
| Parameter Name | Name of the mapped DAW parameter          |
| ---            | ---                                       |
| Current Value  | Live value readout                        |
| ---            | ---                                       |
| MIDI CC        | Assigned CC number                        |
| ---            | ---                                       |
| MIDI Channel   | 1-16                                      |
| ---            | ---                                       |
| Min Range      | Minimum mapped value                      |
| ---            | ---                                       |
| Max Range      | Maximum mapped value                      |
| ---            | ---                                       |
| Curve          | Linear / Log / Exp                        |
| ---            | ---                                       |
| Learn          | Per-row "Learn" button - rightmost column |
| ---            | ---                                       |

Rows are grouped by category: Transport, Channel 1 Fader, Channel 1 Pan, Effects, Master, etc.

### 6.3 Right Panel - MIDI Learn Console

- Scrolling live MIDI monitor - format: "CH1 CC74 Value: 87" in monospace green.
- MIDI Learn toggle button at top - when enabled, next incoming CC auto-maps to the selected parameter row.
- Confirmation card on new mapping detected: "Map CC74 to Master Volume? \[Confirm\] \[Cancel\]"
- Amber banner below toolbar when MIDI Learn is active: "MIDI Learn Active - touch a hardware control to assign."

## 7\. Screen 6 - Settings Page

Accessed via **Settings menu** or **gear icon**. Full page tab. Left sidebar navigation (200px fixed) + right content area.

### 7.1 Audio Engine

- Backend dropdown: WASAPI Exclusive, WASAPI Shared, ASIO, JACK/PipeWire.
- Input device dropdown + output device dropdown.
- Sample rate, buffer size, bit depth selectors.
- Latency display - read-only.
- Test button - plays 1kHz tone to confirm output.
- Driver status indicator.

### 7.2 Model Manager (Critical Section)

Two sub-tabs: **Demucs Models** and **ACE-Step Models**.

Each sub-tab contains the following elements:

- **Installed models table:** Columns - Name, Type/Stems, File Size, Date Added. Per-row: "Set as Default" button, "Remove" button (trash icon, requires confirmation dialog before executing).
- "Add Model from Folder…" - file dialog, validates format, requires confirmation before adding.
- "Add Model from URL…" - URL text field + Download button + inline progress bar.
- **Drag-and-drop zone:** Large, dashed border - "Drop model files here to install". Accepts .pt, .th, .safetensors, and folder drops. Spinner shown while scanning/validating.
- **Model details pane** (when a row is selected): Name, description, stem count, recommended use case, required VRAM, notes from model metadata.

### 7.3 Appearance

- Theme selector.
- Accent color picker - default #00F0FF.
- Font size slider: Small / Medium / Large.
- Waveform color mode: per-track or single color.
- Animation speed: Full / Reduced / None.

### 7.4 Keyboard Shortcuts

Searchable table listing all actions + assigned shortcuts. Click a shortcut cell to reassign. "Reset All to Defaults" button.

### 7.5 Project Defaults

Default folder path, default sample rate, default BPM, auto-save interval, auto-save location.

### 7.6 About

App version 1.0.1, build date 03 August 2026, credits, GitHub repo link (github.com/misears/EchoApp), license information.

## 8\. Screen 7 - New Project Dialog

Modal overlay that dims the main window. Triggered via **File → New Project** or **Ctrl+N**.

### 8.1 Dialog Contents

- **Project name field:** Auto-focuses on dialog open.
- **Project folder selector:** Path display + Browse button; defaults to Preferences setting.
- **Template selector:** Grid of visual template cards - Empty, Basic 4-Track, Podcast, Beat Maker, AI Stems Session. Each card shows a thumbnail illustration and one-line description.
- **Sample rate dropdown.**
- **BPM field.**
- **Buttons:** "Create Project" (cyan 3D primary button) + "Cancel".

## 9\. UI State Machine

| **State**                      | **Visual Behavior**                                                                                                                                                                                  |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Idle / No Project**          | All track controls grayed out. Transport disabled. Arrangement area shows welcome panel with "New Project" and "Open Project" cards.                                                                 |
| ---                            | ---                                                                                                                                                                                                  |
| **Project Open / Stopped**     | All controls active. Stop button dim. Play button ready. Record arm available.                                                                                                                       |
| ---                            | ---                                                                                                                                                                                                  |
| **Playing**                    | Play button glows green. Seek bar animates. Playhead moves across waveforms. Record button disabled (unless overdub mode active).                                                                    |
| ---                            | ---                                                                                                                                                                                                  |
| **Recording**                  | Record button pulses red. Armed tracks show red border glow. Live incoming waveform drawn in real time in waveform lane. Non-armed tracks slightly dimmed. Persistent red "REC" badge in status bar. |
| ---                            | ---                                                                                                                                                                                                  |
| **AI Processing (background)** | Persistent progress indicator in status bar - small bar + "AI Processing…" label in amber. Clicking it switches to the active AI page.                                                               |
| ---                            | ---                                                                                                                                                                                                  |
| **MIDI Learn Mode**            | Amber banner below toolbar: "MIDI Learn Active - touch a hardware control to assign." All assignable parameters highlight with amber border glow.                                                    |
| ---                            | ---                                                                                                                                                                                                  |
| **Unsaved Changes**            | Status bar save indicator shows amber dot. Title bar appends asterisk (\*) after project name.                                                                                                       |
| ---                            | ---                                                                                                                                                                                                  |

## 10\. Keyboard Shortcuts

| **Action**             | **Shortcut**     |
| ---------------------- | ---------------- |
| Play / Stop            | Space            |
| ---                    | ---              |
| Record                 | R                |
| ---                    | ---              |
| Skip to Start          | Home             |
| ---                    | ---              |
| Skip to End            | End              |
| ---                    | ---              |
| Undo                   | Ctrl+Z           |
| ---                    | ---              |
| Redo                   | Ctrl+Y           |
| ---                    | ---              |
| Save                   | Ctrl+S           |
| ---                    | ---              |
| Delete selected clip   | Delete           |
| ---                    | ---              |
| Split clip at playhead | S                |
| ---                    | ---              |
| New track              | Ctrl+T           |
| ---                    | ---              |
| Mute selected          | M                |
| ---                    | ---              |
| Solo selected          | Alt+S            |
| ---                    | ---              |
| Zoom in (timeline)     | Ctrl+Scroll Up   |
| ---                    | ---              |
| Zoom out (timeline)    | Ctrl+Scroll Down |
| ---                    | ---              |
| Switch panels          | Tab              |
| ---                    | ---              |
| Open Demucs            | Ctrl+D           |
| ---                    | ---              |
| Open ACE-Step          | Ctrl+E           |
| ---                    | ---              |
| Open Mastering Chain   | Ctrl+M           |
| ---                    | ---              |
| MIDI Learn toggle      | Ctrl+L           |
| ---                    | ---              |
| New Project            | Ctrl+N           |
| ---                    | ---              |
| Open Project           | Ctrl+O           |
| ---                    | ---              |
| Export                 | Ctrl+Shift+E     |
| ---                    | ---              |

## 11\. Resolved Design Decisions

All design decisions below are **LOCKED AND FINAL** as of 03 August 2026 (v1.0.1). They must not be reopened or modified without a formal document version bump and changelog entry. Developers must implement exactly as specified.

**✅ DECISION 1 - Automation Editor: LOCKED - INLINE for v1.0**

Automation curves are displayed **inline in the waveform lane** as curve overlays. A dropdown on the channel strip selects which parameter's automation lane is visible for that track. This is the only automation view in v1.0.

A dedicated dock panel is explicitly **deferred to v2.0**. Developers must NOT implement a separate automation dock panel in v1 under any circumstances.

**✅ DECISION 2 - AI Tool Tab Structure: LOCKED - SEPARATE TABS for v1.0**

Demucs and ACE-Step are implemented as **separate full-page tabs** in the tab bar. There is no unified "AI Studio" tab in v1.0. The "Transfer to ACE-Step" button on the Demucs output panel provides sufficient workflow continuity.

A unified view is deferred to a future release. Tab bar shows two distinct entries: **"Stem Separation (Demucs)"** and **"AI Generation (ACE-Step)"**.

**✅ DECISION 3 - Long Session Names: LOCKED - TRUNCATE WITH TOOLTIP**

Session and project names in the sidebar Sessions tab must be **truncated with an ellipsis ("...")** when they exceed the available row width. No dynamic row resizing or horizontal overflow is permitted.

On hover, after a **500ms delay**, a tooltip displays the full untruncated name. Row heights are fixed. No alternative truncation strategy is in scope for v1.0.

**✅ DECISION 4 - GPU Memory Warning: LOCKED - INLINE WARNING CONFIRMED**

The inline VRAM warning below the model dropdown is confirmed for implementation in **both the Demucs and ACE-Step** model selector panels. When a model is selected, the UI immediately queries cached device VRAM data (pre-fetched at startup) and displays a color-coded notice:

• **Green** - VRAM is sufficient

• **Amber** - VRAM is borderline

• **Red** - VRAM is insufficient

A "Force CPU" checkbox is included on both pages. This behavior is **strictly non-blocking** - it must never prevent the user from proceeding.

**✅ DECISION 5 - LUFS Target Presets: LOCKED - INCLUDE IN v1.0**

LUFS target preset mode is confirmed for v1.0. A dropdown labeled "Target: \[▼\]" appears above the LUFS meter panel with these presets:

• −14 LUFS - Spotify / Apple Music

• −16 LUFS - YouTube / SoundCloud

• −23 LUFS - EBU R128 Broadcast

• −24 LUFS - ATSC A/85 North American TV

• Custom - user-defined

The selected target renders as a **dashed amber horizontal line** on the LUFS history graph. The Integrated LUFS readout turns **green** within ±0.5 LU of target, **amber** within ±1 LU, **red** further outside. Implement in v1.0 with no deferral.

**✅ DECISION 6 - Clip Fade Settings: LOCKED - POPOVER IN v1.0**

The right-click "Fade Settings..." popover is confirmed for v1.0 and **coexists** with the existing 6px drag handles on clip edges - both mechanisms must be implemented together.

The popover contains two numeric inputs (Fade In: 0 ms, Fade Out: 0 ms) and a curve selector dropdown per fade (Linear, Exponential, Logarithmic, S-curve). It is a **small non-modal popover**, not a full dialog.

The drag handle and the popover must remain **in sync in real time** - changing one immediately updates the other.

**✅ DECISION 7 - Undo History Scope for AI Operations: LOCKED - OPTION 1**

The **Transfer action** (importing stems or generated audio into the arrangement) IS undoable via Ctrl+Z. Undoing a Transfer removes the imported tracks from the arrangement view but does NOT delete source audio files from disk - those remain in the project folder permanently.

The **Demucs separation process itself is NOT undoable** - it is a disk write and cannot be reversed through the undo system.

There is a **single linear undo stack** for all arrangement operations. No separate AI undo stack is implemented.

EchoApp UX Layer Companion Document - Version 1.0.1 - 03 August 2026

Internal design reference for the EchoApp project (github.com/misears/EchoApp)

All design decisions resolved 03 August 2026. This document describes locked UX behavior for v1.0 implementation.