# EchoApp Task Hub

This is the single working file for EchoApp ideas, actionable todos, and current problems.

Use this file as the default place to capture:

- rough ideas that are not yet scoped,
- next actionable engineering tasks,
- active problems or recurring friction,
- and recent completions worth keeping visible.

## Top-Level Instruction Documents

These documents are now treated as top-level instruction sources for EchoApp work. Read them before changing UI, layout, launch flow, playback behavior, AI workflow surfaces, or related persistence paths.

### [offline thoughts.md](offline%20thoughts.md)

- Treat this as the implementation blueprint for the app architecture and technical direction.
- Its guidance locks the global visual system, multi-track timeline sync, audio-thread bridge, Demucs workflow, waveform rendering, automation editing, mixing engine, mastering chain, Linux audio driver path, and non-destructive storage approach.
- The phase structure is directional and implementation-focused, so future work should align with it instead of inventing parallel patterns.

### [EchoApp DAW — UX Layer Companion Document.md](EchoApp%20DAW%20%E2%80%94%20UX%20Layer%20Companion%20Document.md)

- Treat this as the locked UX specification for the main DAW experience.
- It defines the studio-hardware visual language, the main mixer/arrangement view, Demucs and ACE-Step as separate tabs, the mastering chain, MIDI mapping, settings, new-project flow, keyboard shortcuts, and the state machine.
- The resolved design decisions are final unless the document version is formally bumped; do not reopen them casually in implementation work.

### Instruction hierarchy

- These two documents outrank older working notes when they conflict with backlog wording or stale status snapshots.
- Use TASK_HUB.md to track what to do next, but use the two top-level instruction docs to decide how the app should look and behave.
- When a task touches one of those instructions, capture the work here instead of scattering it across ad hoc notes.

When work changes the project state in a meaningful way, update this file in the same change.

## How to use this file

- Put unshaped feature thoughts in **Ideas**.
- Move items into **Todos** when they are specific enough to execute.
- Track blockers, bugs, and repeated pain points in **Problems**.
- Move finished work into **Recently Completed** so the active sections stay useful.

---

## Ordered Build Task List

Derived from `EchoApp DAW — UX Layer Companion Document.md` (v1.0.1, locked) and `offline thoughts.md` (implementation blueprint). Tasks are sequenced so each group depends only on groups above it. Work top-to-bottom within each group before moving to the next.

---

### Group 1 — Foundation: Visual System & App Shell

These must land before any screen work; every subsequent surface inherits from them.

- [x] **1.1** Implement the global QSS stylesheet with all five depth-level backgrounds, 3D bevel button states (resting / pressed / active glow), recessed slider groove, weighted capsule handle, and DAW Cyan `#00F0FF` filled track. Apply via `app.setStyleSheet()` at startup. *(ref: UX §1.1–1.6, offline Phase 1)*
- [x] **1.2** Establish the full color-token set (Background `#121214` through Active Glow box-shadow) as named constants in `app/styles.py` so every widget references tokens, not raw hex. *(ref: UX §1.7)*
- [x] **1.3** Implement the custom frameless title bar: app waveform logo, "EchoApp" label, and right-aligned minimize / maximize / close buttons. Remove the Windows system title bar. *(ref: UX §1.8)*
- [x] **1.4** Lock the main window ergonomic layout skeleton: fixed-width control zones never stretch on resize; only the waveform/timeline area grows. Set minimum resolution to 1100×700, default target 1440×900. *(ref: UX §1.9, §2.1)* **COMPLETE:** MainMixerLayout fully implemented with 3-zone splitter (Master 200px fixed | Waveform flexible | Sidebar 260px fixed, collapsible). Toolbar, Timeline Ruler, Transport Bar container, and content area scaffolded. Window size 1440×900 with minimum 1100×700 enforced. Integrated TimelineSyncController (Group 2.1) as single source of truth.

<!-- REVISIT: Confirm whether typography tokens (Segoe UI / Consolas sizes) belong in styles.py or a separate theme file before 1.2 lands. -->

---

### Group 2 — Core Infrastructure: Sync, Persistence & Threading

Backend wiring that all UI components will depend on.

- [x] **2.1** Build the `TimelineSyncController` (QObject with `zoom_factor`, `scroll_position`, `playhead` Properties and Signals) so all timeline-linked widgets subscribe to a single source of truth instead of updating independently. *(ref: offline Phase 2)*
  - **Status:** COMPLETE
  - **What landed:** `app/controllers/timeline_sync_controller.py` (200 lines) with full signal-based architecture: playhead, zoom (1/128–128x, 1.25x step), scroll, playback, BPM (30–300), time signature, master volume (-80 to +12 dB), sample rate configuration. Integrated into MainMixerLayout and TabbedEchoProWindow; ready for UI subscription.
  - **Notes:** Single source of truth pattern enables clean cross-widget synchronization without tight coupling

- [x] **2.2** Define the non-destructive project serialization schema: JSON envelope storing source file paths, clip start/end samples, track metadata, and arrangement state — no destructive writes to source audio. Hook save/load into `project_model.py`. *(ref: UX Decision 7, offline Phase 10)*
  - **Status:** COMPLETE
  - **What landed:** `app/controllers/project_persistence.py` (250 lines) with ProjectMetadata dataclass, ProjectPersistence manager class, and non-destructive reference-by-path approach. Supports project template creation, source audio addition, stem management, backward compatibility via version field. Exports placeholder for future WAV export (Group 7).
  - **Decision made:** Non-destructive uses path references (v1.0 approach); future versions can support deep copies or archive formats if needed

