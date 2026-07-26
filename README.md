# Echo Pro — Install & User Guide

Echo Pro is a local desktop audio production app with waveform editing, recording, stem separation, voice conversion, and music generation workflows.

## 1) Quick install

### Option A: Installer build (recommended for most users)
1. Run `EchoProInstaller.exe`.
2. Choose the app install folder, then choose the separate Echo Pro data folder when prompted.
3. Select which launcher style to install: desktop, portable, or both.
4. Finish setup and let the installer run the dependency bootstrap automatically.
5. Launch Echo Pro from the Start Menu or desktop shortcut.

### Option B: Portable / source folder run
1. Run `install_echo_pro.bat`.
2. Wait for setup to finish (FFmpeg, Demucs, RVC, ACE Step dependencies).
3. Start the app with `Start_Echo.bat` for a one-click source launch, `echo_pro_app.py` for direct dev runs, or `EchoPro_Portable.bat` for portable mode.

## 2) Data location and first run notes

- App program files stay in the install folder you choose.
- Projects, models, runtime tools, and generated content stay in the separate Echo Pro data folder.
- If you do not choose a custom data folder, Echo Pro uses `%LOCALAPPDATA%\EchoProData`.
- Use valid input/output audio devices before recording.
- Voice conversion should only be used with voices you own or have permission to use.

## 3) Main interface layout

Echo Pro uses tabbed navigation:

- **Home**
  - Primary waveform timeline view.
  - Track list and compact hover-labeled project action icons for add, rename, delete, reorder, mute, solo, and arm operations.
  - Project transport icon controls for play, stop, and jumping to the current selection or selected clip boundaries, with labels exposed on hover.
  - Studio mixer section directly below waveform area.
  - Per-track playback settings for fades, loop region, and starter effects from each mixer strip's **FX** button.
- **Recording**
  - Device selection and compact hover-labeled device/test controls.
  - Hover-labeled icon actions for recording arm/setup, take review, comping, recovery, and transport.
- **Voice FX**
  - Apply voice conversion to a selected clip with a selected profile.
- **Music**
  - Generate single clips or multi-section songs.
  - Alter/regenerate individual song sections.
- **Tools**
  - Utility actions (stems and regression checks).

## 4) Typical workflow

1. Create/open a project on **Home**.
2. Use the Home header's hover-labeled project icons to create, open, save, or browse projects, then add tracks and clips with the action and tool icons below.
3. Use the **Home** transport icon buttons to play, stop, or jump to the current selection or selected clip boundaries during project editing.
4. Record takes on **Recording** using the hover-labeled arm/setup icons, transport controls, and take-review actions.
5. Refine gain/mute/solo and open per-track **FX** settings in **Home** studio mixer.
6. Use **Voice FX** and **Music** tabs as needed.
7. Save project frequently.

## 5) Troubleshooting

- If stems fail due to missing tools, run `install_echo_pro.bat update`.
- If you want a one-click source launch that bootstraps the runtime venv first, use `Start_Echo.bat` from the repo root.
- If recording fails, verify selected audio input/output devices in **Recording**.
- If a model-dependent feature is unavailable, rerun `install_echo_pro.bat update` to refresh local assets.

## 6) Developer utilities location

End-user install/use files stay at repository root. Development-only helpers are organized under:

- `tools/dev/` (regression runners, smoke tests, build helpers, and backup variants)

## 7) Task hub for backlog and follow-up work

For repository task tracking, ideas, active problems, and follow-up work, use [TASK_HUB.md](C:/Users/misea/OneDrive/Documents/AI%20Project%20Folders/EchoApp/TASK_HUB.md) as the actively maintained source of truth.
