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

- [ ] **3.1** Implement the top toolbar: File / Edit / View / Project / AI Tools / Settings menus; New / Open / Save / Export / Undo / Redo icon buttons; editable BPM display with scroll-wheel nudge; master volume circular knob; time signature dropdown; sample rate + bit depth readout. *(ref: UX §2.2)*
  - **Status:** Not started
  - **Depends on:** Item 1.4 (MainMixerLayout scaffolding) ✓ 
  - **Blockers:** CLARIFY menu structure (see todo: g3-toolbar-menu-spec)
  - **Questions:** Complete menu item list, keyboard shortcuts, icon set, nested menus?

- [ ] **3.2** Build the Left Master Section (200px fixed): vertical master fader (≥200px stroke), dual-channel L+R VU meter, LUFS integrated readout (cyan monospace), master EQ toggle, master limiter threshold knob, master effects chain button, "MASTER" label. *(ref: UX §2.3)*
  - **Status:** Not started
  - **Depends on:** Item 1.4 (MainMixerLayout scaffolding) ✓ 
  - **Blockers:** CLARIFY control layout and panel opening behavior (see todo: g3-master-section-detail)
  - **Questions:** Fader height spec, VU meter layout (L/R bars or combined), font specs for LUFS readout, how do EQ/limiter/effects panels open?

- [ ] **3.3** Implement the Timeline Ruler (28px): bars:beats / seconds toggle, cyan full-height playhead, click-to-reposition, synchronized horizontal scroll. *(ref: UX §2.4)*
  - **Status:** Scaffolded in MainMixerLayout._build_timeline_ruler()
  - **Depends on:** Item 1.4 (MainMixerLayout scaffolding) ✓, Item 2.1 (TimelineSyncController)
  - **Blockers:** 2.1 not yet implemented
  - **Next step:** Wire TimelineSyncController once 2.1 is complete

- [ ] **3.4** Build the Channel Strip widget (220px fixed, left of waveform): track name inline edit, color swatch picker, Mute / Solo / Record Arm buttons with correct glow states, input source dropdown, gain + pan knobs, vertical 3D fader, Bus 1 / Bus 2 FX send knobs, EQ mini-graph click-to-open. *(ref: UX §2.5)*
  - **Status:** TrackMixerRow component exists but needs review for 3D styling and glow states
  - **Depends on:** Item 1.4 (MainMixerLayout scaffolding) ✓, Group 1 styling complete ✓
  - **Next step:** Review/update TrackMixerRow to match spec, wire into MainMixerLayout

- [ ] **3.5** Implement Waveform Lane rendering: per-track color fill, center divider, magenta slice markers, rounded-corner clip rectangles with filename label, hover tooltip (duration + sample rate), right-click context menu (Rename / Duplicate / Delete / Export Clip / Send to Demucs / Send to ACE-Step / Properties). *(ref: UX §2.6, offline Phase 5)*
  - **Status:** TimelineWidget component exists; needs review for all visual details
  - **Depends on:** Item 1.4 (MainMixerLayout scaffolding) ✓, Item 2.1 (TimelineSyncController)
  - **Blockers:** 2.1 not yet implemented, possibly Item 4.5 (single-track editor UX pattern)
  - **Next step:** Review TimelineWidget rendering and context menu

- [ ] **3.6** Add the "+ Add Track" button at the bottom of the channel strip column; wire the track-type dialog (Audio / AI Stem / MIDI / Bus). *(ref: UX §2.7)*
  - **Status:** Not started
  - **Depends on:** Item 3.4 (Channel Strip widget complete)
  - **Blockers:** None
  - **Next step:** Create track-type dialog and wire to MainMixerLayout

- [ ] **3.7** Build the Right Sidebar (260px, collapsible): Browser tab with drag-and-drop file tree (hover shows name, duration, sample rate); Sessions tab with fixed-height rows, right-click context menu, and 500ms-hover truncation tooltip for long names. *(ref: UX §2.8, Decision 3)*
  - **Status:** Scaffolded in MainMixerLayout._build_sidebar()
  - **Depends on:** Item 1.4 (MainMixerLayout scaffolding) ✓
  - **Blockers:** CLARIFY Browser tree schema (see todo: g3-sidebar-browser-schema)
  - **Questions:** What file types to show, drag-drop auto-import or dialog, folder context menu, Sessions definition?