- [x] **2.3** Wire the audio-thread-to-UI communication bridge using a lock-free SPSC ring buffer so playhead position updates cross from the audio thread to the PySide repaint loop without blocking real-time audio. *(ref: offline Phase 3)*
  - **Status:** COMPLETE
  - **What landed:** `app/controllers/audio_thread_bridge.py` (260 lines) with non-blocking queue-based bridge using Python's thread-safe `queue.Queue`. Supports playhead, meter, VU, state updates from audio thread; signal-based subscription model for UI handlers. Graceful message dropping on queue overflow to prevent audio stalls.
  - **Decision made:** Pure-Python threading.Queue approach chosen for v1.0 (cross-platform, no C++ DLL dependency, sufficient latency for non-RT requirements). Can migrate to lock-free ring buffer or JUCE/C++ bridge in later phases if latency requirements increase.

---

### Group 3 — Screen 1: Main Mixer / Arrangement View

Build the primary DAW surface in sub-section order so each new layer has a stable parent to attach to.

- [x] **3.1** Implement the top toolbar: File / Edit / View / Project / AI Tools / Settings menus; New / Open / Save / Export / Undo / Redo icon buttons; editable BPM display with scroll-wheel nudge; master volume circular knob; time signature dropdown; sample rate + bit depth readout. *(ref: UX §2.2)*
  - **Status:** Complete
  - **Depends on:** Item 1.4 (MainMixerLayout scaffolding) ✓
  - **What landed:** `app/ui/widgets/main_mixer_layout.py` now builds the toolbar shell with menu buttons, quick-action buttons, controller-backed BPM/time-signature/master-volume controls, and sample format readout. File Export and Settings are now wired to real callbacks in `echo_pro_app.py`, View now includes sidebar toggling, and DAW-standard key bindings are applied (`Ctrl+N`, `Ctrl+O`, `Ctrl+S`, `Ctrl+Shift+E`, `Ctrl+Z`, `Ctrl+Y`, `Ctrl+B`, `Ctrl+,`).

- [x] **3.2** Build the Left Master Section (200px fixed): vertical master fader (≥200px stroke), dual-channel L+R VU meter, LUFS integrated readout (cyan monospace), master EQ toggle, master limiter threshold knob, master effects chain button, "MASTER" label. *(ref: UX §2.3)*
  - **Status:** Complete
  - **Depends on:** Item 1.4 (MainMixerLayout scaffolding) ✓
  - **What landed:** `app/ui/widgets/main_mixer_layout.py` now renders the fixed 200px master panel shell with a 220px vertical fader, dual L/R VU meters, cyan LUFS readout, master EQ toggle, limiter threshold dial, and effects-chain button. Live meter/LUFS updates are now driven from recording meter updates in `echo_pro_app.py::refresh_recording_meters()` using a DAW-style integrated loudness proxy. Master EQ toggle and effects-chain button are now routed to real app callbacks, and limiter threshold now feeds render behavior via `playback_mixer.py` during mix/export.

- [x] **3.3** Implement the Timeline Ruler (28px): bars:beats / seconds toggle, cyan full-height playhead, click-to-reposition, synchronized horizontal scroll. *(ref: UX §2.4)*
  - **Status:** Complete
  - **Depends on:** Item 1.4 (MainMixerLayout scaffolding) ✓, Item 2.1 (TimelineSyncController)
  - **What landed:** `app/ui/widgets/main_mixer_layout.py` now uses a controller-backed ruler canvas with Bars:Beats / Seconds toggle, cyan playhead render, and click-to-reposition behavior. `echo_pro_app.py` bridges waveform scroll position through `TimelineSyncController`, and ruler extent now syncs to live timeline content width so ruler interactions mirror the active viewport.

- [x] **3.4** Build the Channel Strip widget (220px fixed, left of waveform): track name inline edit, color swatch picker, Mute / Solo / Record Arm buttons with correct glow states, input source dropdown, gain + pan knobs, vertical 3D fader, Bus 1 / Bus 2 FX send knobs, EQ mini-graph click-to-open. *(ref: UX §2.5)*
  - **Status:** Complete
  - **Depends on:** Item 1.4 (MainMixerLayout scaffolding) ✓, Group 1 styling complete ✓
  - **What landed:** `project_model.py`, `app/ui/widgets/track_mixer_row.py`, and `echo_pro_app.py` now carry a full 220px channel-strip pass with inline name editing, color swatch, record-arm state, input-source selection, gain/pan/send controls, and EQ mini-graph button wiring. Bus send knobs now write through to persisted project track fields (`send_a`, `send_b`), input/EQ actions are wired to real callbacks, and the live Home arrangement now places strip and waveform surfaces side-by-side (DAW-standard channel-strip next to lane workflow). Non-recording channel-strip edits now participate in project undo/redo snapshots (volume, pan, mute, solo, color, input source, sends, and rename behavior).

- [x] **3.5** Implement Waveform Lane rendering: per-track color fill, center divider, magenta slice markers, rounded-corner clip rectangles with filename label, hover tooltip (duration + sample rate), right-click context menu (Rename / Duplicate / Delete / Export Clip / Send to Demucs / Send to ACE-Step / Properties). *(ref: UX §2.6, offline Phase 5)*
  - **Status:** Complete
  - **Depends on:** Item 1.4 (MainMixerLayout scaffolding) ✓, Item 2.1 (TimelineSyncController)
  - **What landed:** `timeline_widget.py` now renders track-color lane fills, center dividers, rounded clip bodies with filename labels, magenta slice markers from clip metadata, hover tooltips, and the full clip context-menu entry set. `echo_pro_app.py` now handles duplicate and Demucs/Music handoff actions from that menu, plus real rename/export/properties clip actions (rename persists as clip metadata display label, export copies source audio to a chosen destination, properties now includes inline name editing). Home-tab waveform scrolling and playhead updates are now bridged to `TimelineSyncController`, aligning the timeline viewport and ruler state model. Single-track interaction rule is now explicit in behavior: selecting a clip or clicking inside a lane sets that track as the active track context, keeping timeline edits and track-scoped controls synchronized.

