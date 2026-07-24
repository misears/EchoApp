# ECHO PRO BUILD OUTLINE — Complete Phase Breakdown

<!-- markdownlint-disable MD024 MD040 MD060 -->

## 📋 PREREQUISITES & SETUP

Before starting any phase, ensure you have:

- Python 3.10+ installed with PATH configured
- Visual Studio Code with Python extension
- All required packages installed: `pip install pyside6 pydub simpleaudio sounddevice soundfile demucs`
- FFmpeg installed and PATH configured
- Project folder: `C:\EchoPro\EchoApp\`
- Repository initialized (optional but recommended)

---

## 🎚️ PHASE 5A/5B RECORDING ROADMAP ADDENDUM

This outline originally grouped recording into earlier implementation sessions and used Phase 5 for installer packaging only. The active roadmap now splits advanced recording into two explicit production phases before installer release work.

### Phase 5A (Complete): Recording Core Integration

- Multi-track recording controls in the main app
- Input/output device selection and test workflow
- Tempo, time signature, metronome, and count-in controls
- Live meter feedback with clipping indicators and reset
- Take metadata capture with undo/redo support

Primary reference: `PHASE_5A_RECORDING_PLAN.md`

### Phase 5B (In Progress): Recording Polish and Production Safety

- Punch-in/out transport and loop recording workflows
- Take browser and active-take selection
- Basic non-destructive comping flow
- Recovery flow for interrupted recording sessions
- Safety checks (disk/device/clip event guidance)

Primary reference: `PHASE_5B_RECORDING_PLAN.md`

### Phase 6 (Installer)

Phase 5 in this original document maps to Phase 6 in the active execution plan.

Phase 5A is now complete and validated. Phase 5B is the remaining recording work before installer release.

---

## 🎚️ PHASE 1: BUILD THE CORE DAW

### Goal

Create a functional multitrack digital audio workstation with basic project management.

### What Gets Built

- Project data model (tracks, clips, timeline)
- Audio file info extraction
- Visual timeline display
- Main application window
- File I/O for projects

### Deliverables

- `project_model.py` — Data structures for Project, Track, Clip
- `audio_info.py` — Audio file metadata extraction
- `timeline_widget.py` — Visual timeline rendering
- `app_paths.py` — Path management and directory setup
- `first_run.py` — First-run detection
- `echo_pro_app.py` — Main window and basic UI
- `.eproj` file format (JSON-based project files)

### Next Steps

- [ ] Create all Phase 1 Python files
- [ ] Test project creation (New Project → works?)
- [ ] Test track addition (Add Track → timeline updates?)
- [ ] Test clip addition with audio files
- [ ] Test project save/load cycle
- [ ] Verify timeline renders clips visually
- [ ] Test file dialog workflows
- [ ] Verify status bar updates
- [ ] Run full Phase 1 app and verify no crashes
- [ ] Document any issues or UX improvements

### Success Criteria

✅ Can create empty projects
✅ Can add multiple tracks
✅ Can add audio clips to tracks
✅ Timeline displays clips visually
✅ Projects save as `.eproj` files
✅ Can load previously saved projects

---

## 🎛️ PHASE 2: ADD STEMS, PLAYBACK, MIXING, FIRST RUN WIZARD

### Goal

Add professional audio processing: stem separation, playback mixing, and welcoming new users.

### What Gets Built

- Demucs integration for stem separation
- Real-time audio mixing engine
- Volume control system
- First-run welcome dialog
- Project browser/library view

### New/Modified Files

- `stems_engine.py` — Demucs integration and stem import
- `playback_mixer.py` — Audio mixing and playback
- **Modified `echo_pro_app.py`** — Add stems UI, playback controls, volume sliders, project browser
- **Modified `project_model.py`** — Add track volume_db field (already present)

### Next Steps

- [ ] Create `stems_engine.py` with Demucs wrapper
- [ ] Create `playback_mixer.py` with pydub mixing logic
- [ ] Test stem separation on sample audio file
- [ ] Verify stems load as new tracks
- [ ] Test playback of single clips
- [ ] Test playback with volume adjustments
- [ ] Test mixing multiple overlapping clips
- [ ] Verify First Run dialog shows on fresh installation
- [ ] Test Project Browser dialog opens and loads projects
- [ ] Add keyboard shortcuts for common actions (Ctrl+P = Play, etc.)
- [ ] Test error handling for missing audio files
- [ ] Verify demucs error messages are user-friendly

### Success Criteria

✅ Can split songs into stems using Demucs
✅ Stems automatically added as tracks
✅ Can play entire project mix
✅ Volume controls work (±12 dB range)
✅ First-run wizard shows on first launch
✅ Project Browser displays all saved projects
✅ Playback doesn't crash with invalid files

---

## 🎤 PHASE 3: VOICE RECORDING + VOICE CONVERSION HOOKS

### Goal

Add voice profile storage and placeholder voice conversion system.

### What Gets Built

- Voice profile storage with consent flags
- Microphone recording interface
- Voice Manager dialog
- Voice conversion placeholder (future replacement point)
- Ethical consent warnings

### New/Modified Files

- `voice_store.py` — Voice profile persistence (JSON index)
- `voice_recorder.py` — Microphone recording via sounddevice
- `voice_interface.py` — Future-proof voice conversion interfaces
- `voice_effects.py` — Voice conversion wrapper (placeholder)
- **Modified `echo_pro_app.py`** — Add voice UI, manager dialog, apply voice effects button

### Next Steps

- [ ] Create `voice_store.py` with profile persistence
- [ ] Create `voice_recorder.py` with 10s recording
- [ ] Create `voice_interface.py` with frozen dataclass interfaces
- [ ] Create `voice_effects.py` placeholder implementation
- [ ] Test recording a voice profile (10 seconds)
- [ ] Verify voice profiles save to `%APPDATA%\EchoPro\voices\`
- [ ] Test loading and listing voice profiles
- [ ] Test applying placeholder voice effect to a clip
- [ ] Verify consent warnings appear and are mandatory
- [ ] Test Voice Manager dialog open/close
- [ ] Create 5+ test voice profiles and verify all load
- [ ] Test voice effect creates new track correctly
- [ ] Document the voice_interface.py frozen interface for future model replacement

### Success Criteria

✅ Can record voice profiles (10s minimum)
✅ Voice profiles stored with consent metadata
✅ Can list all recorded voices
✅ Can apply voice effect to any clip
✅ New track created with converted audio
✅ Consent warning mandatory before use
✅ Interface allows easy future model replacement

### Future Integration Point

Replace `voice_interface.voice_convert()` function body with:

```python
# Real voice conversion model integration here
# Input: request.source_wav, request.target_profile
# Output: VoiceConvertResult with converted audio
```

---

## 🎵 PHASE 4: MUSIC GENERATOR + SONG PLANNER

### Goal

Add AI music generation capabilities with flexible backend selection.

### What Gets Built

- Text-to-music (T2M) interface with offline/cloud backends
- Single clip generation UI
- Full song planning and generation
- Lyrics splitting across song structure
- Duration planning per section
- Cloud toggle for backend selection

### New/Modified Files

- `t2m_interface.py` — Frozen T2M generation interfaces
- `music_generator.py` — T2M wrapper and clip generation
- `song_planner.py` — Song structure planning and multi-clip generation
- **Modified `echo_pro_app.py`** — Add generator UI, song planner UI, cloud toggle

### Next Steps

- [ ] Create `t2m_interface.py` with frozen dataclass interfaces
- [ ] Create `music_generator.py` with placeholder (silent clips for now)
- [ ] Create `song_planner.py` with lyrics splitting and duration planning
- [ ] Test single clip generation (10-30 seconds)
- [ ] Verify generated clips added as new tracks
- [ ] Test song generation with multi-section structure (Intro/Verse/Chorus/Outro)
- [ ] Test lyrics splitting across sections
- [ ] Test duration planning (e.g., 60 second song = 4 equal 15s sections)
- [ ] Test cloud toggle UI (yes/no input)
- [ ] Test all generation parameters (style, genre, mood, tempo, key, chords, time signature)
- [ ] Verify generated files saved to `%APPDATA%\EchoPro\generated\{project_name}\`
- [ ] Create comprehensive test cases for 5+ song structures
- [ ] Document the t2m_interface.py frozen interface

### Success Criteria

✅ Can generate single music clips (placeholder audio)
✅ Can generate full songs with multiple sections
✅ Lyrics properly split and assigned to sections
✅ Duration planning works for any song length
✅ Generated clips automatically added to project
✅ Cloud toggle influences backend selection
✅ Interface supports future model replacement

### Future Integration Point

Replace `t2m_interface.t2m_generate_clip()` function body with:

```python
# Real T2M model integration here
# Can be: Stable Audio, AudioLDM, custom model
# Input: request (style, genre, mood, lyrics, etc.)
# Output: T2MClipResult with real audio file
```

---

## 📦 PHASE 5: BUILD THE WINDOWS INSTALLER

### Goal

Package Echo Pro as a professional Windows application with installer.

### What Gets Built

- PyInstaller executable (EchoPro.exe)
- Inno Setup installer script (EchoProInstaller.exe)
- Start Menu shortcuts
- Desktop shortcut
- Application registry entries
- First-run extraction logic
- Dependency installer flow for ffmpeg and demucs runtime
- Dependency update flow after initial install
- Portable mode launcher keeping app + data together on external drive

### New/Modified Files

- `EchoPro.spec` — PyInstaller build configuration
- `echo_pro_installer.iss` — Inno Setup installer script
- `build_exe.bat` — Batch script for building EXE
- `install_echo_pro.bat` — Runtime dependency install/update manager
- `EchoPro_Portable.bat` — Portable launcher and local data bootstrap
- **.gitignore** — Exclude build/ and Output/ directories

### Build Artifacts

- `build/` — PyInstaller intermediate files
- `dist/EchoPro.exe` — Final executable
- `Output/EchoProInstaller.exe` — Final installer

### Next Steps

- [ ] Create `EchoPro.spec` PyInstaller configuration
- [ ] Configure PyInstaller to include all Python files
- [ ] Configure PyInstaller to include data directories
- [ ] Create `build_exe.bat` script
- [ ] Test building EchoPro.exe locally
- [ ] Verify EchoPro.exe runs without Python installed
- [ ] Verify all UI dialogs work in EXE
- [ ] Create `echo_pro_installer.iss` Inno Setup script
- [ ] Configure installer to extract to `%LOCALAPPDATA%\EchoPro\`
- [ ] Configure Start Menu shortcuts
- [ ] Configure Desktop shortcut
- [ ] Configure dependency install task during setup (`install_echo_pro.bat install`)
- [ ] Configure dependency update entry point (`install_echo_pro.bat update`)
- [ ] Configure portable mode task and launcher (`EchoPro_Portable.bat`)
- [ ] Create uninstall logic
- [ ] Test installer on clean Windows VM or second machine
- [ ] Verify first-run wizard triggers on fresh install
- [ ] Verify projects persist across updates
- [ ] Verify dependency update works post-install without full reinstall
- [ ] Verify portable mode works from removable drive with local `data/` folder
- [ ] Test uninstall removes all files correctly
- [ ] Create release notes for v0.1
- [ ] Sign installer (optional, for trust)

### Success Criteria

✅ EchoPro.exe runs without Python installation
✅ Installer creates Start Menu shortcuts
✅ Installer creates Desktop shortcut
✅ Installer can install runtime dependencies
✅ Installer exposes dependency update workflow after install
✅ Portable mode keeps app and data together for removable drive usage
✅ First-run wizard shows for new users
✅ Projects directory persists after uninstall (user choice)
✅ Clean uninstall removes all application files
✅ Can reinstall cleanly after uninstall
✅ All audio features work in EXE version

### Installation Verification Checklist

- [ ] Installer runs without admin (if possible)
- [ ] No missing DLL errors
- [ ] FFmpeg integration works (if bundled)
- [ ] Demucs available (or user can install)
- [ ] Dependency installer succeeds on clean machine
- [ ] Dependency update path works after install
- [ ] Portable launcher creates and uses local `data/` root
- [ ] Portable build runs from external USB path after drive letter change
- [ ] Microphone access works
- [ ] File dialogs show correct initial paths
- [ ] First-run wizard completes
- [ ] Can create new project immediately
- [ ] Can save project and close
- [ ] Can reopen application and load project
- [ ] Add track → works
- [ ] Add clip → works
- [ ] Playback → works
- [ ] Stems → works (if Demucs installed)
- [ ] Voice recording → works
- [ ] Generate clip → works

---

## ✅ POST-BUILD TASKS

### Documentation

- [ ] Create user guide (Getting Started)
- [ ] Document voice conversion interface for developers
- [ ] Document T2M interface for developers
- [ ] Create troubleshooting guide
- [ ] Add video tutorial links (if creating them)

### Quality Assurance

- [ ] Run full test suite (5+ complete workflows)
- [ ] Test on Windows 10 and Windows 11
- [ ] Test with various audio formats (MP3, WAV, FLAC, OGG)
- [ ] Test with very long songs (30+ minutes)
- [ ] Test with complex projects (10+ tracks)
- [ ] Test error recovery (corrupted files, missing audio)
- [ ] Performance test (profile large projects)

### Optimization

- [ ] Profile memory usage
- [ ] Optimize timeline rendering for many clips
- [ ] Add progress bars for long operations (Demucs, generation)
- [ ] Cache audio length calculations
- [ ] Consider multithreading for playback

### Optional Enhancements

- [ ] Undo/Redo system
- [ ] Keyboard shortcuts documentation
- [ ] Dark/Light theme toggle
- [ ] Audio visualization (waveform display)
- [ ] Clip trimming/splitting UI
- [ ] Marker/cue point system
- [ ] Export to MP3/FLAC
- [ ] Plugin system for custom effects

---

## 🔄 PHASE TRANSITION CHECKLIST

### Phase 1 → Phase 2 Requirements

- [ ] All Phase 1 files created and tested
- [ ] No crashes on basic operations
- [ ] Project save/load verified working
- [ ] Timeline renders correctly

### Phase 2 → Phase 3 Requirements

- [ ] Demucs integrated and tested
- [ ] Playback working (test with 2+ tracks)
- [ ] Volume controls working
- [ ] First Run wizard functional

### Phase 3 → Phase 4 Requirements

- [ ] Voice recording works
- [ ] Voice profiles persist
- [ ] Consent warnings functional
- [ ] Placeholder voice effect creates clips

### Phase 4 → Phase 5A Requirements

- [x] Single clip generation works (placeholder)
- [x] Song generation works (placeholder)
- [x] All 4 AI interfaces frozen and documented
- [x] No critical bugs in main app workflow

### Phase 5A → Phase 5B Requirements

- [x] Stable recording start/stop across supported devices
- [x] Count-in and timing controls validated with real recordings
- [x] Meter clipping/peak feedback validated during sessions
- [x] Track arm/select/mute/solo behavior verified while recording

### Phase 5B → Phase 6 Requirements

- [ ] Punch and loop workflows stable in real sessions
- [ ] Take selection/comping saves and reloads reliably
- [ ] Recovery flow tested on interrupted sessions
- [ ] No major regressions in Phase 1-5A features

### Phase 6 → Release Requirements

- [ ] EXE builds and runs standalone
- [ ] Installer creates shortcuts
- [ ] Uninstall removes files
- [ ] All Phase 1-5B features work in installed version
- [ ] No import errors or missing modules
- [ ] User can reinstall and start over

---

## 📊 PROGRESS TRACKING

| Phase | Status | Start Date | End Date | Complete % | Notes |
|-------|--------|-----------|----------|-----------|-------|
| Setup | ✅ Complete | - | - | 100% | Dependencies and foundation ready |
| Phase 1 | ✅ Complete | - | - | 100% | Core DAW |
| Phase 2 | ✅ Complete | - | - | 100% | Audio features |
| Phase 3 | ✅ Complete | - | - | 100% | Voice system |
| Phase 4 | ✅ Complete | - | - | 100% | AI generation |
| Phase 5A | ✅ Complete | - | - | 100% | Recording core integration |
| Phase 5B | 🚧 In Progress | - | - | 65% | Recording polish + safety |
| Phase 6 | ⏳ Pending | - | - | 0% | Installer |
| Testing | ⏳ Pending | - | - | - | Full QA |

---

## 🚨 KNOWN LIMITATIONS & FUTURE WORK

### Placeholder Systems (To Be Replaced)

- Voice conversion currently only adjusts gain (dB)
- Music generation outputs silent clips
- No real AI model integration yet

### Not Included in v0.1

- Undo/Redo system
- Clip editing (trim, split, fade)
- VST plugin support
- Real-time waveform visualization
- Audio effects rack
- MIDI support
- Bouncing/rendering to single file

### Performance Assumptions

- Assumes projects < 100 clips
- Assumes < 20 tracks per project
- Assumes audio files on local disk (not network)
- Demucs processing may take 1-5 minutes per song

---

## 🔗 INTEGRATION POINTS FOR AI MODELS

### Voice Conversion Model

**File:** `voice_interface.py::voice_convert()`

```
Replace placeholder implementation with:
- Model loading: `model = load_voice_model(...)`
- Inference: `converted = model.convert(source, target_embedding)`
- Supported models: Resembler, VITS, RVC, Covarep, etc.
```

### Text-to-Music Model

**File:** `t2m_interface.py::t2m_generate_clip()`

```
Replace placeholder implementation with:
- Model loading: `model = load_t2m_model(...)`
- Inference: `audio = model.generate(request)`
- Supported models: Stable Audio, AudioLDM, MusicGen, Riffusion, etc.
```

Both interfaces are frozen (no UI changes required).

---

## 🎯 SUCCESS CRITERIA FOR COMPLETE BUILD

The Echo Pro build is **COMPLETE** when:

1. ✅ All 6 phases implemented
2. ✅ No syntax errors (verified by linter)
3. ✅ All features tested individually
4. ✅ Full workflow tested end-to-end
5. ✅ Installer creates working app
6. ✅ Works on clean Windows installation
7. ✅ All dialogs responsive
8. ✅ All file I/O reliable
9. ✅ Error handling doesn't crash
10. ✅ Documentation complete