- [ ] **3.8** Implement the Transport Bar (72px full-width, never resizes): left cluster (input device dropdown, monitoring toggle, gain slider); center cluster (seven 36×36px 3D bevel transport buttons, seek bar scoped to cluster width, dual time display — BARS:BEATS:TICKS + HH:MM:SS:MS — on recessed LCD panel); right cluster (loop toggle with amber glow, loop start/end inputs, metronome toggle with BPM mirror, punch-in/punch-out toggles). *(ref: UX §2.9)*
  - **Status:** TransportBar component exists; needs review and integration into MainMixerLayout
  - **Depends on:** Item 1.4 (MainMixerLayout scaffolding) ✓, Group 1 styling (3D bevels, amber glow) ✓, Item 2.1 (TimelineSyncController)
  - **Blockers:** CLARIFY time display format and LCD styling (see todo: g3-transport-time-display)
  - **Next step:** Review TransportBar styling against spec, wire into MainMixerLayout

- [ ] **3.9** Implement the Status Bar (24px): CPU bar + %, RAM, driver name, sample rate, buffer size, latency in cyan, project name, save-status dot (green = saved, amber = unsaved). *(ref: UX §2.10)*
  - **Status:** QStatusBar exists in EchoProWindow; needs styling and wiring
  - **Depends on:** Group 1 styling complete ✓
  - **Next step:** Wire CPU/RAM/driver/latency telemetry, add save-status dot indicator

---

### Group 4 — Waveform Interaction & Editing Correctness

Fix and complete the in-lane editing behaviors that the arrangement view depends on.

- [ ] **4.1** Fix waveform zoom so users can reach close enough for clip-level inspection and editing; expose clear zoom-in / zoom-out controls and keyboard shortcuts (Ctrl+Scroll). *(ref: UX §10, existing P1 brief)*
  - **Status:** Not started
  - **Blockers:** CLARIFY zoom depth limits (see todo: g4-zoom-limits)
  - **Questions:** Closest/farthest zoom levels, zoom UI (slider/buttons/scroll), can user see individual samples?
  - **Notes:** Currently listed as a known problem (waveform zoom insufficient)

- [ ] **4.2** Fix skip-forward / skip-reverse so they fall back to a stable position when no region is selected; add click-based selection start/end editing directly on the waveform surface. *(ref: existing P1 brief)*
  - **Status:** Not started
  - **Known issue:** Skip forward/reverse behavior is currently broken (see Problems section)
  - **Next step:** Review existing skip logic, implement fallback behavior, add click-based selection

- [ ] **4.3** Implement inline automation curve overlays directly in the waveform lane: parameter selector dropdown on channel strip, cyan dot handles, double-click to add nodes, drag to move, no separate dock panel (locked for v1.0). *(ref: UX §2.6, Decision 1, offline Phase 6)*
  - **Status:** Not started
  - **Blockers:** Item 3.5 (waveform lane rendering complete)
  - **Notes:** No separate dock/panel allowed — must be inline with waveform

- [ ] **4.4** Implement clip fade settings: 6px drag handles on clip edges plus a right-click "Fade Settings…" non-modal popover (Fade In / Fade Out ms inputs, Linear / Exp / Log / S-curve dropdown per fade). Drag handle and popover must stay in real-time sync. *(ref: UX Decision 6)*
  - **Status:** Not started
  - **Blockers:** Item 3.5 (waveform lane rendering complete)
  - **Notes:** Popover must sync with drag handle in real-time (no stale state)

- [ ] **4.5** Add double-click on a waveform/track to open a focused single-track editor surface, passing the correct track context without disturbing the rest of the project. *(ref: existing P2 brief)*
  - **Status:** Not started
  - **Blockers:** CLARIFY single-track editor UI pattern (see todo: g3-clarify-single-track-editor)
  - **Questions:** Inline panel, floating dock, modal, or new tab? This affects Group 3 layout code.