- [x] **3.6** Add the "+ Add Track" button at the bottom of the channel strip column; wire the track-type dialog (Audio / AI Stem / MIDI / Bus). *(ref: UX §2.7)*
  - **Status:** Complete
  - **Depends on:** Item 3.4 (Channel Strip widget complete)
  - **Blockers:** None
  - **What landed:** `echo_pro_app.py` now adds a dedicated `+ Add Track` strip widget at the end of the live mixer channel-strip area. Clicking it opens a track-type selection dialog (Audio / AI Stem / MIDI / Bus) and creates a new track with type-specific defaults (name prefix, color, and input-source seed). The add-strip now enforces full channel-strip height with an anchored bottom CTA so the affordance consistently reads as "bottom of strip column" in the live mixer layout. `project_model.py` now persists `Track.track_type`, and the track list now surfaces non-Audio types (for example, `[MIDI]`, `[Bus]`) so typed-track intent remains visible after save/load. Non-Audio tracks now enforce lightweight runtime policy in `echo_pro_app.py`: locked input-source mapping by type and disallowed record-arm for AI Stem/MIDI/Bus tracks (treated as playback/routing-only in this build).

- [x] **3.7** Build the Right Sidebar (260px, collapsible): Browser tab with drag-and-drop file tree (hover shows name, duration, sample rate); Sessions tab with fixed-height rows, right-click context menu, and 500ms-hover truncation tooltip for long names. *(ref: UX §2.8, Decision 3)*
  - **Status:** Complete
  - **Depends on:** Item 1.4 (MainMixerLayout scaffolding) ✓
  - **Blockers:** CLARIFY Browser tree schema (see todo: g3-sidebar-browser-schema)
  - **What landed:** `app/ui/widgets/main_mixer_layout.py` now builds a real tabbed sidebar shell (`Browser` + `Sessions`) in `_build_sidebar()`. The Sessions tab now uses fixed-height list rows, a right-click context menu (open/rename/duplicate/delete), and delayed hover behavior that shows full names for truncated entries after 500ms. The Browser tab now includes a real audio tree (current project + project library + dropped files), hover metadata tooltips (name, duration, sample rate), explicit context actions (`Add to Selected Track`, `Add to New Audio Track`, `Reveal in Folder`, `Refresh Browser`), and external Explorer file-drop import flow with track-target selection. Browser add actions are wired into `TabbedEchoProWindow.add_clip_from_browser_path()`.
  - **Remaining:** Optional UX polish only (visual tuning and final copy); core 3.7 behavior is now implemented.

- [x] **3.8** Implement the Transport Bar (72px full-width, never resizes): left cluster (input device dropdown, monitoring toggle, gain slider); center cluster (seven 36×36px 3D bevel transport buttons, seek bar scoped to cluster width, dual time display — BARS:BEATS:TICKS + HH:MM:SS:MS — on recessed LCD panel); right cluster (loop toggle with amber glow, loop start/end inputs, metronome toggle with BPM mirror, punch-in/punch-out toggles). *(ref: UX §2.9)*
  - **Status:** Complete
  - **Depends on:** Item 1.4 (MainMixerLayout scaffolding) ✓, Group 1 styling (3D bevels, amber glow) ✓, Item 2.1 (TimelineSyncController)
  - **Blockers:** CLARIFY time display format and LCD styling (see todo: g3-transport-time-display)
  - **What landed:** `echo_pro_app.py` now wires a dedicated `mixer_transport_bar` into `MainMixerLayout.set_transport_bar(...)` so the Mixer tab owns a real transport surface. Recording button state and metronome-state syncing are now shared across both transport bars (Recording tab + Mixer tab) via common helpers. `app/ui/widgets/main_mixer_layout.py` now renders a clustered 72px Mixer transport shell: left cluster (input mirror, monitor toggle, gain slider), center cluster (seven-button transport row with jump-start/jump-end + core transport controls, seek slider, dual BARS:BEATS:TICKS + HH:MM:SS:MS readouts synced to `TimelineSyncController`), and right cluster (loop/click/punch toggles with loop and punch range inputs + apply action wired to `RecordingController`). Additional sync hooks now refresh Mixer transport controls when recording-side loop/punch/device state changes. Transport visuals were further polished toward the locked look: bevel-like button treatment, recessed LCD styling, and an amber-emphasis loop toggle with BPM mirror label next to metronome controls. `recording_controller.py` now persists explicit monitoring runtime state (`monitoring_enabled`, `monitor_gain_percent`), with Mixer monitor/gain controls writing to that state and status text reflecting monitor mode.

- [x] **3.9** Implement the Status Bar (24px): CPU bar + %, RAM, driver name, sample rate, buffer size, latency in cyan, project name, save-status dot (green = saved, amber = unsaved). *(ref: UX §2.10)*
  - **Status:** Complete
  - **Depends on:** Group 1 styling complete ✓
  - **What landed (2026-08-04):** `echo_pro_app.py` now builds persistent status widgets on the active tabbed-window path with fixed 24px bar height, CPU usage bar + %, RAM %, driver label, sample-rate label, buffer-size label, cyan latency readout, project-name label, and save-status dot/text (`Saved` green, `Unsaved` amber). A 1s telemetry timer now refreshes values from runtime state, and open/save/new project flows synchronize saved-state baseline for the indicator. Status telemetry wiring now uses selected sample rate and selected input/output devices, and host API names resolve to readable driver labels via `audio_device.py`.

---

### Group 4 — Waveform Interaction & Editing Correctness

Fix and complete the in-lane editing behaviors that the arrangement view depends on.

- [x] **4.1** Fix waveform zoom so users can reach close enough for clip-level inspection and editing; expose clear zoom-in / zoom-out controls and keyboard shortcuts (Ctrl+Scroll). *(ref: UX §10, existing P1 brief)*
  - **Status:** Complete
  - **Blockers:** None
  - **Decision (2026-08-04, common DAW baseline):** Use horizontal zoom range 1/16x to 16x for normal arrangement work, with fine-zoom extension up to 64x for detailed waveform inspection. Apply `Ctrl+Scroll` incremental zoom around cursor/playhead with ~1.25x step, plus explicit zoom-in/zoom-out controls and a visible zoom percentage/readout.
  - **What landed (2026-08-04):** `timeline_widget.py` now supports dynamic zoom factor scaling and Ctrl+Scroll zoom requests; `echo_pro_app.py` now wires zoom requests through `TimelineSyncController` with cursor-anchored zoom and adds explicit Home waveform zoom controls (`-`, `+`, `100%`) plus readout updates and shortcuts (`Ctrl+-`, `Ctrl+=`, `Ctrl+0`); `timeline_sync_controller.py` zoom limits now follow the DAW baseline (min 1/16x, max 64x).

