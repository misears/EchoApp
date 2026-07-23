# Echo Pro Phase 1-5 Known Issues and Fix TODO

Last updated: 2026-07-23
Purpose: single source of truth for active issues, errors, and fix tasks across Phases 1-5.

## Current Error Snapshot

- Active diagnostics errors:
  - Markdown lint errors (MD060 table style) in BUILD_STATUS.md only.
- No active diagnostics errors found in core code modules for Phases 1-5.

## Important Status Notes

- The following prior issues are already fixed in code:
  - Mutable dataclass defaults in voice_interface.py and t2m_interface.py.
  - Duplicate audioinfo.py removal.
- BUILD_STATUS.md still lists some of those as unresolved in older sections, so documentation is partially stale.

---

## Phase-by-Phase Issues and TODO

## Phase 1 (Core DAW)

### P1-1 Input validation hardening for clip import

- Status: Open
- File targets: echo_pro_app.py
- Problem:
  - Add Clip and related track-index fields rely on repeated ad hoc parsing.
  - Better validation and messaging would reduce user error loops.
- TODO:
  - [ ] Add shared numeric parsing helpers for int/float with consistent error text.
  - [ ] Validate track index and clip time ranges before file dialog opens.
  - [ ] Add explicit file-exists check before clip append.
  - [ ] Add unit-style validation checks for common bad inputs.

### P1-2 Timeline interactivity gap

- Status: Open
- File targets: timeline_widget.py
- Problem:
  - Timeline renders well but still has minimal direct editing interactions.
- TODO:
  - [ ] Add click select for clips.
  - [ ] Add drag move for clip start times.
  - [ ] Add visual selected-clip state and keyboard delete action.

---

## Phase 2 (Stems, Playback, Mixing)

### P2-1 Long-running stems UX

- Status: Open
- File targets: echo_pro_app.py, stems_engine.py
- Problem:
  - Stem split currently uses status text only; progress feedback is limited.
- TODO:
  - [ ] Add non-blocking progress dialog for stem separation.
  - [ ] Add cancel/abort path if backend supports it.
  - [ ] Add clearer completion/failure summaries.

### P2-2 Demucs/ffmpeg failure guidance

- Status: Open
- File targets: stems_engine.py, echo_pro_app.py
- Problem:
  - Failures can still surface as generic exception text.
- TODO:
  - [ ] Map common Demucs-not-found errors to actionable user guidance.
  - [ ] Map ffmpeg-not-found errors to setup/update instructions.
  - [ ] Add quick link/action to dependency update script from UI error dialogs.

---

## Phase 3 (Voice Recording/Conversion)

### P3-1 Placeholder conversion quality (expected limitation)

- Status: Open (by design)
- File targets: voice_effects.py, voice_interface.py
- Problem:
  - Voice conversion is placeholder behavior, not model-grade conversion.
- TODO:
  - [ ] Keep placeholder clearly labeled in UI and docs.
  - [ ] Define model integration acceptance tests before swapping backend.
  - [ ] Add configurable backend selection and runtime capability check.

### P3-2 Metadata consistency coverage

- Status: Open
- File targets: voice_store.py, echo_pro_app.py
- Problem:
  - Voice profile metadata and consent flow works, but validation coverage is limited.
- TODO:
  - [ ] Add checks for missing/corrupt profile files at load time.
  - [ ] Add migration path if profile schema expands.

---

## Phase 4 (Music Generation/Song Planner)

### P4-1 Placeholder generation output (expected limitation)

- Status: Open (by design)
- File targets: t2m_interface.py, music_generator.py
- Problem:
  - Generated audio is placeholder silence until real model integration.
- TODO:
  - [ ] Keep placeholder warning in generation UI.
  - [ ] Add backend readiness check and user-readable capability state.

### P4-2 Section-alteration persistence scope

- Status: Open
- File targets: echo_pro_app.py, song_planner.py
- Problem:
  - Section alteration works in-session, but mapping is currently memory-resident and not persisted to project metadata.
- TODO:
  - [ ] Persist section mapping/version data into project/session metadata.
  - [ ] Restore section mapping on project load.
  - [ ] Add dropdown section picker to avoid manual index entry.

### P4-3 Generation input validation polish

- Status: Open
- File targets: echo_pro_app.py
- Problem:
  - Generation forms can still accept incomplete/weak input combinations.
- TODO:
  - [ ] Validate structure list and duration bounds with friendly messages.
  - [ ] Validate time signature format consistently across generation and recording.

---

## Phase 5A (Recording Core)

### P5A-1 Take review UX incomplete

- Status: Open
- File targets: recording_session.py, echo_pro_app.py, recording_ui_components.py
- Problem:
  - Core take data exists but richer per-track take browser/selection workflow is still partial.
- TODO:
  - [ ] Add per-track take browser widget.
  - [ ] Add active take selector and quick audition actions.
  - [ ] Show take metadata (duration, clipping, timestamp) in UI.

### P5A-2 Recording robustness regression suite

- Status: Open
- File targets: recording_controller.py, audio_engine.py
- Problem:
  - Major features are integrated, but dedicated regression matrix is still needed.
- TODO:
  - [ ] Add scripted checks for count-in transition to record state.
  - [ ] Add checks for stop during count-in.
  - [ ] Add checks for device swap/error paths.

### P5A-3 Meter semantics tuning

- Status: Open
- File targets: recording_ui_components.py, audio_engine.py
- Problem:
  - Clip hold/reset is implemented; peak reset and decay behavior can be improved.
- TODO:
  - [ ] Add optional peak hold timeout and manual peak reset.
  - [ ] Add input-silence warning threshold option.

---

## Cross-Phase Documentation and Error Hygiene

### DOC-1 BUILD_STATUS.md stale issue entries

- Status: Open
- File targets: BUILD_STATUS.md
- Problem:
  - Document still contains already-fixed issues in legacy sections.
- TODO:
  - [ ] Remove or mark resolved: mutable dataclass defaults items.
  - [ ] Remove or mark resolved: duplicate audioinfo.py item.
  - [ ] Keep active issues only in Known Issues section.

### DOC-2 Markdown lint cleanup

- Status: Open
- File targets: BUILD_STATUS.md
- Problem:
  - MD060 table style warnings are currently active.
- TODO:
  - [ ] Normalize markdown table style consistently in the file.
  - [ ] Re-run diagnostics and confirm zero markdown lint errors.

---

## Prioritized Execution Order

1. DOC-2 markdown lint cleanup (fast, removes active diagnostics noise)
2. DOC-1 stale issue cleanup (ensures planning truth)
3. P5A-1 take review UX completion
4. P5A-2 recording regression suite
5. P2-1 stems progress UX + P2-2 dependency error guidance
6. P4-2 section-alteration persistence
7. P1-1 input validation consolidation
8. Remaining enhancement items

---

## Definition of Done for this TODO

- [ ] No active diagnostics/lint errors in planning docs.
- [ ] BUILD_STATUS.md reflects only currently active issues.
- [ ] Phase 5A take review UX completed and validated.
- [ ] Core phase workflows (1-5A) pass regression checks.
