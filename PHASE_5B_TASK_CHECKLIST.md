# Phase 5B Task Checklist

Status: In progress  
Scope: Punch/loop workflows, take browser, comping v1, recovery, and safety checks

## Progress Update

- 2026-07-24: Completed Phase 5B P1/P2 enhancement pass and broader regression automation.
  - `audio_engine.py`: clip-event counters, peak clip-hold tracking, and silence warning/event tracking.
  - `audio_device.py`: channel compatibility checks plus disk+device preflight summary formatting.
  - `recording_controller.py`: transport start/stop debounce and optional auto-disarm policy hooks.
  - `echo_pro_app.py`: one-click best take, recovery history dropdown restore flow, note template actions, compact/expanded take view mode, and P5B checks trigger.
  - `recording_recovery.py`: snapshot history retention/list/load helpers.
  - `timeline_widget.py`: alternating comp overlay color presets by source take.
  - New `p5b_regression_runner.py` added and passing (7/7), including Phase 5A baseline compatibility check.

- 2026-07-24: Closed remaining P0 UI/timeline tickets.
  - `recording_ui_components.py`: added reusable `TakeListWidget` and `TransportPunchLoopWidget` and wired deterministic callbacks.
  - `timeline_widget.py`: added drag-select comp-range selection constrained to selected track plus comp region overlays.
  - `echo_pro_app.py`: integrated reusable widgets and timeline range-selection wiring into comp range controls.
  - Validation: `run_p5a_checks.bat` passed (3/3) and `ui_runtime_smoke.py` passed all targeted flows with no exceptions.

- 2026-07-24: P5B core transport and recovery plumbing are largely in place.
  - `recording_controller.py`: added punch and loop state, range setters (samples/seconds/bars), pre/post-roll windows, punch auto-stop, and loop cycle take rollover.
  - `echo_pro_app.py`: added bar-based punch controls, pre/post-roll controls, and loop controls in recording panel with live cycle/status display.
  - `recording_controller.py` + `recording_ui_components.py`: added structured transport diagnostics API and compact diagnostics panel wiring in the recording UI.
  - `recording_session.py` + `echo_pro_app.py`: added take quality markers and browser actions (keeper/mute/rating) with metadata persistence and clip sync.
  - `recording_session.py` + `echo_pro_app.py` + `recording_recovery.py`: added comp-region actions (create/assign/clear) plus interrupted-session snapshot validation and restore/discard prompt flow.
  - Remaining: reusable comp/take widgets, timeline comp overlays, recovery history UX, and broader session validation.

## Usage

- Priority levels:
  - P0 = must-have for Phase 5B completion
  - P1 = high value polish for Phase 5B quality
  - P2 = optional enhancements if time remains

- Suggested workflow:
  - Implement all P0 tickets first
  - Validate with the test notes after each file section
  - Promote P1 items only after P0 regression pass

---

## P0 Tickets (Must Have)

### recording_controller.py

- [x] P0-RC-001 Add punch mode state model
  - Add fields: `punch_enabled`, `punch_in_samples`, `punch_out_samples`
  - Add setters for punch in/out from bars/time
  - Accept when recording starts/stops at expected punch boundaries
- [x] P0-RC-002 Add loop recording transport state
  - Add fields: `loop_enabled`, `loop_start_samples`, `loop_end_samples`, `loop_cycle_index`
  - Ensure cycle restart does not drop callback frames
  - Accept when each loop cycle creates a new take
- [x] P0-RC-003 Add pre-roll/post-roll scheduling support
  - Add pre-roll and post-roll sample windows around punch capture
  - Keep metronome timing aligned through transitions
  - Accept when capture starts/stops musically around punch points
- [x] P0-RC-004 Emit structured recording diagnostics
  - Expose cycle count, punch hit events, clip events, and last transport error
  - Accept when UI can display diagnostics without parsing raw strings

### recording_session.py

- [x] P0-RS-001 Add active-take pointer per track
  - Store `active_take_number` for each track
  - Add methods to set/get active take safely
  - Accept when switching active take changes playback selection source
- [x] P0-RS-002 Add take tags and quality markers
  - Support `is_keeper`, `is_muted`, `rating`, `clip_events`
  - Accept when tags persist through save/load
- [x] P0-RS-003 Add comp region model (non-destructive)
  - Add structure for comp regions and selected source take
  - Accept when comp map serializes to metadata and reloads intact
- [x] P0-RS-004 Save metadata on critical state transitions
  - Persist after loop cycle completion, active-take change, comp edit
  - Accept when forced app close loses at most current callback window

### echo_pro_app.py

- [x] P0-APP-001 Add punch controls in recording panel
  - Inputs/buttons for punch enable, punch in, punch out
  - Validate format and ranges before applying
  - Accept when bad values show readable errors
- [x] P0-APP-002 Add loop recording controls
  - Loop enable plus start/end controls
  - Cycle counter and status text updates in real time
  - Accept when UI clearly indicates active loop cycle
