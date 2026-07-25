# Echo Pro Phase 1-5 Known Issues and Fix TODO

Last updated: 2026-07-23
Purpose: single source of truth for active issues, errors, and fix tasks across Phases 1-5.

## Current Error Snapshot

- Active diagnostics errors:
  - None currently reported in planning docs.
- No active diagnostics errors found in core code modules for Phases 1-5.
- Remaining open work is feature completion and validation, not a diagnostics cleanup item.

## Important Status Notes

- The following prior issues are already fixed in code:
  - Mutable dataclass defaults in voice_interface.py and t2m_interface.py.
  - Duplicate audioinfo.py removal.
- BUILD_STATUS.md stale entries and markdown table lint issues were cleaned on 2026-07-23.

---

## Phase-by-Phase Issues and TODO

## Phase 1 (Core DAW)

### P1-1 Input validation hardening for clip import

- Status: Closed (resolved 2026-07-23)
- File targets: echo_pro_app.py
- Problem:
  - Add Clip and related track-index fields rely on repeated ad hoc parsing.
  - Better validation and messaging would reduce user error loops.
- TODO:
  - [x] Add shared numeric parsing helpers for int/float with consistent error text.
  - [x] Validate track index and clip time ranges before file dialog opens.
  - [x] Add explicit file-exists check before clip append.
  - [x] Add unit-style validation checks for common bad inputs.

### P1-2 Timeline interactivity gap

- Status: Closed (resolved 2026-07-23)
- File targets: timeline_widget.py
- Problem:
  - Timeline renders well but still has minimal direct editing interactions.
- TODO:
  - [x] Add click select for clips.
  - [x] Add drag move for clip start times.
  - [x] Add visual selected-clip state and keyboard delete action.

---

## Phase 2 (Stems, Playback, Mixing)

### P2-1 Long-running stems UX

- Status: Closed (resolved 2026-07-23)
- File targets: echo_pro_app.py, stems_engine.py
- Problem:
  - Stem split currently uses status text only; progress feedback is limited.
- TODO:
  - [x] Add non-blocking progress dialog for stem separation.
  - [x] Add cancel/abort path if backend supports it.
  - [x] Add clearer completion/failure summaries.

### P2-2 Demucs/ffmpeg failure guidance

- Status: Closed (resolved 2026-07-23)
- File targets: stems_engine.py, echo_pro_app.py
- Problem:
  - Failures can still surface as generic exception text.
- TODO:
  - [x] Map common Demucs-not-found errors to actionable user guidance.
  - [x] Map ffmpeg-not-found errors to setup/update instructions.
  - [x] Add quick link/action to dependency update script from UI error dialogs.

---

## Phase 3 (Voice Recording/Conversion)

### P3-1 Placeholder conversion quality (expected limitation)

- Status: Closed (resolved 2026-07-23; placeholder behavior remains explicit by design)
- File targets: voice_effects.py, voice_interface.py
- Problem:
  - Voice conversion is placeholder behavior, not model-grade conversion.
- TODO:
  - [x] Keep placeholder clearly labeled in UI and docs.
  - [x] Define model integration acceptance tests before swapping backend.
  - [x] Add configurable backend selection and runtime capability check.
  - Validation note: baseline acceptance checks and parser sanity checks are codified in `input_validation.py::run_common_validation_checks()`.

### P3-2 Metadata consistency coverage

- Status: Closed (resolved 2026-07-23)
- File targets: voice_store.py, echo_pro_app.py
- Problem:
  - Voice profile metadata and consent flow works, but validation coverage is limited.
- TODO:
  - [x] Add checks for missing/corrupt profile files at load time.
  - [x] Add migration path if profile schema expands.

---

## Phase 4 (Music Generation/Song Planner)

### P4-1 Placeholder generation output (expected limitation)

- Status: Closed (resolved 2026-07-23; placeholder output remains explicit by design)
- File targets: t2m_interface.py, music_generator.py
- Problem:
  - Generated audio is placeholder silence until real model integration.
