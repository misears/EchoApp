# Phase 5A Recording Implementation Plan

**Status:** Ready to build  
**Scope:** Professional recording workflow, metering, metronome, and recording session controls  
**Placement:** Phase 5A in the V1.0 roadmap

## Objective
Build the recording experience that turns Echo Pro from a generation-focused app into a practical music production tool. This phase should make it possible to capture clean takes, monitor input levels, manage multiple takes, and record in time with a project tempo.

## Why This Phase Matters
Phase 0 created the foundation: real-time audio routing, plugin chains, device selection, and take/session management. Phase 5A uses that foundation to deliver the first truly professional workflow that users will feel immediately.

## Deliverables
- Multi-track recording controls in the main app
- Input/output device selection and configuration
- Metronome / click track generation synced to tempo
- Track and input level meters
- Take creation, undo, redo, and take history
- Recording presets for common workflows
- Recording status feedback and safety checks

## Build Order

### 1. Recording Core
Build the recording control layer on top of the audio engine.
- Start and stop recording state
- Connect recording state to active track(s)
- Store take metadata through `recording_session.py`
- Capture level statistics during recording
- Guard against invalid device or track selections

### 2. Metronome and Timing
Add timing support so users can record musical ideas in time.
- Generate click tracks at the project tempo
- Support common time signatures
- Provide count-in before recording starts
- Allow click volume control
- Keep the click isolated from recorded material

### 3. Monitoring and Metering
Give users confidence while recording.
- Show live input level meters
- Show peak and clipping indicators
- Display recording status per track
- Warn when gain is too hot or the input is silent
- Keep meters responsive without blocking audio callbacks

### 4. Undo / Redo and Take Management
Make recording safe to iterate on.
- Add take history for each track
- Allow undo of the last take
- Allow redo after undo
- Keep recent takes visible and selectable
- Preserve metadata for each take

### 5. UI Integration
Wire the recording workflow into `echo_pro_app.py`.
- Add record / stop buttons
- Add device selectors
- Add metronome controls
- Add meter widgets
- Add take management controls
- Add clear user feedback for recording state

## Proposed Files
- `metronome.py` - click track generation and tempo sync
- `undo_manager.py` - recording undo / redo abstraction
- `recording_ui_components.py` - reusable Qt widgets for meters and transport controls
- `recorder.py` - recording orchestration layer on top of the audio engine
- `echo_pro_app.py` - UI integration for recording controls

## Existing Files to Reuse
- `audio_engine.py` - low-latency engine and track handling
- `audio_device.py` - device discovery and latency checks
- `recording_session.py` - take history and presets
- `plugin_system.py` - metering-safe effects chain when monitoring
- `app_paths.py` - storage locations

## User Flow
1. User selects a project and opens the recording panel.
2. User chooses an input device and monitoring setup.
3. User enables the metronome and sets tempo if needed.
4. User arms one or more tracks.
5. User presses record and captures a take.
6. Echo Pro stores the take, levels, and metadata.
7. User undoes or redoes takes as needed.
8. User keeps the best take and continues production.

## Acceptance Criteria
- Can record at least one track with stable input monitoring
- Can record multiple takes without losing prior takes
- Metering updates during recording and playback
- Metronome follows project tempo accurately
- Undo / redo works for the most recent takes
- Device selection failures fail gracefully with a readable message
- Existing Phase 1-4 features continue to work

## Validation Plan
- Import all new modules without syntax errors
- Record a short test take and confirm metadata is saved
- Verify click track timing against a known tempo
- Test undo / redo on at least three takes
- Verify meters show clip and peak states
- Test invalid device selection and confirm user-safe handling
- Run the main app and confirm recording controls do not break project load/save

## Risks and Constraints
- Real-time audio callbacks can fail if too much work happens on the UI thread
- Metering must stay lightweight to avoid dropouts
- Device behavior can vary across Windows machines and drivers
- Take history must remain consistent if a session is interrupted

## Recommended Implementation Sequence
1. Connect recording state to the existing audio engine.
2. Add metronome generation and tempo sync.
3. Add meter widgets and level handling.
4. Add undo / redo and take persistence.
5. Integrate all controls into the Qt UI.
6. Validate recording on a real device and fix edge cases.

## Definition of Done
Phase 5A is complete when a user can open Echo Pro, choose an input device, record a timed take with metronome support, see live meters, and recover from mistakes with undo / redo without destabilizing the rest of the app.