- [x] P0-APP-003 Add take browser panel
  - Per-track list of takes with metadata columns
  - Actions: set active take, keeper toggle, mute toggle
  - Accept when user can switch active take in under 2 clicks
- [x] P0-APP-004 Add comping actions (v1)
  - Actions: create region from timeline selection, assign take, clear region
  - Accept when comp region mapping updates playback preview state
- [x] P0-APP-005 Add recovery prompt flow
  - On startup, detect interrupted recording metadata and offer restore/discard
  - Accept when restore path is user-safe and explicit

### recording_ui_components.py

- [x] P0-UI-001 Add reusable TakeListWidget
  - Track-scoped take list with active/keeper/muted visual indicators
  - Accept when selection and action callbacks are deterministic
- [x] P0-UI-002 Add TransportPunchLoopWidget
  - Encapsulate punch/loop controls for maintainable app wiring
  - Accept when state updates can be pushed/pulled from controller cleanly
- [x] P0-UI-003 Add compact diagnostics widget
  - Show latency, clip events, punch/loop state, and recovery status
  - Accept when values update without blocking UI

### timeline_widget.py

- [x] P0-TL-001 Add range selection for comp region definition
  - Mouse drag selection constrained to active track context
  - Accept when selected range maps to sample/time accurately
- [x] P0-TL-002 Add comp region overlays
  - Show visual region boundaries and selected take indicator
  - Accept when overlays stay aligned after zoom/resize updates

### new file: recording_recovery.py

- [x] P0-RR-001 Create recovery snapshot helpers
  - Save minimal crash-safe snapshot at recording state boundaries
  - Accept when snapshot writes are atomic and fail-safe
- [x] P0-RR-002 Create restore validator
  - Validate snapshot age, session ID, project identity, and integrity
  - Accept when invalid snapshots are safely rejected with explanation
- [x] P0-RR-003 Create restore/apply methods
  - Restore active takes, loop state, and comp metadata references
  - Accept when restored state does not mutate source takes destructively

---

## P1 Tickets (High Value)

### P1 audio_engine.py

- [x] P1-AE-001 Add clip event aggregation counters
  - Track clipping frequency and peak hold time per track
- [x] P1-AE-002 Add optional input-silence detection flags
  - Emit warning when armed track input stays below threshold

### P1 audio_device.py

- [x] P1-AD-001 Add disk+device preflight summary helper
  - Combine device test with selected format and latency compatibility hints
- [x] P1-AD-002 Add safer compatibility check for channel mismatch
  - Validate selected devices against app channel assumptions

### P1 recording_controller.py

- [x] P1-RC-005 Add auto-disarm policy after punch/loop completion
  - Optional preset-driven auto-disarm behavior
- [x] P1-RC-006 Add debounce for transport state transitions
  - Prevent duplicate start/stop calls during rapid UI clicks

### P1 echo_pro_app.py

- [x] P1-APP-006 Add one-click "Use Best Take" helper
  - Based on keeper flag + lowest clip events
- [x] P1-APP-007 Add recovery history dropdown
  - Let user inspect and choose among recent snapshots

---

## P2 Tickets (Optional)

### P2 recording_session.py

- [x] P2-RS-005 Add take notes templates
  - Quick note chips for common states (clean, noisy, timing issue)

### P2 recording_ui_components.py

- [x] P2-UI-004 Add compact/expanded take browser modes
  - Improve usability for small screens

### P2 timeline_widget.py

- [x] P2-TL-003 Add color presets for comp region readability
  - Alternate region colors by selected source take

---

## Regression and Validation Checklist

### Core recording validation

- [x] Record loop session with 4+ cycles and verify unique take numbers
- [x] Record punch-in/out session and verify timing boundaries
- [x] Switch active takes repeatedly and verify playback source changes correctly

### Comping validation

- [x] Create 3+ comp regions across one track and assign mixed takes
- [x] Save, close, and reopen project/session and verify comp map integrity
- [x] Confirm source takes remain unmodified by comp edits

### Recovery validation

- [ ] Simulate interruption during recording and verify restore prompt appears
- [ ] Restore session and verify take pointers and loop/punch state
- [ ] Discard recovery and verify clean startup path

### Safety validation

- [x] Device preflight returns readable failure for invalid I/O pairing
- [ ] Clip and silence warnings appear without blocking callback performance
- [x] Existing Phase 1-5A workflows remain functional

---

## Suggested Execution Order

1. P0-RC-001 through P0-RC-004
2. P0-RS-001 through P0-RS-004
3. P0-RR-001 through P0-RR-003
4. P0-UI-001 through P0-UI-003
5. P0-TL-001 through P0-TL-002
6. P0-APP-001 through P0-APP-005
7. Full P0 regression pass
8. P1 items as capacity allows

---

## Exit Criteria for Phase 5B

- [x] All P0 tickets complete
- [x] P0 regression checklist passes
- [x] No blocking recording regressions introduced in existing Phase 5A flow
- [x] Build/status docs updated with implementation results
