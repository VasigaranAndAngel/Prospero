#define MyAppName "Prospero"
#define MyAppExeName "Prospero.exe"
#define MyAppLauncherName "ProsperoLauncher.exe"
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

[Setup]
; Stable identity for upgrades and uninstall. Do not change it after the first release.
AppId={{7A4E2C2F-2B6D-4F31-9A7E-5C0D3B8F1A62}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=VasigaranAndAngel
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename={#MyAppName}Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\{#MyAppLauncherName}
PrivilegesRequired=lowest
CloseApplications=no
WizardStyle=modern

[Files]
; The launcher is the only stable path that shortcuts and scheduled tasks point at.
Source: "dist\{#MyAppLauncherName}"; DestDir: "{app}"; Flags: ignoreversion
; Every release gets its own immutable directory.
Source: "dist\Prospero\*"; DestDir: "{app}\versions\{#MyAppVersion}\Prospero"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppLauncherName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppLauncherName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppLauncherName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\current.txt"
Type: files; Name: "{app}\previous.txt"
Type: files; Name: "{app}\pending.txt"
Type: filesandordirs; Name: "{app}\versions"
Type: dirifempty; Name: "{app}"

[Code]
// Helper function to check if a command-line parameter exists
function CmdLineParamExists(const ParamName: string): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
  begin
    if CompareText(ParamStr(I), ParamName) = 0 then
    begin
      Result := True;
      Exit;
    end;
  end;
end;

function ShouldAutoStart: Boolean;
begin
  Result := WizardSilent and CmdLineParamExists('/AUTOSTART');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ErrorCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    // Point the launcher at the version this installer just placed on disk.
    SaveStringToFile(
      ExpandConstant('{app}\current.txt'),
      '{#MyAppVersion}',
      False
    );
  end;

  if (CurStep = ssDone) and ShouldAutoStart then
  begin
    Exec(
      ExpandConstant('{app}\{#MyAppLauncherName}'),
      '',
      '',
      SW_SHOWNORMAL,
      ewNoWait,
      ErrorCode
    );
  end;
end;
