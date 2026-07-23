[Setup]
AppName=Echo Pro
AppVersion=1.0.0
DefaultDirName={localappdata}\EchoPro
DefaultGroupName=Echo Pro
OutputBaseFilename=EchoProInstaller
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern

[Files]
Source: "dist\EchoPro\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "install_echo_pro.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "EchoPro_Portable.bat"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Echo Pro"; Filename: "{app}\EchoPro.exe"
Name: "{commondesktop}\Echo Pro"; Filename: "{app}\EchoPro.exe"; Tasks: desktopicon
Name: "{group}\Echo Pro (Portable Mode)"; Filename: "{app}\EchoPro_Portable.bat"; Tasks: portablemode
Name: "{group}\Update Echo Pro Dependencies"; Filename: "{cmd}"; Parameters: "/C \"\"{app}\install_echo_pro.bat\" update\""; WorkingDir: "{app}"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; Flags: unchecked
Name: "installdeps"; Description: "Install runtime dependencies (ffmpeg, demucs runtime)"; Flags: checkedonce
Name: "portablemode"; Description: "Enable portable mode launcher (keep app data in install folder)"; Flags: unchecked

[Dirs]
Name: "{app}\data\projects"; Tasks: portablemode
Name: "{app}\data\voices"; Tasks: portablemode
Name: "{app}\data\generated"; Tasks: portablemode

[Run]
Filename: "{cmd}"; Parameters: "/C type nul > \"{app}\\.echo_portable\""; WorkingDir: "{app}"; Flags: runhidden; Tasks: portablemode
Filename: "{cmd}"; Parameters: "/C \"\"{app}\install_echo_pro.bat\" install\""; WorkingDir: "{app}"; Flags: runhidden; Tasks: installdeps
Filename: "{app}\EchoPro.exe"; Description: "Launch Echo Pro"; Flags: nowait postinstall skipifsilent