- [x] **4.2** Fix skip-forward / skip-reverse so they fall back to a stable position when no region is selected; add click-based selection start/end editing directly on the waveform surface. *(ref: existing P1 brief)*
  - **Status:** Complete
  - **Known issue:** Addressed in active tabbed path.
  - **What landed (2026-08-04):** `echo_pro_app.py` now treats Jump Start/End as selection/clip boundary jumps when a target exists, and as stable relative skip controls when no region is selected (fallback step = one bar computed from current BPM/time signature, clamped to timeline bounds). `timeline_widget.py` now supports click-based range edge editing directly on the waveform lane (`Alt+click` adjusts selection start, `Shift+click` adjusts selection end), and emits range-change callbacks so `comp_start_sec_input` / `comp_end_sec_input` stay synchronized with timeline edits.

- [x] **4.3** Implement inline automation curve overlays directly in the waveform lane: parameter selector dropdown on channel strip, cyan dot handles, double-click to add nodes, drag to move, no separate dock panel (locked for v1.0). *(ref: UX §2.6, Decision 1, offline Phase 6)*
  - **Status:** Complete
  - **Blockers:** None
  - **What landed (2026-08-04):** `app/ui/widgets/track_mixer_row.py` now includes a per-channel automation parameter selector (`Auto: Volume`, `Auto: Pan`, `Auto: Send A`, `Auto: Send B`) wired to `TabbedEchoProWindow`. `timeline_widget.py` now renders inline cyan automation overlays directly in each waveform lane for the active per-track parameter, with cyan dot handles, double-click node insertion, and drag-to-move interaction constrained/sorted by neighbor nodes. `echo_pro_app.py` now persists per-track automation points and active target parameter through `TrackPlaybackSettings` and project save/load (`project_model.py`), syncs overlay state on timeline refresh, and records automation edits into project undo/redo snapshots. No separate automation dock/panel was added.

- [x] **4.4** Implement clip fade settings: 6px drag handles on clip edges plus a right-click "Fade Settings…" non-modal popover (Fade In / Fade Out ms inputs, Linear / Exp / Log / S-curve dropdown per fade). Drag handle and popover must stay in real-time sync. *(ref: UX Decision 6)*
  - **Status:** Complete
  - **Blockers:** None
  - **What landed (2026-08-04):** `timeline_widget.py` now draws 6px fade handles on selected clip edges, renders inline fade ramps, and supports drag-updating `fade_in_ms` / `fade_out_ms` directly in the lane. Right-click clip context now includes `Fade Settings…`, routed through `echo_pro_app.py` to a non-modal `ClipFadeSettingsPopover` with Fade In/Fade Out ms and per-side curve selectors (Linear/Exp/Log/S-curve). Drag and popover now stay synchronized in real time through shared clip metadata updates and callback syncing; closing the popover commits one project-history snapshot when values changed.

- [x] **4.5** Add double-click on a waveform/track to open a focused single-track editor surface, passing the correct track context without disturbing the rest of the project. *(ref: existing P2 brief)*
  - **Status:** Complete
  - **Decision (2026-08-04, common DAW-style workflow):** Open a dedicated in-app `Track Editor` tab that focuses one track context while keeping all other project state and tabs intact.
  - **What landed (2026-08-04):** `timeline_widget.py` now emits track double-click callbacks (double-click clip body or left track-lane header zone). `echo_pro_app.py` now routes that callback to `open_single_track_editor(track_index)` in `TabbedEchoProWindow`, which opens/reuses a focused Track Editor tab with track summary and clip list scoped to the selected track, plus quick actions for jumping playhead to first clip and opening playback settings for that track only. Existing timeline and project surfaces remain available and unchanged.

<!-- Decision resolved on 2026-08-04: use dedicated Track Editor tab for focused single-track workflow. -->

---

### Group 5 — Audio Mixing Engine

- [x] **5.1** Implement multi-channel audio summing: mix per-track float buffers with individual gain values into the master output buffer in a vectorizable form; wire into the playback path. *(ref: offline Phase 7)*
  - **Status:** Complete
  - **Decision (2026-08-04):** Use NumPy-first vectorized summing in the existing `playback_mixer.py` render path (no compiled extension yet), preserving current playback/export entrypoints.
  - **What landed (2026-08-04):** `playback_mixer.py` now groups clips by track before rendering, applies per-clip in-lane fade metadata (`fade_in_ms`/`fade_out_ms`), keeps per-track processing passes (loop/effects/fades), then applies per-track gain + equal-power pan and accumulates into a float64 master buffer before limiter/clip to float32. Existing playback/export wiring (`play_project`, `mix_project_to_segment`, `export_project_mix_dialog`) remains unchanged and now uses the upgraded summing path automatically.
  - **Known issue:** Track FX reliability edge cases remain in scope for 5.2.

- [x] **5.2** Make track FX and playback parameter changes apply reliably and audibly during active playback; clearly communicate any deliberate defer-to-next-buffer behavior. *(ref: existing P1 brief)*
  - **Status:** Complete
  - **What landed (2026-08-04):** `echo_pro_app.py` now performs a controlled active-playback remix/restart from the current playhead (`_refresh_active_project_playback_mix(...)`) whenever committed track playback parameters change (volume/pan/mute/solo/send, automation edits, clip fade commit, and playback settings dialog apply). This keeps edits audibly reliable during ongoing playback in the current non-streaming architecture. For high-frequency fade popover edits, the app now explicitly communicates deferred apply behavior while the popover is open, then applies/remixes on close.
  - **Notes:** Implementation intentionally remixes from current playhead for reliability with the existing pre-render playback model.