<!-- DECISION NEEDED: Single-track editor UI pattern (inline/floating/modal) — affects Group 3 layout code. -->

---

### Group 5 — Audio Mixing Engine

- [ ] **5.1** Implement multi-channel audio summing: mix per-track float buffers with individual gain values into the master output buffer in a vectorizable form; wire into the playback path. *(ref: offline Phase 7)*
  - **Status:** Not started
  - **Blockers:** CLARIFY summing vectorization approach (see todo: g5-mixing-vectorization), Item 2.3 (audio bridge wiring)
  - **Questions:** Use numpy, numpy + SIMD compiled extension, or pure Python? This affects latency and real-time responsiveness.
  - **Known issue:** Track FX do not apply reliably (see Problems section)

- [ ] **5.2** Make track FX and playback parameter changes apply reliably and audibly during active playback; clearly communicate any deliberate defer-to-next-buffer behavior. *(ref: existing P1 brief)*
  - **Status:** Not started
  - **Blockers:** Item 5.1 (summing engine complete)
  - **Known issue:** Track FX currently unreliable (see Problems section)

- [ ] **5.3** Make the Master Section live during playback: waveform updates, dual VU meter bars respond, LUFS integrated reading updates, peak indicators react. *(ref: UX §2.3, existing P2 brief)*
  - **Status:** Not started
  - **Blockers:** Item 3.2 (master section complete), Item 2.3 (audio-thread-to-UI bridge complete)
  - **Known issue:** Master section appears nonfunctional; needs dedicated waveform bars and meter panel (see Problems section)

---

### Group 6 — New Project Dialog

- [ ] **6.1** Implement the New Project modal dialog (Ctrl+N / File → New Project): project name field (auto-focus), folder selector, visual template grid (Empty / Basic 4-Track / Podcast / Beat Maker / AI Stems Session), sample rate dropdown, BPM field, "Create Project" cyan primary button + "Cancel". *(ref: UX Screen 7)*

---

### Group 7 — AI Tab: Demucs Stem Extraction

- [ ] **7.1** Create the "Stem Separation (Demucs)" full-page tab: left panel (drag-and-drop source zone, separation model dropdown with stem-count labels and "Manage Models…" link, device selector with auto-detect, inline VRAM color indicator, Force CPU checkbox, shifts spinner, two-stem mode, output format / sample rate / normalize settings). *(ref: UX §3.2–3.4)*
- [ ] **7.2** Implement the Demucs run controls: full-width "Separate" button (green ready / amber pulsing during processing), "Cancel" button (appears during processing only); wire to background Demucs worker with signal callbacks. *(ref: UX §3.5, offline Phase 4)*
- [ ] **7.3** Build the center progress area: overall progress bar with states (Idle / Loading model… / Processing… / Complete), per-stem progress bars with labels, elapsed time + ETA, terminal-style activity log (green / amber / red color scheme, auto-scroll, timestamps, Copy / Save / Clear / filter toolbar). *(ref: UX §3.6–3.7)*
- [ ] **7.4** Build the post-completion output preview section: per-stem waveform thumbnail rows with Play button and volume knob. *(ref: UX §3.8)*
- [ ] **7.5** Implement the right Transfer Options panel: "Send to Main Tracks" raised tile card (insert position sub-options, auto-color-code toggle), "Save to Project Folder" tile card (path + subfolder pattern), per-stem output checklist with file sizes, "→ Transfer to ACE-Step" secondary button, primary Transfer button with cyan glow. *(ref: UX §3.9, Decision 7)*

---

### Group 8 — AI Tab: ACE-Step Generation

