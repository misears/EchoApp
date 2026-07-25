# Phase 5B Recording Polish and Production Safety Plan

Status: Ready to build  
Scope: Recording reliability, take comping workflow, punch/loop capture, and session safety tooling  
Placement: Phase 5B in the V1.0 roadmap (after Phase 5A)

## Objective

Turn the Phase 5A recording foundation into a dependable production workflow by adding polish features that reduce mistakes, speed up iteration, and improve take decisions.

## Why This Phase Matters

Phase 5A delivers core capture. Phase 5B makes capture practical in repeated daily use: better punch-ins, cleaner take review, safer session recovery, and stronger confidence before export/mix.

## Deliverables

- Punch-in and punch-out controls with bar/time positioning
- Loop recording mode with automatic take incrementing
- Take review panel with active-take selection per track
- Basic comping workflow (choose active regions/takes)
- Recording safety checks (disk space, clipping warnings, armed-track validation)
- Recovery flow for interrupted sessions
- Recording QA checks and diagnostics summary

## Build Order

### 1. Transport and Capture Modes

Extend recording transport with pro capture modes.

- Add punch-in and punch-out start/stop boundaries
- Add loop-record mode with cycle restart
- Add pre-roll and post-roll options
- Ensure timing works with metronome and count-in

### 2. Take Organization and Selection

Improve take visibility and decision speed.

- Show takes grouped by track
- Display take metadata (timestamp, duration, peak/clipping)
- Let user mark takes as keeper or muted
- Let user choose active take per track

### 3. Comping Workflow (V1)

Provide first comping pass without heavy DAW complexity.

- Split selected timeline range into comp regions
- Assign preferred take per region
- Rebuild playback from selected comp map
- Preserve non-destructive source takes

### 4. Safety and Recovery

Reduce loss risk and improve failure behavior.

- Validate available disk space before recording
- Add recording interrupt recovery prompt
- Auto-save session metadata on state changes
- Show clear errors for failed I/O or bad device state

### 5. UI Integration and Usability

Integrate with current Echo Pro main window cleanly.

- Add punch/loop controls in recording panel
- Add take browser and active-take selector
- Add comping action buttons
- Add compact diagnostics panel (latency, clip events, recovery status)

## Proposed Files

- recording_controller.py - punch/loop capture orchestration
- recording_session.py - active-take and comp metadata structures
- recording_ui_components.py - take list widgets and comping controls
- timeline_widget.py - range selection helpers for comp regions
- echo_pro_app.py - UI wiring for punch/loop/take management
- new: recording_recovery.py - crash/interruption recovery helpers

## Existing Files to Reuse

- metronome.py - timing and count-in synchronization
- audio_device.py - latency and device validation
- audio_engine.py - real-time callbacks and level telemetry
- undo_manager.py - reversible recording actions
- app_paths.py - session and metadata storage paths

## User Flow

1. User arms one or more tracks and enables loop or punch mode.
2. User records multiple takes through cycles.
3. Echo Pro creates and tags takes per cycle automatically.
4. User reviews takes in the take panel and marks preferred takes.
5. User selects comp regions and assigns best take per region.
6. Echo Pro rebuilds playback non-destructively from comp map.
7. User saves and can recover state if app/device interruption occurs.

## Acceptance Criteria

- Punch-in/out recording starts and stops on expected timeline positions
- Loop recording creates multiple takes without overwriting old takes
- User can select active take per track quickly from UI
- Comp map playback uses selected takes per region
- Interrupted session can be restored with minimal data loss
- Safety checks show readable guidance before recording starts
- Existing Phase 1-5A features continue to work

## Validation Plan

- Run module import checks for all touched files
- Run recording loop test with at least 4 automatic takes
- Verify punch-in/out timing against set bar markers
- Validate active-take switching updates playback result
- Simulate interruption and verify recovery prompt/data restore
- Confirm comp map serialization in project/session metadata
- Verify no regressions in save/load and timeline drawing

## Risks and Constraints

- Punch/loop timing can drift if callback work is heavy
- Comping logic can become complex if clip boundaries are not normalized
- Recovery system must avoid corrupting valid sessions
- UI complexity can increase quickly if take/comp controls are overextended

## Recommended Implementation Sequence

1. Add punch/loop state model in recording_controller.py.
2. Add take metadata extensions in recording_session.py.
3. Build take browser UI and active-take selection.
4. Add comp region selection and mapping.
5. Add recovery checks and restore flow.
6. Run integration QA across recording, playback, and save/load.

## Definition of Done

Phase 5B is complete when users can record repeated takes using loop or punch workflows, select preferred takes quickly, build a basic comp without destructive edits, and recover from interrupted sessions with stable project state.