- [x] **5.3** Make the Master Section live during playback: waveform updates, dual VU meter bars respond, LUFS integrated reading updates, peak indicators react. *(ref: UX §2.3, existing P2 brief)*
  - **Status:** Complete
  - **What landed (2026-08-04):** `echo_pro_app.py` now caches the active playback segment and updates master telemetry every playback poll from the rendered audio window (left/right RMS VU, peak dB indicators, integrated loudness proxy, and waveform preview glyphs). `app/ui/widgets/main_mixer_layout.py` now exposes dedicated playback-metric update/reset hooks and displays peak indicators plus waveform preview in the Master section. Recording-meter updates no longer override master playback telemetry while project playback is active.
  - **Notes:** Uses the existing pre-render playback architecture, with timeline-poll-driven master visualization updates.

---

### Group 6 — New Project Dialog

- [x] **6.1** Implement the New Project modal dialog (Ctrl+N / File → New Project): project name field (auto-focus), folder selector, visual template grid (Empty / Basic 4-Track / Podcast / Beat Maker / AI Stems Session), sample rate dropdown, BPM field, "Create Project" cyan primary button + "Cancel". *(ref: UX Screen 7)*
  - **Status:** Complete
  - **What landed (2026-08-04):** Added `app/ui/dialogs/new_project_dialog.py` with a real New Project modal (auto-focus name input, folder browse selector, visual template tile grid, sample-rate dropdown, BPM spinner, and Create/Cancel buttons with cyan primary CTA styling). `echo_pro_app.py` now routes `new_project()` through this modal, creates template-specific track layouts (Empty / Basic 4-Track / Podcast / Beat Maker / AI Stems Session), applies BPM + sample-rate through the existing recording and timeline controller wiring, and stores project defaults (`project_template`, `project_sample_rate`, `project_tempo_bpm`, `project_folder`) in project metadata.
  - **Notes:** Save/Open/Browse flows now maintain the active project folder context so Save defaults to the selected/loaded project directory.

---

### Group 7 — AI Tab: Demucs Stem Extraction

- [x] **7.1** Create the "Stem Separation (Demucs)" full-page tab: left panel (drag-and-drop source zone, separation model dropdown with stem-count labels and "Manage Models…" link, device selector with auto-detect, inline VRAM color indicator, Force CPU checkbox, shifts spinner, two-stem mode, output format / sample rate / normalize settings). *(ref: UX §3.2–3.4)*
  - **Status:** Complete
  - **What landed (2026-08-04):** `echo_pro_app.py` now adds a dedicated full-page `Stem Separation` tab in the active tabbed window path, with a three-column workspace and a full left control panel matching UX scope: drag-and-drop source zone (plus browse fallback), Demucs model selector with stem-count labels, `Manage Models...` entry point, device selector (Auto/CUDA/CPU), inline color-coded capability indicator, `Force CPU` toggle, shifts spinner, two-stem mode selector, and output format/sample-rate/normalize controls. Existing stem backend/status/activity wiring was reused and updated so source selection and runtime readiness telemetry sync across the new tab.
  - **Notes:** Tools tab now links users to the dedicated Stem Separation page; Demucs run/progress/transfer enhancements continue in 7.2-7.5.
- [x] **7.2** Implement the Demucs run controls: full-width "Separate" button (green ready / amber pulsing during processing), "Cancel" button (appears during processing only); wire to background Demucs worker with signal callbacks. *(ref: UX §3.5, offline Phase 4)*
  - **Status:** Complete
  - **What landed (2026-08-04):** `echo_pro_app.py` now runs Demucs separation through a dedicated `StemSeparationWorker` on a `QThread` with signal callbacks (`progress`, `completed`, `failed`, `cancelled`). The Stem Separation tab now uses a full-width green `Separate` button in ready state, switches to an amber pulsing processing state while a run is active, and shows a `Cancel` button only during active processing. Completion/failure/cancel callbacks update status/activity UI and preserve existing stem-import behavior into project tracks.
  - **Safety fix:** Added worker shutdown handling on app close to avoid orphaned running Demucs worker threads.
- [x] **7.3** Build the center progress area: overall progress bar with states (Idle / Loading model… / Processing… / Complete), per-stem progress bars with labels, elapsed time + ETA, terminal-style activity log (green / amber / red color scheme, auto-scroll, timestamps, Copy / Save / Clear / filter toolbar). *(ref: UX §3.6–3.7)*
  - **Status:** Complete
  - **What landed (2026-08-04):** `echo_pro_app.py` now includes a full center progress surface in the Stem Separation tab: explicit state label lifecycle (idle/loading/processing/complete), overall progress bar, per-stem progress bars, elapsed+ETA updates, and an activity log panel with timestamped entries, severity-aware row styling, auto-scroll, filter dropdown, and Copy/Save/Clear actions.
- [x] **7.4** Build the post-completion output preview section: per-stem waveform thumbnail rows with Play button and volume knob. *(ref: UX §3.8)*
  - **Status:** Complete
  - **What landed (2026-08-04):** `echo_pro_app.py` now renders post-run per-stem preview rows from the latest separation results, including waveform glyph preview, per-row play/stop action, and per-stem preview volume control.
- [x] **7.5** Implement the right Transfer Options panel: "Send to Main Tracks" raised tile card (insert position sub-options, auto-color-code toggle), "Save to Project Folder" tile card (path + subfolder pattern), per-stem output checklist with file sizes, "→ Transfer to ACE-Step" secondary button, primary Transfer button with cyan glow. *(ref: UX §3.9, Decision 7)*
  - **Status:** Complete
  - **What landed (2026-08-04):** `echo_pro_app.py` now provides full transfer controls: checked-stem transfer list with size readout, insert-position option (top/append), auto-color-code toggle, save/copy-to-project folder controls with subfolder pattern, ACE-Step handoff action, and primary transfer action wired into project track insertion/update flows.