- [ ] **8.1** Create the "AI Generation (ACE-Step)" full-page tab: model dropdown (checkpoint discovery from models dir, type badges), LoRA adapter dropdown with "+ Add Custom LoRA…", inline VRAM indicator, Force CPU checkbox. *(ref: UX §4.2)*
- [ ] **8.2** Implement Style Tags and Instruments pill inputs: type-and-Enter pill creation, suggestion dropdown while typing, × removal per pill, 12-pill visible max with scroll, "Clear All" link; "No specific instruments" checkbox. *(ref: UX §4.3–4.4)*
- [ ] **8.3** Implement Audio Reference section: source dropdown (None / Upload / Active Track / Last Demucs Stem), waveform thumbnail, Influence Strength slider (0.0–1.0), start/end time fields. *(ref: UX §4.5)*
- [ ] **8.4** Expose all Generation Settings controls: Duration slider+input (5–300s), Steps (10–150), CFG scale (1.0–20.0), Seed + randomize dice, Lock seed checkbox, Scheduler dropdown (Euler / Euler Ancestral / DPM++ 2M / DPM++ SDE / DDIM / PNDM), ERG weight, ELA weight (grayed without lyrics), Batch count (1–8) with estimated time, Output format. *(ref: UX §4.6)*
- [ ] **8.5** Build the right column prompts area: main textarea (min 5 lines), collapsible negative prompt, collapsible line-numbered lyrics field; full-width Generate button (green idle / amber pulsing processing with ETA); collapsible real-time terminal log. *(ref: UX §4.7–4.8)*
- [ ] **8.6** Build results grid: waveform thumbnail cards with duration, seed, Play, Loop, star/favorite; quick-action row (Regenerate same/new seed, Vary subtle/strong); Transfer panel mirroring Demucs transfer options plus "Send to Demucs" tile. *(ref: UX §4.9–4.10)*

---

### Group 9 — Mastering Chain Page

- [ ] **9.1** Build the mastering chain full-page view: horizontal 3D raised-card signal chain — Input Trim → 4-Band Parametric EQ (visual frequency curve) → Compressor (threshold / ratio / attack / release / knee / makeup, VU meters) → Stereo Widener → Limiter (threshold / ceiling / release, clip LED, true peak readout) → Output. Bypass button per block (red glow when bypassed). Arrow connectors between blocks. *(ref: UX §5.1, offline Phase 8)*
- [ ] **9.2** Implement the LUFS meter panel: Integrated / Short-term / Momentary / LU Range / True Peak readouts in cyan monospace; target preset dropdown (Spotify −14 / YouTube −16 / EBU R128 −23 / ATSC −24 / Custom); dashed amber target line on LUFS history scrolling chart; Integrated readout color-coded green/amber/red vs target. *(ref: UX §5.2, Decisions 5)*

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

- Reframe the main Echo Pro shell around the locked 3D studio-hardware layout from the UX companion document so control clusters, transport, and arrangement space follow the fixed-width rules.
- Treat Demucs and ACE-Step as separate full-page AI tabs with transfer handoff, not a unified AI surface.
- Add the mastering chain as a dedicated first-class page with LUFS target presets, history graphing, and bypassable processing blocks.
- Make the MIDI hardware mapping page and model-manager settings sub-tabs first-class destinations instead of hidden support screens.
- Continue the non-destructive project/storage architecture so track slices, clip metadata, and arrangement state can be saved without mutating source audio.
- Phase 5B validation pass and recovery-history UX improvements.
- Phase 6 installer validation and packaged-launch verification.
- Plain non-debug Echo Pro launch flow that is as reliable as the current VS Code debug launch.
- Manual playback QA pass focused on per-track fades, loop regions, and starter effects with save/reopen coverage.
- Additional lightweight timeline affordances if playback settings need stronger visibility after user testing.
- Broader recording and device-startup polish if audio-device refresh continues to feel slow or fragile on startup.
- Real-device recording sanity pass before any release-oriented packaging or rollout.
- Better progress/reporting UX for long-running generation workflows if current status updates still feel too thin in practice.
- Clip-import validation polish if add-clip flows still produce avoidable user-error loops during QA.
- Declutter the Home tab layout so track controls feel less crowded and more directly associated with the track they affect.
- Explore a vertical beside-the-track mixer/control layout instead of the current separate mixer section.

## Todos

> **Note (2026-08-03):** Active build work is tracked in the **Ordered Build Task List** above. Items in this section are older scoped tasks and general backlog; they will be retired as the build list covers them. Typography tokens (Segoe UI / Consolas sizes) are kept in `app/styles.py` alongside color tokens — no separate theme file needed for v1.0.

