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
2. Complete setup.
3. Launch Echo Pro from Start Menu or desktop shortcut.
4. If prompted for missing dependencies, run update from the app flow.

## Portable path

1. Open `Portable/`.
2. Run `install_echo_pro.bat` once to set up local dependencies.
3. Run `EchoPro_Portable.bat` to launch the app.

## Notes

- Keep all files in `Portable/` together.
- Do not move `EchoPro.exe` away from its bundled `_internal` folder.
- Use the app's tabbed UI:
  - **Home**: waveform timeline + studio mixer
  - **Recording**: devices, transport, take review
  - **Voice FX** and **Music**: model-driven creative tools
