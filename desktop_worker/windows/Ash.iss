#ifndef SourceDir
  #define SourceDir "..\..\release\AshDesktop"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\release"
#endif
#ifndef MyAppVersion
  #define MyAppVersion "0.2.0"
#endif

#define MyAppName "Ash Desktop"
#define MyAppPublisher "Harvey & Co Digitals"
#define MyAppExeName "Ash.exe"

[Setup]
AppId={{8DB8BB77-0E43-43C0-AB13-8228B4B81D8B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Ash Desktop
DefaultGroupName=Ash Desktop
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=AshDesktopSetup-{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName=Ash Desktop
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
LicenseFile={#SourceDir}\LICENSE

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked
Name: "startup"; Description: "Start Ash when I sign in to Windows"; GroupDescription: "Startup:"; Flags: checkedonce

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Ash Desktop"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Ash Desktop"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\Ash Desktop"; Filename: "{app}\{#MyAppExeName}"; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Ash"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"
