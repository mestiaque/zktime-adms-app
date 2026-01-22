[Setup]
AppName=ZKTimeSync
AppVersion=1.0
DefaultDirName={pf}\ZKTimeSync
OutputBaseFilename=ZKTimeSyncInstaller
SetupIconFile=app_icon.ico
PrivilegesRequired=admin
DisableProgramGroupPage=yes
DisableStartupPrompt=yes

[Files]
Source: "dist\ZKTimeSync.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\ZKTimeSync"; Filename: "{app}\ZKTimeSync.exe"; IconFilename: "{app}\app_icon.ico"

[Run]
Filename: "{app}\ZKTimeSync.exe"; Description: "Start ZKTimeSync"; Flags: nowait postinstall

[Code]
// Auto add to startup + firewall
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    Exec('reg', 'add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "ZKTimeSync" /t REG_SZ /d "' + ExpandConstant('{app}\ZKTimeSync.exe') + '" /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec('netsh', 'advfirewall firewall add rule name="ZK ADMS 5015" dir=in action=allow protocol=TCP localport=5015', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
