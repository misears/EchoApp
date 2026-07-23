# Phase 5B Task Checklist

Status: Ready for implementation  
Scope: Punch/loop workflows, take browser, comping v1, recovery, and safety checks

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

- [ ] P0-RC-001 Add punch mode state model
  - Add fields: `punch_enabled`, `punch_in_samples`, `punch_out_samples`
  - Add setters for punch in/out from bars/time
  - Accept when recording starts/stops at expected punch boundaries
- [ ] P0-RC-002 Add loop recording transport state
  - Add fields: `loop_enabled`, `loop_start_samples`, `loop_end_samples`, `loop_cycle_index`
  - Ensure cycle restart does not drop callback frames
  - Accept when each loop cycle creates a new take
- [ ] P0-RC-003 Add pre-roll/post-roll scheduling support
  - Add pre-roll and post-roll sample windows around punch capture
  - Keep metronome timing aligned through transitions
  - Accept when capture starts/stops musically around punch points
- [ ] P0-RC-004 Emit structured recording diagnostics
  - Expose cycle count, punch hit events, clip events, and last transport error
  - Accept when UI can display diagnostics without parsing raw strings

### recording_session.py

- [ ] P0-RS-001 Add active-take pointer per track
  - Store `active_take_number` for each track
  - Add methods to set/get active take safely
  - Accept when switching active take changes playback selection source
- [ ] P0-RS-002 Add take tags and quality markers
  - Support `is_keeper`, `is_muted`, `rating`, `clip_events`
  - Accept when tags persist through save/load
- [ ] P0-RS-003 Add comp region model (non-destructive)
  - Add structure for comp regions and selected source take
  - Accept when comp map serializes to metadata and reloads intact
- [ ] P0-RS-004 Save metadata on critical state transitions
  - Persist after loop cycle completion, active-take change, comp edit
  - Accept when forced app close loses at most current callback window

### echo_pro_app.py

- [ ] P0-APP-001 Add punch controls in recording panel
  - Inputs/buttons for punch enable, punch in, punch out
  - Validate format and ranges before applying
  - Accept when bad values show readable errors
- [ ] P0-APP-002 Add loop recording controls
  - Loop enable plus start/end controls
  - Cycle counter and status text updates in real time
  - Accept when UI clearly indicates active loop cycle
- [ ] P0-APP-003 Add take browser panel
  - Per-track list of takes with metadata columns
  - Actions: set active take, keeper toggle, mute toggle
  - Accept when user can switch active take in under 2 clicks
- [ ] P0-APP-004 Add comping actions (v1)
  - Actions: create region from timeline selection, assign take, clear region
  - Accept when comp region mapping updates playback preview state
- [ ] P0-APP-005 Add recovery prompt flow
  - On startup, detect interrupted recording metadata and offer restore/discard
  - Accept when restore path is user-safe and explicit

### recording_ui_components.py

- [ ] P0-UI-001 Add reusable TakeListWidget
  - Track-scoped take list with active/keeper/muted visual indicators
  - Accept when selection and action callbacks are deterministic
- [ ] P0-UI-002 Add TransportPunchLoopWidget
  - Encapsulate punch/loop controls for maintainable app wiring
  - Accept when state updates can be pushed/pulled from controller cleanly
- [ ] P0-UI-003 Add compact diagnostics widget
  - Show latency, clip events, punch/loop state, and recovery status
  - Accept when values update without blocking UI

### timeline_widget.py

- [ ] P0-TL-001 Add range selection for comp region definition
  - Mouse drag selection constrained to active track context
  - Accept when selected range maps to sample/time accurately
- [ ] P0-TL-002 Add comp region overlays
  - Show visual region boundaries and selected take indicator
  - Accept when overlays stay aligned after zoom/resize updates

### new file: recording_recovery.py

- [ ] P0-RR-001 Create recovery snapshot helpers
  - Save minimal crash-safe snapshot at recording state boundaries
  - Accept when snapshot writes are atomic and fail-safe
- [ ] P0-RR-002 Create restore validator
  - Validate snapshot age, session ID, project identity, and integrity
  - Accept when invalid snapshots are safely rejected with explanation
- [ ] P0-RR-003 Create restore/apply methods
  - Restore active takes, loop state, and comp metadata references
  - Accept when restored state does not mutate source takes destructively

---

## P1 Tickets (High Value)

### P1 audio_engine.py

- [ ] P1-AE-001 Add clip event aggregation counters
  - Track clipping frequency and peak hold time per track
- [ ] P1-AE-002 Add optional input-silence detection flags
  - Emit warning when armed track input stays below threshold

### P1 audio_device.py

- [ ] P1-AD-001 Add disk+device preflight summary helper
  - Combine device test with selected format and latency compatibility hints
- [ ] P1-AD-002 Add safer compatibility check for channel mismatch
  - Validate selected devices against app channel assumptions

### P1 recording_controller.py

- [ ] P1-RC-005 Add auto-disarm policy after punch/loop completion
  - Optional preset-driven auto-disarm behavior
- [ ] P1-RC-006 Add debounce for transport state transitions
  - Prevent duplicate start/stop calls during rapid UI clicks

### P1 echo_pro_app.py

- [ ] P1-APP-006 Add one-click "Use Best Take" helper
  - Based on keeper flag + lowest clip events
- [ ] P1-APP-007 Add recovery history dropdown
  - Let user inspect and choose among recent snapshots

---

## P2 Tickets (Optional)

### P2 recording_session.py

- [ ] P2-RS-005 Add take notes templates
  - Quick note chips for common states (clean, noisy, timing issue)

### P2 recording_ui_components.py

- [ ] P2-UI-004 Add compact/expanded take browser modes
  - Improve usability for small screens

### P2 timeline_widget.py

- [ ] P2-TL-003 Add color presets for comp region readability
  - Alternate region colors by selected source take

---

## Regression and Validation Checklist

### Core recording validation

- [ ] Record loop session with 4+ cycles and verify unique take numbers
- [ ] Record punch-in/out session and verify timing boundaries
- [ ] Switch active takes repeatedly and verify playback source changes correctly

### Comping validation

- [ ] Create 3+ comp regions across one track and assign mixed takes
- [ ] Save, close, and reopen project/session and verify comp map integrity
- [ ] Confirm source takes remain unmodified by comp edits

### Recovery validation

- [ ] Simulate interruption during recording and verify restore prompt appears
- [ ] Restore session and verify take pointers and loop/punch state
- [ ] Discard recovery and verify clean startup path

### Safety validation

- [ ] Device preflight returns readable failure for invalid I/O pairing
- [ ] Clip and silence warnings appear without blocking callback performance
- [ ] Existing Phase 1-5A workflows remain functional

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

- [ ] All P0 tickets complete
- [ ] P0 regression checklist passes
- [ ] No blocking recording regressions introduced in existing Phase 5A flow
- [ ] Build/status docs updated with implementation results
