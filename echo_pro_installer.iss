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

[Icons]
Name: "{group}\Echo Pro"; Filename: "{app}\EchoPro.exe"
Name: "{commondesktop}\Echo Pro"; Filename: "{app}\EchoPro.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; Flags: unchecked

[Run]
Filename: "{app}\EchoPro.exe"; Description: "Launch Echo Pro"; Flags: nowait postinstall skipifsilent