---

### Group 8 — AI Tab: ACE-Step Generation

- **Status (2026-08-04):** Complete in the Python UI path. `echo_pro_app.py` now includes the full ACE-Step page with model/LoRA selection, chip inputs with suggestions, audio-reference source + trim/influence controls, complete generation settings, prompt/negative/lyrics areas, processing-state UX, metadata-consistent result cards, quick rerun actions, and bidirectional ACE↔Demucs transfer handoff.

- **Finish plan (to close Group 8):**
  - [x] **8P.1 Chip UX completion:** popup typeahead suggestions + compact scroll lanes are now in place, with chip add/remove and clear-all behavior wired.
  - [x] **8P.2 Audio-reference trimming pass:** reference start/end fields now validate numeric/non-negative input, selected range is shown in the preview label, and generation calls persist reference trim/source/path metadata in `generation_payload`.
  - [x] **8P.3 Generate-state polish:** Generate now pulses amber during processing with ETA text shown inline; idle style/text restore correctly after completion/failure.
  - [x] **8P.4 Transfer parity with Demucs:** "Send to Demucs" now routes through selected-result handoff with file-existence validation, pre-seeds stem source/output context, and keeps ACE/Demucs transfer options synchronized bidirectionally.
  - [x] **8P.5 Results-card metadata consistency:** result entries now persist normalized output format/sample-rate fields, cards display seed/duration/format/sample-rate consistently, and quick actions re-apply output/reference metadata to generation controls before rerun.
  - [x] **8P.6 Close criteria:** executed `python -m py_compile echo_pro_app.py music_generator.py t2m_interface.py` plus `tools/dev/run_ui_smoke_checks.bat`; smoke harness now includes `ace_generation_flow` (generate → play/loop/favorite → quick rerun → transfer + Demucs handoff) and passed without exceptions.

- [x] **8.1** Create the "AI Generation (ACE-Step)" full-page tab: model dropdown (checkpoint discovery from models dir, type badges), LoRA adapter dropdown with "+ Add Custom LoRA…", inline VRAM indicator, Force CPU checkbox. *(ref: UX §4.2)*
- [x] **8.2** Implement Style Tags and Instruments pill inputs: type-and-Enter pill creation, suggestion dropdown while typing, × removal per pill, 12-pill visible max with scroll, "Clear All" link; "No specific instruments" checkbox. *(ref: UX §4.3–4.4)*
- [x] **8.3** Implement Audio Reference section: source dropdown (None / Upload / Active Track / Last Demucs Stem), waveform thumbnail, Influence Strength slider (0.0–1.0), start/end time fields. *(ref: UX §4.5)*
- [x] **8.4** Expose all Generation Settings controls: Duration slider+input (5–300s), Steps (10–150), CFG scale (1.0–20.0), Seed + randomize dice, Lock seed checkbox, Scheduler dropdown (Euler / Euler Ancestral / DPM++ 2M / DPM++ SDE / DDIM / PNDM), ERG weight, ELA weight (grayed without lyrics), Batch count (1–8) with estimated time, Output format. *(ref: UX §4.6)*
- [x] **8.5** Build the right column prompts area: main textarea (min 5 lines), collapsible negative prompt, collapsible line-numbered lyrics field; full-width Generate button (green idle / amber pulsing processing with ETA); collapsible real-time terminal log. *(ref: UX §4.7–4.8)*
- [x] **8.6** Build results grid: waveform thumbnail cards with duration, seed, Play, Loop, star/favorite; quick-action row (Regenerate same/new seed, Vary subtle/strong); Transfer panel mirroring Demucs transfer options plus "Send to Demucs" tile. *(ref: UX §4.9–4.10)*

---

### Group 9 — Mastering Chain Page

- **Status (2026-08-04):** Complete in the Python UI path. `echo_pro_app.py` now includes the full Mastering tab signal chain, persisted per-block controls, bypass toggles, compressor VU/gain-reduction meters, limiter clip/true-peak readout, live LUFS history chart with target line, and integrated color-state feedback against target.

- [x] **9.1** Build the mastering chain full-page view: horizontal 3D raised-card signal chain — Input Trim → 4-Band Parametric EQ (visual frequency curve) → Compressor (threshold / ratio / attack / release / knee / makeup, VU meters) → Stereo Widener → Limiter (threshold / ceiling / release, clip LED, true peak readout) → Output. Bypass button per block (red glow when bypassed). Arrow connectors between blocks. *(ref: UX §5.1, offline Phase 8)*
- [x] **9.2** Implement the LUFS meter panel: Integrated / Short-term / Momentary / LU Range / True Peak readouts in cyan monospace; target preset dropdown (Spotify −14 / YouTube −16 / EBU R128 −23 / ATSC −24 / Custom); dashed amber target line on LUFS history scrolling chart; Integrated readout color-coded green/amber/red vs target. *(ref: UX §5.2, Decisions 5)*

<!-- REVISIT: The offline blueprint has C++ mastering_chain.cpp (atomic bypass). Confirm before 9.1 whether the Python implementation uses numpy DSP or calls a compiled extension — this changes the scope of 9.1 significantly. -->

---

### Group 10 — MIDI Hardware Mapping Page

- [ ] **10.1** Build the MIDI mapping page three-panel layout: left device list (status dot, channel dropdown, Refresh button); center mappings table (Parameter / Current Value / CC / Channel / Min / Max / Curve / Learn columns, grouped by category); right MIDI Learn console (scrolling monospace monitor, Learn toggle, confirmation card for new mappings, amber "MIDI Learn Active" banner). *(ref: UX §6.1–6.3, offline Phase 11)*
- [ ] **10.2** Wire the background MIDI input worker thread: poll active input port at ~500Hz, translate CC 0–127 to normalized 0.0–1.0, emit to parameter bindings; implement MIDI Learn assignment flow. *(ref: offline Phase 11)*

---

### Group 11 — Settings Page

