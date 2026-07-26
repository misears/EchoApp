# EchoApp Task Hub

This is the single working file for EchoApp ideas, actionable todos, and current problems.

Use this file as the default place to capture:
- rough ideas that are not yet scoped,
- next actionable engineering tasks,
- active problems or recurring friction,
- and recent completions worth keeping visible.

When work changes the project state in a meaningful way, update this file in the same change.

## How to use this file

- Put unshaped feature thoughts in **Ideas**.
- Move items into **Todos** when they are specific enough to execute.
- Track blockers, bugs, and repeated pain points in **Problems**.
- Move finished work into **Recently Completed** so the active sections stay useful.

---

## Ideas

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

- [ ] Verify the new VS Code debug launch path from a fresh editor session and confirm it is the preferred developer launch path.
- [ ] Decide whether to keep, rename, or replace the old task-based launch workflow now that the debug configuration is the reliable path.
- [ ] Run a focused manual QA pass for per-track fade-in, fade-out, loop-region, and starter-effect playback after save/reopen.
- [ ] Capture any follow-up UX tweaks discovered during track playback QA back into this file before starting implementation.
- [ ] Run a manual real-device recording sanity pass to complement the existing automated Phase 5 regression coverage.
- [ ] Re-check long-running generation and stem workflows for progress feedback gaps that still need better UX.
- [ ] Increase the new icon controls to roughly double their current size so they are easier to see and click.

## Problems

- Source checkouts do not include `EchoPro.exe`, so the portable packaged launcher path cannot be validated from this repo alone.
- A shell task can start the Echo Pro runtime Python process without reliably surfacing the PySide window, which is why the debug launch path is currently preferred.
- Echo Pro runtime dependencies live outside the repo under `%LOCALAPPDATA%\\EchoProData\\runtime\\venv`, so launch reliability can drift if that environment gets out of sync.
- Older internal status docs can drift from the repo's current runtime and launch reality, so this file should be treated as the actively maintained task snapshot.
- Stem splitting needs its own Home-tab section with Demucs-specific options, and Demucs still does not reliably activate or show clear progress/completion feedback while splitting runs.
- The Master section appears nonfunctional and still needs its own waveform bars plus a dedicated control/meter panel for levels, peaks, and related master-output monitoring.
- UI controls should use evenly sized, evenly spaced icon buttons instead of text-heavy buttons, with descriptive text exposed on hover/tooltips.
- Double-clicking a waveform/track still does not open a dedicated single-track editor for focused editing.
- Track FX do not seem to apply reliably, and playback parameters should be adjustable live while audio is playing.
- Skip forward/reverse behaves incorrectly when no part of the waveform is selected, and single-click selection start/end editing is still missing.
- Users still cannot zoom in or out far enough to work directly at the waveform level on a single track.

## Implementation Briefs

### Stem splitting section and Demucs progress reliability

- **Priority:** P1
- **Feature definition:** Give stem splitting a dedicated Home-tab surface with Demucs-specific controls and make the Demucs launch/progress/completion flow visibly reliable.
- **User-visible behavior:** Choosing a song for stem splitting clearly enables the Demucs workflow, exposes the right options, and shows meaningful in-progress and finished states instead of appearing inactive.
- **Out of scope:** No full model/backend replacement and no broad redesign of unrelated Home-tab sections beyond what stem-splitting UX needs.
- **Likely affected areas:** [echo_pro_app.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/echo_pro_app.py), [stems_engine.py](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/stems_engine.py), runtime/bootstrap scripts, and any status/progress dialogs or helper widgets used by the Demucs flow.
- **Done when:** Stem splitting has its own discoverable section, Demucs activation is visibly tied to the chosen source audio, and users can see clear progress, success, and failure states without guessing whether the process started.

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

## Recently Completed

- Confirmed that the project-playback freeze issue is no longer reproducing in manual playback checks.
- Added a [cleanup prompt](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/.github/prompts/cleanup.prompt.md) for archiving obsolete files and reducing project-folder clutter safely.
- Converted the main Home controls plus the Recording tab's transport, setup, take-review, and comp/recovery actions to compact icon-style buttons with hover labels as a first pass on the broader control declutter work.
- Removed developer-only P5A/P5B regression actions from general user-facing tabs and aligned the phase implementation prompt with the repo instructions.
- Fixed the active tabbed Home UI path so playback transport controls actually render and source launches export the Echo Pro data root consistently.
- Added a root-level [Start_Echo.bat](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/Start_Echo.bat) launcher that bootstraps the runtime venv, ensures core app packages are present, and starts Echo Pro from source.
- Added Home-tab playback transport controls with non-blocking play/stop, a visible playhead, and jump-to-selection-or-clip navigation.
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
