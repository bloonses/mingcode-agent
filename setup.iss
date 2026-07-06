; MINGCODE Installer Script
; For Inno Setup 6

#define MyAppName "MINGCODE"
#define MyAppVersion "1.4.0"
#define MyAppPublisher "MINGCODE Team"
#define MyAppExeName "mingcode.exe"

[Setup]
AppId={{B8A2F7D4-1E3C-4F5A-9B7D-2C8E6F1A3B5C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=dist
OutputBaseFilename=MINGCODE-Setup-{#MyAppVersion}
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
ChangesEnvironment=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "addtopath"; Description: "Add to PATH (run mingcode from any terminal)"; GroupDescription: "Additional options:"; Flags: checkedonce

[Files]
Source: "dist\mingcode.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}";
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName} now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
function NeedAddToPath: Boolean;
var
  Paths: string;
  AppDir: string;
begin
  Result := False;
  if not WizardIsTaskSelected('addtopath') then
    Exit;
  
  AppDir := ExpandConstant('{app}');
  Paths := GetEnv('PATH');
  
  if Pos(';' + AppDir + ';', ';' + Paths + ';') > 0 then
    Exit;
  
  if not DirExists(AppDir) then
    Exit;
  
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  OldPath: string;
  NewPath: string;
begin
  if CurStep = ssPostInstall then
  begin
    if NeedAddToPath then
    begin
      OldPath := GetEnv('PATH');
      NewPath := OldPath + ';' + ExpandConstant('{app}');
      RegWriteStringValue(HKCU, 'Environment', 'PATH', NewPath);
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  OldPath: string;
  AppDir: string;
  P: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    AppDir := ExpandConstant('{app}');
    OldPath := GetEnv('PATH');
    
    P := Pos(';' + AppDir, OldPath);
    while P > 0 do
    begin
      Delete(OldPath, P, Length(';' + AppDir));
      P := Pos(';' + AppDir, OldPath);
    end;
    
    P := Pos(AppDir + ';', OldPath);
    while P > 0 do
    begin
      Delete(OldPath, P, Length(AppDir + ';'));
      P := Pos(AppDir + ';', OldPath);
    end;
    
    if OldPath = AppDir then
      OldPath := '';
    
    RegWriteStringValue(HKCU, 'Environment', 'PATH', OldPath);
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpFinished then
  begin
    WizardForm.FinishedLabel.Caption := 
      'MINGCODE has been successfully installed!' + #13#10#13#10 +
      'To get started:' + #13#10 +
      '  1. OPEN A NEW COMMAND PROMPT / POWERShell' + #13#10 +
      '     (existing terminals will not pick up the new PATH immediately)' + #13#10 +
      '  2. Type: ' + 'mingcode' + #13#10 +
      '  3. On first run, type /settings to configure your LLM provider' + #13#10#13#10 +
      'Type /help in the program to see all available commands.';
  end;
end;
