#define MyAppName "BlueJ FRI Edition"
#define MyAppVersion "###VER###"
#define MyAppPublisher "BlueJ Team; Fakulta riadenia a informatiky, Zilinska univerzita v Ziline"
#define MyAppURL "https://github.com/infjava"
#define MyAppExeName "BlueJ.exe"

[Setup]
AppId={{C046C078-4663-4DE2-BFDF-1B00234A0C80}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName=BlueJ FRI
AllowNoIcons=yes
LicenseFile=bluej\LICENSE.txt
OutputDir=output
OutputBaseFilename=BlueJFRI-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
ChangesAssociations=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "associations"; Description: "Create file association (*.bluej)"; GroupDescription: "File associations"

[Dirs]
; BlueJ stores per-user settings in %USERPROFILE%\bluej on Windows.
; Create it immediately for the user running the installer.
Name: "{userprofile}\bluej"

[Files]
Source: "bluej\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\View README"; Filename: "{app}\README.TXT"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKLM; Subkey: "Software\Classes\.bluej"; ValueType: string; ValueName: ""; ValueData: "BlueJProject"; Flags: uninsdeletevalue; Tasks: associations
Root: HKLM; Subkey: "Software\Classes\BlueJProject"; ValueType: string; ValueName: ""; ValueData: "BlueJ project file"; Flags: uninsdeletekey; Tasks: associations
Root: HKLM; Subkey: "Software\Classes\BlueJProject\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\BlueJ.exe,0"; Flags: uninsdeletekey; Tasks: associations
Root: HKLM; Subkey: "Software\Classes\BlueJProject\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\BlueJ.exe"" ""%1"""; Flags: uninsdeletekey; Tasks: associations

; Active Setup runs once for every Windows user profile. This also covers users
; created after BlueJ FRI was installed. A new BlueJ FRI release updates Version,
; causing the idempotent command to run again for existing users as well.
Root: HKLM; Subkey: "Software\Microsoft\Active Setup\Installed Components\{{31AFDAF5-4B71-47D2-A47B-50C640C77A49}"; ValueType: string; ValueName: ""; ValueData: "BlueJ FRI user profile initialization"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\Microsoft\Active Setup\Installed Components\{{31AFDAF5-4B71-47D2-A47B-50C640C77A49}"; ValueType: string; ValueName: "Version"; ValueData: "{#StringChange(MyAppVersion, '.', ',')}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\Microsoft\Active Setup\Installed Components\{{31AFDAF5-4B71-47D2-A47B-50C640C77A49}"; ValueType: string; ValueName: "StubPath"; ValueData: """{cmd}"" /C if not exist ""%USERPROFILE%\bluej"" mkdir ""%USERPROFILE%\bluej"""; Flags: uninsdeletekey
