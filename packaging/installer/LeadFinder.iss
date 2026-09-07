; LeadFinder per-user Windows installer (Inno Setup 6).
; Version is passed as /DAppVersion=x.y.z from packaging/build_windows.ps1.

#ifndef AppVersion
  #define AppVersion "1.3.0"
#endif

#ifndef SourceDir
  #define SourceDir "..\..\dist\LeadFinder"
#endif

#ifndef OutputDir
  #define OutputDir "..\..\dist\installer"
#endif

#define MyAppName "LeadFinder"
#define MyAppPublisher "FrancescoRamirezC"
#define MyAppURL "https://github.com/francescoramirez/local-business-lead-finder"
#define MyAppExeName "LeadFinder.exe"

[Setup]
AppId={{7C3E9B1A-4F2D-4A8E-9C11-A1B2C3D4E5F6}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppVerName={#MyAppName} {#AppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\LeadFinder
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=LeadFinder-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\..\src\leadfinder\desktop\assets\leadfinder.ico
LicenseFile=..\..\LICENSE
; User SQLite, logs, backups, and templates live under OS app-data, not {app}.
; Uninstall removes program files only.

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; WorkingDir: "{app}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch LeadFinder"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeUninstall(): Boolean;
begin
  Result := True;
  if not UninstallSilent then
    MsgBox('LeadFinder will be removed. Your local data folder (SQLite, backups, logs, pitch templates) is not deleted.', mbInformation, MB_OK);
end;
