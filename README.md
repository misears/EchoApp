# Echo Pro — Install & User Guide

Echo Pro is a local desktop audio production app with waveform editing, recording, stem separation, voice conversion, and music generation workflows.

## 1) Quick install

### Option A: Installer build (recommended for most users)
1. Run `EchoProInstaller.exe`.
2. Launch Echo Pro from the Start Menu shortcut.
3. On first run, use **Update Dependencies** if prompted.

### Option B: Portable / source folder run
1. Run `install_echo_pro.bat`.
2. Wait for setup to finish (FFmpeg, Demucs, RVC, ACE Step dependencies).
3. Start the app with `echo_pro_app.py` (dev) or `EchoPro_Portable.bat` (portable mode).

## 2) First run notes

- Audio files and projects are created under the app/project directories.
- Use valid input/output audio devices before recording.
- Voice conversion should only be used with voices you own or have permission to use.

## 3) Main interface layout

Echo Pro uses tabbed navigation:

- **Home**
  - Primary waveform timeline view.
  - Track list and project actions.
  - Studio mixer section directly below waveform area.
- **Recording**
  - Device selection and device tests.
  - Transport controls, take review, comping, recovery, and metering.
- **Voice FX**
  - Apply voice conversion to a selected clip with a selected profile.
- **Music**
  - Generate single clips or multi-section songs.
  - Alter/regenerate individual song sections.
- **Tools**
  - Utility actions (stems and regression checks).

## 4) Typical workflow

1. Create/open a project on **Home**.
2. Add tracks and clips.
3. Record takes on **Recording** (arm track -> record -> review takes).
4. Refine gain/mute/solo in **Home** studio mixer.
5. Use **Voice FX** and **Music** tabs as needed.
6. Save project frequently.

## 5) Troubleshooting

- If stems fail due to missing tools, run `install_echo_pro.bat update`.
- If recording fails, verify selected audio input/output devices in **Recording**.
- If a model-dependent feature is unavailable, run the installer/update again to refresh local assets.

## 6) Developer utilities location

End-user install/use files stay at repository root. Development-only helpers are organized under:

- `tools/dev/` (regression runners, smoke tests, build helpers, and backup variants)