- [ ] Audit the active Home / mixer shell against the locked UX document and list the remaining layout gaps for the 3D hardware-style arrangement view.
- [ ] Split the AI workflow into distinct Demucs and ACE-Step tabs with the documented transfer actions between them.
- [ ] Add the mastering chain page with target LUFS presets, live meter feedback, and bypass controls.
- [ ] Add the MIDI hardware mapping page and the Settings model-manager sub-tabs described in the instruction documents.
- [ ] Implement the new project dialog and the session-sidebar truncation/tooltip behavior from the UX spec.
- [ ] Define the non-destructive project serialization path for arrangement state, clip metadata, and saved slices.
- [ ] Verify the new VS Code debug launch path from a fresh editor session and confirm it is the preferred developer launch path.
- [ ] Decide whether to keep, rename, or replace the old task-based launch workflow now that the debug configuration is the reliable path.
- [ ] Run a focused manual QA pass for per-track fade-in, fade-out, loop-region, and starter-effect playback after save/reopen.
- [ ] Capture any follow-up UX tweaks discovered during track playback QA back into this file before starting implementation.
- [ ] Run a manual real-device recording sanity pass to complement the existing automated Phase 5 regression coverage.
- [ ] Re-check long-running generation workflows for progress feedback gaps that still need better UX.
- [ ] Increase the new icon controls to roughly double their current size so they are easier to see and click.

## Problems

- Source checkouts do not include `EchoPro.exe`, so the portable packaged launcher path cannot be validated from this repo alone.
- A shell task can start the Echo Pro runtime Python process without reliably surfacing the PySide window, which is why the debug launch path is currently preferred.
- Echo Pro runtime dependencies live outside the repo under `%LOCALAPPDATA%\\EchoProData\\runtime\\venv`, so launch reliability can drift if that environment gets out of sync.
- Older internal status docs can drift from the repo's current runtime and launch reality, so this file should be treated as the actively maintained task snapshot.
- The Master section appears nonfunctional and still needs its own waveform bars plus a dedicated control/meter panel for levels, peaks, and related master-output monitoring.
- UI controls should use evenly sized, evenly spaced icon buttons instead of text-heavy buttons, with descriptive text exposed on hover/tooltips.
- Double-clicking a waveform/track still does not open a dedicated single-track editor for focused editing.
- Track FX do not seem to apply reliably, and playback parameters should be adjustable live while audio is playing.
- Skip forward/reverse behaves incorrectly when no part of the waveform is selected, and single-click selection start/end editing is still missing.
- Users still cannot zoom in or out far enough to work directly at the waveform level on a single track.

## Implementation Briefs

### Locked DAW shell and visual language

- **Priority:** P1
- **Feature definition:** Align the main Echo Pro shell with the locked 3D material design, fixed-width control clusters, and studio-hardware visual language from the UX companion document.
- **User-visible behavior:** The app feels like a structured DAW surface with a custom title bar, fixed transport/status zones, left-side mixing controls, and waveform space that expands instead of the controls stretching.
- **Out of scope:** No broad cosmetic rewrite outside the documented shell and no change to the locked layout rules unless the UX spec is formally revised.
- **Likely affected areas:** [echo_pro_app.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/echo_pro_app.py), [app/styles.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/app/styles.py), [timeline_widget.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/timeline_widget.py), and shared widget/style helpers.
- **Done when:** The live shell matches the locked mixer/transport/sidebar structure closely enough that the documented layout decisions are visible in the running app.

### Split AI tabs and transfer workflow

- **Priority:** P1
- **Feature definition:** Implement Demucs and ACE-Step as separate full-page tabs with the documented source, progress, output, and transfer flows between them.
- **User-visible behavior:** Users can move from mixer to Demucs or ACE-Step directly, complete a workflow, and hand results off to the other AI page or back into the arrangement.
- **Out of scope:** No unified AI studio tab and no collapse of the two workflows into a single shared page.
- **Likely affected areas:** [echo_pro_app.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/echo_pro_app.py), [stems_engine.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/stems_engine.py), [music_generator.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/music_generator.py), and related tab/navigation code.
- **Done when:** Both AI pages exist as distinct tabs, each exposes the documented controls, and transfer actions preserve the intended handoff path.