- TODO:
  - [x] Keep placeholder warning in generation UI.
  - [x] Add backend readiness check and user-readable capability state.

### P4-2 Section-alteration persistence scope

- Status: Closed (resolved 2026-07-23)
- File targets: echo_pro_app.py, song_planner.py
- Problem:
  - Section alteration works in-session, but mapping is currently memory-resident and not persisted to project metadata.
- TODO:
  - [x] Persist section mapping/version data into project/session metadata.
  - [x] Restore section mapping on project load.
  - [x] Add dropdown section picker to avoid manual index entry.

### P4-3 Generation input validation polish

- Status: Closed (resolved 2026-07-23)
- File targets: echo_pro_app.py
- Problem:
  - Generation forms can still accept incomplete/weak input combinations.
- TODO:
  - [x] Validate structure list and duration bounds with friendly messages.
  - [x] Validate time signature format consistently across generation and recording.

---

## Phase 5A (Recording Core)

### P5A-1 Take review UX incomplete

- Status: Closed (resolved 2026-07-23)
- File targets: recording_session.py, echo_pro_app.py, recording_ui_components.py
- Problem:
  - Core take data previously lacked full browsing/selection and timeline-linked active state controls.
- TODO:
  - [x] Add per-track take browser widget.
  - [x] Add active take selector and quick audition actions.
  - [x] Show take metadata (duration, clipping, timestamp) in UI.
  - [x] Add timeline badges for active/alternative takes and bulk hide inactive clips.
  - [x] Persist take-review preferences (filter/sort/loop/hide) per session.

### P5A-2 Recording robustness regression suite

- Status: Closed (resolved 2026-07-23)
- File targets: recording_controller.py, audio_engine.py
- Problem:
  - Major features are integrated, but dedicated regression matrix is still needed.
- TODO:
  - [x] Add scripted checks for count-in transition to record state (`p5a_regression_runner.py`).
  - [x] Add checks for stop during count-in (`p5a_regression_runner.py`).
  - [x] Add checks for device swap/error paths (`p5a_regression_runner.py`).
  - [x] Run scripted checks and capture pass/fail report in QA notes (latest: 3 passed, 0 failed).

### P5A-3 Meter semantics tuning

- Status: Closed (resolved 2026-07-23)
- File targets: recording_ui_components.py, audio_engine.py
- Problem:
  - Clip hold/reset is implemented; peak reset and decay behavior can be improved.
- TODO:
  - [x] Add optional peak hold timeout and manual peak reset.
  - [x] Add input-silence warning threshold option.

---

## Cross-Phase Documentation and Error Hygiene

### DOC-1 BUILD_STATUS.md stale issue entries

- Status: Closed (resolved 2026-07-23)
- File targets: BUILD_STATUS.md
- Problem:
  - Document previously contained already-fixed issues in legacy sections.
- TODO:
  - [x] Remove or mark resolved: mutable dataclass defaults items.
  - [x] Remove or mark resolved: duplicate audioinfo.py item.
  - [x] Keep active issues only in Known Issues section.

### DOC-2 Markdown lint cleanup

- Status: Closed (resolved 2026-07-23)
- File targets: BUILD_STATUS.md
- Problem:
  - MD060 table style warnings were previously active.
- TODO:
  - [x] Normalize markdown table style consistently in the file.
  - [x] Re-run diagnostics and confirm zero markdown lint errors.

---

## Prioritized Execution Order

1. Phase 5B validation pass and recovery-history UX
2. Phase 6 installer validation
3. P2-1 stems progress UX + P2-2 dependency error guidance if they resurface in QA
4. P4-2 section-alteration persistence if project metadata changes
5. Remaining enhancement items

---

## Definition of Done for this TODO

- [x] No active diagnostics/lint errors in planning docs.
- [x] BUILD_STATUS.md reflects only currently active issues.
- [x] Phase 5A take review UX completed and validated.
- [x] Core phase workflows (1-5A) pass regression checks.
