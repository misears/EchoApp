# Echo Pro Release Instructions

This folder contains end-user distribution artifacts only.

## Folder layout

- `Installer/`
  - `EchoProInstaller.exe`
- `Portable/`
  - Portable app files (`EchoPro.exe`, `_internal`, etc.)
  - `EchoPro_Portable.bat`
  - `install_echo_pro.bat`
- `README.md`
  - Main usage guide

## Recommended install path (most users)

1. Open `Installer/EchoProInstaller.exe`.
2. Choose the application install folder.
3. Choose the separate Echo Pro data folder for projects, models, runtime tools, and generated content.
4. Select desktop mode, portable mode, or both.
5. Finish setup and let the dependency bootstrap complete.
6. Launch Echo Pro from the Start Menu or desktop shortcut.

## Portable path

1. Open `Portable/`.
2. Run `install_echo_pro.bat` once to set up local dependencies.
3. Run `EchoPro_Portable.bat` to launch the app.
4. By default, portable data is stored outside the app folder under `%LOCALAPPDATA%\EchoProData` unless `echo_home.txt` points elsewhere.

## Notes

- Keep all files in `Portable/` together.
- Do not move `EchoPro.exe` away from its bundled `_internal` folder.
- The installed or portable app should open with the tabbed interface immediately.
- Use the app's tabbed UI:
  - **Home**: waveform timeline + studio mixer
  - **Recording**: devices, transport, take review
  - **Voice FX** and **Music**: model-driven creative tools