- [ ] **11.1** Build the Settings full-page tab with left sidebar navigation (200px): Audio Engine section (backend dropdown, input/output device dropdowns, sample rate / buffer size / bit depth selectors, latency readout, test-tone button, driver status indicator). *(ref: UX §7.1)*
- [ ] **11.2** Implement the Model Manager section with Demucs and ACE-Step sub-tabs: installed models table with per-row Set Default and Remove (confirm dialog); "Add from Folder…" with format validation; "Add from URL…" with inline download progress; drag-and-drop install zone; model details pane on row selection. *(ref: UX §7.2)*
- [ ] **11.3** Add Appearance, Keyboard Shortcuts (searchable / reassignable table with Reset All), Project Defaults, and About sections. *(ref: UX §7.3–7.6)*

<!-- REVISIT: Keyboard shortcuts in §11.3 must be reconciled with the shortcut bindings task (Group 12). Decide whether shortcuts are stored per-user in a config file or hardcoded with an override layer before implementing the reassignment table. -->

---

### Group 12 — Keyboard Shortcuts & UI State Machine

- [ ] **12.1** Wire all documented keyboard shortcut bindings: Space (play/stop), R (record), Home / End (skip to start/end), Ctrl+Z / Ctrl+Y (undo/redo), Ctrl+S (save), Delete (delete clip), S (split at playhead), Ctrl+T (new track), M (mute), Alt+S (solo), Ctrl+Scroll (zoom), Tab (switch panels), Ctrl+D (Demucs), Ctrl+E (ACE-Step), Ctrl+M (Mastering), Ctrl+L (MIDI Learn), Ctrl+N (new project), Ctrl+O (open), Ctrl+Shift+E (export). *(ref: UX §10)*
- [ ] **12.2** Implement the full UI state machine: Idle/No Project (grayed controls, welcome panel), Project Open/Stopped (controls active), Playing (Play glows green, seek animates, playhead moves), Recording (Record pulses red, armed track red borders, live waveform draw, dim non-armed tracks, REC badge in status bar), AI Processing (amber progress indicator in status bar, click to jump to active AI tab), MIDI Learn Mode (amber banner, assignable parameters amber glow), Unsaved Changes (amber dot + title bar asterisk). *(ref: UX §9)*

---

### Group 13 — Control Polish & Icon Consistency

- [ ] **13.1** Standardize all icon button sizing and spacing: 36×36px for transport, consistent size across Home and Recording flows, hover-tooltip labels for all icon-only controls, larger hit targets where noted. *(ref: existing P2 brief)*
- [ ] **13.2** Control sizing and layout cleanup pass: ensure control clusters use fixed bounding boxes, buttons are 8px apart within clusters, no control stretches to fill space. *(ref: UX §1.9)*

---

### Group 14 — Developer Infrastructure & Launch Reliability

- [ ] **14.1** Fix the non-debug source launch path so `Start_Echo.bat` and the VS Code shell task reliably surface the PySide window; document the preferred developer launch path. *(ref: existing P2 brief)*
- [ ] **14.2** Add a runtime environment health check and recovery path for `%LOCALAPPDATA%\EchoProData\runtime\venv`; document the reset/resync procedure for contributors. *(ref: existing P3 brief)*
- [ ] **14.3** Define and document the repeatable packaged-launcher validation path for contributors who do not have `EchoPro.exe` in their source checkout. *(ref: existing P3 brief)*

---

### Group 15 — Documentation Alignment

- [ ] **15.1** Mark or update stale internal status docs (`docs/internal/`) so contributors can quickly identify which documents are authoritative vs historical; link to TASK_HUB.md as the active source. *(ref: existing P4 brief)*

---

## Ideas

- Plain non-debug Echo Pro launch flow that is as reliable as the current VS Code debug launch.
- Phase 6 installer validation and packaged-launch verification.
- Broader recording and device-startup polish if audio-device refresh continues to feel slow or fragile on startup.
- Real-device recording sanity pass before any release-oriented packaging or rollout.
- Explore a vertical beside-the-track mixer/control layout instead of the current separate mixer section.

## Todos

- Active backlog work is tracked in the Ordered Build Task List above. This section is kept only for ad hoc notes that do not belong in the phased build list.

## Problems

- Source checkouts do not include `EchoPro.exe`, so the portable packaged launcher path cannot be validated from this repo alone.
- A shell task can start the Echo Pro runtime Python process without reliably surfacing the PySide window, which is why the debug launch path is currently preferred.
- Echo Pro runtime dependencies live outside the repo under `%LOCALAPPDATA%\\EchoProData\\runtime\\venv`, so launch reliability can drift if that environment gets out of sync.
- Older internal status docs can drift from the repo's current runtime and launch reality, so this file should be treated as the actively maintained task snapshot.

## Implementation Briefs

### Reliable non-debug launch from source

- **Priority:** P2
- **Feature definition:** Investigate and fix the shell-task launch path so starting Echo Pro from source reliably surfaces the PySide window instead of only spawning the runtime Python process.
- **User-visible behavior:** A contributor can use a normal non-debug launch flow from the repo and see the app window appear consistently, without having to fall back to the debug launcher for routine startup.
- **Out of scope:** No debugger-specific improvements, no packaged-launch work except where it shares the same root cause, and no broad task-system rewrite unless it is needed to make the launch path dependable.
- **Likely affected areas:** [.vscode/tasks.json](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/.vscode/tasks.json), [.vscode/launch.json](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/.vscode/launch.json), [echo_pro_app.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/echo_pro_app.py), startup scripts, and runtime bootstrap behavior.
- **Done when:** The non-debug source launch path consistently opens the main window, the root cause for the missing-window behavior is understood, and the preferred launch workflow is documented based on the actual result.

### Runtime environment drift detection and recovery