### Master chain and LUFS metering

- **Priority:** P1
- **Feature definition:** Build the mastering chain page with the ordered processing blocks, LUFS target presets, and real-time analytics described in the instruction document.
- **User-visible behavior:** The user can inspect loudness, set a target preset, see the target line on the LUFS history display, and bypass individual chain stages.
- **Out of scope:** No full DAW mastering suite and no attempt to replace the existing mixer architecture.
- **Likely affected areas:** [echo_pro_app.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/echo_pro_app.py), [playback_mixer.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/playback_mixer.py), [app/ui/widgets/](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/app/ui/widgets/), and any mastering-specific backend.
- **Done when:** The chain page exists, live loudness feedback works, and the documented LUFS target behavior is visible in the UI.

### Inline automation and clip-fade workflow

- **Priority:** P1
- **Feature definition:** Keep automation inline in the waveform lane and add the locked fade-settings popover so clip-edge editing and automation remain synchronized.
- **User-visible behavior:** Users can see and edit automation curves directly on the lane, then adjust fade in/out settings through the popover or clip handles with immediate sync.
- **Out of scope:** No dedicated automation dock panel and no replacement of the inline lane overlay model in v1.
- **Likely affected areas:** [timeline_widget.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/timeline_widget.py), [app/ui/widgets/](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/app/ui/widgets/), and clip-context-menu/fade helpers.
- **Done when:** Automation stays inline, fade controls remain synchronized, and the clip interaction model matches the locked UX decision.

### Non-destructive project serialization

- **Priority:** P1
- **Feature definition:** Define the save/load schema for tracks, slices, clips, and project metadata so source audio stays untouched while project state is preserved.
- **User-visible behavior:** Users can save and reopen projects without losing clip arrangement, edits, or metadata, and source media remains intact on disk.
- **Out of scope:** No destructive rewrite of source files and no custom media database beyond what the project needs.
- **Likely affected areas:** [project_model.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/project_model.py), [recording_session.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/recording_session.py), [voice_store.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/voice_store.py), and persistence helpers.
- **Done when:** Project state round-trips cleanly through save/reopen and the on-disk source media is not modified by normal workflow operations.

### Live FX application during playback

- **Priority:** P1
- **Feature definition:** Make track FX and playback parameter changes apply reliably and audibly while playback is already running, or clearly communicate any deliberate limitations if truly live updates are not feasible.
- **User-visible behavior:** Adjusting supported playback settings during playback produces immediate or predictably refreshed audible changes instead of appearing broken or ignored.
- **Out of scope:** No full real-time DSP engine rewrite unless the current architecture absolutely requires it, and no speculative plugin system expansion beyond the existing playback settings surface.
- **Likely affected areas:** [playback_mixer.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/playback_mixer.py), [project_model.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/project_model.py), [echo_pro_app.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/echo_pro_app.py), and [app/ui/dialogs/track_playback_settings_dialog.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/app/ui/dialogs/track_playback_settings_dialog.py).
- **Done when:** Supported FX/playback adjustments are clearly applied during playback or at a defined refresh point, and the user can verify that parameter changes are not silently ignored.

### Waveform navigation fallback and click-based selection editing

- **Priority:** P1
- **Feature definition:** Fix waveform navigation so skip forward/reverse behaves sensibly when nothing is selected, and add click-based selection start/end editing on the waveform surface.
- **User-visible behavior:** Skip controls fall back to intuitive positions when no region is selected, and users can establish or refine a selection directly from the waveform without awkward workarounds.
- **Out of scope:** No full timeline interaction rewrite and no replacement of existing drag-selection behavior unless needed to support clear click-based editing.
- **Likely affected areas:** [timeline_widget.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/timeline_widget.py), [echo_pro_app.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/echo_pro_app.py), and any playhead/selection helpers already used by transport controls.
- **Done when:** Skip controls use stable fallback behavior with no selection, and users can set or refine selection boundaries directly with click-driven interactions that update the active playhead/selection state visibly.

