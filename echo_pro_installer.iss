[Setup]
AppName=Echo Pro
AppVersion=1.0.0
DefaultDirName={localappdata}\Programs\EchoPro
DefaultGroupName=Echo Pro
OutputBaseFilename=EchoProInstaller
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern
DisableDirPage=no

[Files]
Source: "dist\EchoPro\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "install_echo_pro.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "EchoPro_Desktop.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "EchoPro_Portable.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "seeds\Retrieval-based-Voice-Conversion-WebUI-main\*"; DestDir: "{app}\seeds\Retrieval-based-Voice-Conversion-WebUI-main"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "seeds\demucs-main\*"; DestDir: "{app}\seeds\demucs-main"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "seeds\FFmpeg-master\*"; DestDir: "{app}\seeds\FFmpeg-master"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "seeds\ACE-Step-1.5-main\*"; DestDir: "{app}\seeds\ACE-Step-1.5-main"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Echo Pro"; Filename: "{app}\EchoPro_Desktop.bat"; Tasks: desktopmode
Name: "{commondesktop}\Echo Pro"; Filename: "{app}\EchoPro_Desktop.bat"; Tasks: desktopicon desktopmode
Name: "{group}\Echo Pro (Portable Launcher)"; Filename: "{app}\EchoPro_Portable.bat"; Tasks: portablemode
Name: "{group}\Update Echo Pro Dependencies"; Filename: "{cmd}"; Parameters: "/C ""{app}\install_echo_pro.bat"" update"; WorkingDir: "{app}"
Name: "{group}\Uninstall Echo Pro"; Filename: "{uninstallexe}"
Name: "{group}\Open Echo Pro Folder"; Filename: "{app}"

[Tasks]
Name: "desktopmode"; Description: "Install desktop launcher"; Flags: checkedonce
Name: "portablemode"; Description: "Install portable launcher"; Flags: unchecked
Name: "desktopicon"; Description: "Create a desktop icon"; Flags: unchecked

[Run]
Filename: "{cmd}"; Parameters: "/C ""{app}\install_echo_pro.bat"" install"; WorkingDir: "{app}"; Flags: waituntilterminated
Filename: "{app}\EchoPro_Desktop.bat"; Description: "Launch Echo Pro"; Flags: nowait postinstall skipifsilent; Check: WizardIsTaskSelected('desktopmode')
Filename: "{app}\EchoPro_Portable.bat"; Description: "Launch Echo Pro Portable Launcher"; Flags: nowait postinstall skipifsilent; Check: (not WizardIsTaskSelected('desktopmode')) and WizardIsTaskSelected('portablemode')

[Code]
var
  DataDirPage: TInputDirWizardPage;

function GetSelectedDataDir: string;
begin
  Result := DataDirPage.Values[0];
end;

procedure InitializeWizard;
begin
  DataDirPage := CreateInputDirPage(
    wpSelectDir,
    'Choose Echo Pro data location',
    'Select where Echo Pro stores projects, models, runtime tools, and generated content.',
    'This location is kept separate from the application install folder to keep the program files clean.',
    False,
    ''
  );
  DataDirPage.Add('');
  DataDirPage.Values[0] := ExpandConstant('{localappdata}\EchoProData');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    ForceDirectories(ExpandConstant('{app}'));
    ForceDirectories(GetSelectedDataDir);
    SaveStringToFile(ExpandConstant('{app}\echo_home.txt'), GetSelectedDataDir, False);
  end;
end;