- **Priority:** P3
- **Feature definition:** Reduce failures caused by the external runtime virtual environment drifting out of sync by adding a clearer verification and recovery path for `%LOCALAPPDATA%\\EchoProData\\runtime\\venv`.
- **User-visible behavior:** When the runtime environment is stale or broken, contributors get a clear way to detect it and recover rather than encountering mysterious launch failures or inconsistent behavior.
- **Out of scope:** No move to fully repo-local runtime dependencies unless later work explicitly chooses that direction, and no speculative environment-manager migration.
- **Likely affected areas:** [README.md](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/README.md), runtime/setup scripts, VS Code launch preparation tasks, and any startup checks that can validate runtime health before launch.
- **Done when:** The runtime dependency location and health-check process are documented, contributors have a concrete reset or resync path, and launch troubleshooting can distinguish code issues from environment drift quickly.

### Packaged launcher validation without repo-shipped EchoPro.exe

- **Priority:** P3
- **Feature definition:** Define and implement a repeatable validation path for the portable packaged launcher even when source checkouts do not include [EchoPro.exe](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/EchoPro.exe).
- **User-visible behavior:** Contributors can tell whether they are validating the packaged launcher, the source launch path, or both, without assuming the repo alone is enough to exercise the packaged flow.
- **Out of scope:** No full installer pipeline redesign, no requirement to commit packaged binaries into the repo, and no release automation work beyond what is needed for a reliable validation path.
- **Likely affected areas:** [README.md](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/README.md), developer launch/setup docs, packaging notes, and any scripts or config that point contributors to the packaged runtime location.
- **Done when:** The expected packaged-launch prerequisites are documented, the validation path is explicit, and contributors can follow one clear process to verify packaged-launch behavior without guessing where the executable should come from.

### Active-status documentation alignment

- **Priority:** P4
- **Feature definition:** Align older internal status documents with the current repo reality so contributors do not mistake stale launch/runtime notes for the active project state.
- **User-visible behavior:** Contributors can quickly identify which project documents are authoritative and are less likely to follow outdated instructions or backlog assumptions.
- **Out of scope:** No full documentation rewrite and no archival cleanup beyond what is needed to mark or update drift-prone status documents.
- **Likely affected areas:** [TASK_HUB.md](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/TASK_HUB.md), [docs/internal/PHASE_1_TO_5_KNOWN_ISSUES_TODO.md](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/docs/internal/PHASE_1_TO_5_KNOWN_ISSUES_TODO.md), [README.md](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/README.md), and any other status snapshot docs that still describe superseded workflows.
- **Done when:** Stale status docs are either updated, explicitly marked as historical, or linked back to [TASK_HUB.md](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/TASK_HUB.md) as the active source of truth, so project-state drift is visibly reduced.

---

## Recently Completed

- Extracted major `TabbedEchoProWindow` GUI construction (`_build_ui`, Home/Recording/Voice tab builders, scroll wrapper, and timeline add-clip handler) into [app/ui/tabbed_window_layout.py](app/ui/tabbed_window_layout.py), leaving `echo_pro_app.py` with thin delegating methods for cleaner structure and easier maintenance.
- Completed phase-2 GUI extraction by moving remaining tab builders (ACE-Step, Mastering Chain, Demucs, Tools, and Help filtering helpers) into [app/ui/tabbed_window_layout.py](app/ui/tabbed_window_layout.py), with `TabbedEchoProWindow` methods in [echo_pro_app.py](echo_pro_app.py) now delegating to module helpers.
- Removed the now-unused `TabbedEchoProWindow._filter_help_text` wrapper from [echo_pro_app.py](echo_pro_app.py) and wired Help search directly to `filter_help_text` in [app/ui/tabbed_window_layout.py](app/ui/tabbed_window_layout.py) to keep layout logic centralized.
- Moved Help guide HTML content ownership from [echo_pro_app.py](echo_pro_app.py) into `HELP_GUIDE_HTML` inside [app/ui/tabbed_window_layout.py](app/ui/tabbed_window_layout.py), then removed the obsolete `_help_guide_html` class method.
- Confirmed that the project-playback freeze issue is no longer reproducing in manual playback checks.
- Added a [cleanup prompt](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/.github/prompts/cleanup.prompt.md) for archiving obsolete files and reducing project-folder clutter safely.
- Converted the main Home controls plus the Recording tab's transport, setup, take-review, and comp/recovery actions to compact icon-style buttons with hover labels as a first pass on the broader control declutter work.
- Removed developer-only phase-5 regression actions from general user-facing tabs and aligned the phase implementation prompt with the repo instructions.
- Fixed the active tabbed Home UI path so playback transport controls actually render and source launches export the Echo Pro data root consistently.
- Added a root-level [Start_Echo.bat](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/Start_Echo.bat) launcher that bootstraps the runtime venv, ensures core app packages are present, and starts Echo Pro from source.
- Added Home-tab playback transport controls with non-blocking play/stop, a visible playhead, and jump-to-selection-or-clip navigation.
- Added a dedicated Home-tab Demucs stem-splitting section with source/model controls plus clearer launch, progress, completion, and dependency feedback.
- Fixed a startup regression in the active tabbed Echo Pro window by restoring the new stem-workflow state on the real launch path.
- Added this repo-level task hub file plus a Copilot skill/instruction hook so backlog work has a single default home.
- Added a dedicated [task-hub prompt](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/.github/prompts/task-hub.prompt.md) for quick backlog review and updates.
- Added a README pointer so contributors can find [TASK_HUB.md](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/TASK_HUB.md) quickly.
- Added persisted per-track playback settings for fades, loop regions, and starter effects.
- Added compact per-track playback settings UI and timeline markers/badges.
- Added repo Copilot prompts and instructions tailored to EchoApp workflow.
- Added VS Code runtime preparation task and a working debug launch configuration for Echo Pro.

## Source Notes

The initial contents here were seeded from:

- recent completed work in this repository,
- current launch/runtime investigation results,
- and the backlog direction in [docs/internal/PHASE_1_TO_5_KNOWN_ISSUES_TODO.md](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/docs/internal/PHASE_1_TO_5_KNOWN_ISSUES_TODO.md).