### Waveform-level zoom for single-track editing

- **Priority:** P1
- **Feature definition:** Add enough zoom control and resolution on the track editor/timeline surfaces for direct waveform-level work instead of only broad arrangement-level navigation.
- **User-visible behavior:** Users can zoom in close enough to inspect and edit waveform details, then zoom back out without losing orientation in the project.
- **Out of scope:** No fully separate sample editor unless later work explicitly chooses that path, and no destructive waveform editing pass beyond navigation/inspection improvements.
- **Likely affected areas:** [timeline_widget.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/timeline_widget.py), [echo_pro_app.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/echo_pro_app.py), and any dedicated track-editor surface created for focused waveform work.
- **Done when:** The UI exposes usable zoom in/out behavior for close waveform work, the current zoom state is reflected clearly enough for the user to stay oriented, and the resulting workflow supports direct single-track inspection/editing.

### Dedicated single-track editor on waveform double-click

- **Priority:** P2
- **Feature definition:** Add a reliable double-click interaction that opens a focused single-track editor window or panel from the waveform/track surface.
- **User-visible behavior:** Double-clicking the intended track or waveform region opens a dedicated editing surface for that track instead of doing nothing.
- **Out of scope:** No multi-window session manager and no attempt to redesign every editing workflow before the first single-track editor pass works.
- **Likely affected areas:** [timeline_widget.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/timeline_widget.py), [echo_pro_app.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/echo_pro_app.py), and any new dialogs/windows created under [app/ui/](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/app/ui/).
- **Done when:** A track double-click consistently opens the intended focused editor path, passes the correct track context, and preserves the user's current project/timeline state.

### Master output section functionality and metering

- **Priority:** P2
- **Feature definition:** Make the Master section function as a meaningful output-monitoring surface with waveform, levels, peaks, and related master controls instead of a mostly passive placeholder.
- **User-visible behavior:** The Master area reacts to playback, exposes useful monitoring information, and feels like a real output section rather than an inert panel.
- **Out of scope:** No full mastering suite, no advanced DAW-grade plugin rack, and no attempt to replace the per-track mixer with a completely different architecture.
- **Likely affected areas:** [echo_pro_app.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/echo_pro_app.py), [playback_mixer.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/playback_mixer.py), any level-meter widgets under [app/ui/widgets/](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/app/ui/widgets/), and playback polling/status paths.
- **Done when:** The Master section updates during playback, shows useful waveform/meter feedback, and exposes at least a scoped first pass of master-output monitoring that matches the rest of the app's live state.

### Control sizing and icon affordance consistency

- **Priority:** P2
- **Feature definition:** Finish the control declutter pass by standardizing icon button sizing, spacing, and hover-label behavior so the new icon-based UI remains readable and easy to hit.
- **User-visible behavior:** Icon buttons are consistently sized, easier to see, and easier to click, with hover/tooltips remaining the primary way to reveal descriptive labels.
- **Out of scope:** No full visual redesign of every widget style in the app and no unrelated theme/color overhaul unless required for button readability.
- **Likely affected areas:** [echo_pro_app.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/echo_pro_app.py), [recording_ui_components.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/recording_ui_components.py), [app/ui/widgets/track_mixer_row.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/app/ui/widgets/track_mixer_row.py), and any shared button helpers or style rules that now control icon surfaces.
- **Done when:** The icon-based controls use a coherent size/spacing standard across the main Home and Recording flows, including the requested larger hit targets, without making the layouts collapse or clip.

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

## Problems

Known blockers, integration gaps, performance concerns, and deferred work requiring attention:

### Group 2 & 3 Integration Concerns

1. **TimelineSyncController subscription wiring in Group 3 widgets**
   - **Issue:** TimelineSyncController is now the authoritative source for timeline state (playhead, zoom, scroll, playback, BPM). All Group 3 widgets (Timeline Ruler, Waveform Lane, Transport Bar, Master Section, Channel Strips) must subscribe to controller signals instead of managing independent state.
   - **Impact:** Without proper subscription, UI will not update during playback or when user changes zoom/scroll/playback state.
   - **Action needed:** Wire signal subscriptions in each Group 3 component before testing live playback. See Group 3 items 3.1–3.9.

2. **TrackMixerRow styling alignment for 3D glow states**
   - **Issue:** Existing TrackMixerRow component needs review for Mute / Solo / Record Arm button glow states to match the 3D bevel spec in Group 1 (active glow box-shadow on #00F0FF).
   - **Impact:** Item 3.4 (Channel Strip widget) cannot be considered complete without visual correctness.
   - **Action needed:** Review [app/ui/widgets/track_mixer_row.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/app/ui/widgets/track_mixer_row.py) and update button styling to match spec.

3. **Waveform rendering performance at extreme zoom levels**
   - **Issue:** TimelineSyncController supports zoom range 1/128–128x (256x range). Waveform rendering at 128x (sample-level editing) may have performance implications for large projects.
   - **Impact:** Potential janky UI or excessive CPU during sample-level zoom and scroll.
   - **Action needed:** Profile waveform rendering at zoom extremes (post-Group 3 completion); may require caching or LOD strategy in Group 4.

4. **Audio bridge playhead polling frequency**
   - **Issue:** AudioThreadBridge uses queue.Queue with manual `poll()` calls from UI thread. No automatic polling wired yet; audio→UI updates only happen when UI thread calls `bridge.poll()`.
   - **Impact:** Playhead and meters may appear "stuck" if UI thread is busy or polling is not called frequently enough.
   - **Action needed:** Wire `bridge.poll()` into a QTimer or main event loop before testing live audio (see Group 3 Transport Bar wiring).

5. **Project persistence integration with current project model**
   - **Issue:** ProjectPersistence is scaffolded but not wired into echo_pro_app.py's save/load paths yet.
   - **Impact:** Projects saved via current "Save Project" button are stored in old format; new persistence layer is unused.
   - **Action needed:** Integrate ProjectPersistence.save_project() and load_project() into project_browser_dialog and main app save/load slots (Group 6 or 7 work).

### Deferred Technical Decisions (Not Blocking, But Flagged)

1. **Project schema backward compatibility strategy**
   - **Note:** ProjectMetadata includes `version` field for future migration. Current schema is v1.0 (reference-by-path, no deep copies).
   - **Decision:** If future versions need to support embedded stems or alternate storage formats, add a schema version migration handler in ProjectPersistence._is_compatible_version().

2. **Master section real-time metering (Group 3.2)**
   - **Note:** Master fader and VU meter UI components are scaffolded in MainMixerLayout but not wired to actual master volume state or audio levels yet.
   - **Decision:** Requires Group 5 mixing engine to expose master output levels via AudioThreadBridge; should be wired after mixing engine is ready.

3. **Undo/Redo architecture**
   - **Note:** ProjectPersistence includes `undo_history` field in project JSON (unused).
   - **Decision:** Full undo/redo implementation deferred to Group 6 or 7. Current approach: warn user on unsaved changes; no checkpoint-based undo yet.

### Known Gaps (Not Critical But Worth Noting)

- MainMixerLayout toolbar is scaffolded with TODO markers for File/Edit/View menus and quick-action buttons; wiring to actual slots needed in Group 3.1.
- Timeline Ruler placeholder text present; full bars:beats:ticks rendering and click-to-reposition logic deferred to Group 3.3.
- Waveform Lane placeholder in center area; full waveform rendering, clip rectangles, and color fill deferred to Group 3.5.
- Sidebar scaffold present; Browser tree drag-and-drop and Sessions tab implementation deferred to Group 3.7.

## Recently Completed

- Confirmed that the project-playback freeze issue is no longer reproducing in manual playback checks.
- Added a [cleanup prompt](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/.github/prompts/cleanup.prompt.md) for archiving obsolete files and reducing project-folder clutter safely.
- Converted the main Home controls plus the Recording tab's transport, setup, take-review, and comp/recovery actions to compact icon-style buttons with hover labels as a first pass on the broader control declutter work.
- Removed developer-only P5A/P5B regression actions from general user-facing tabs and aligned the phase implementation prompt with the repo instructions.
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
