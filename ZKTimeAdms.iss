[Setup]
AppName=ZKTimeAdms
AppVersion=1.0
DefaultDirName={pf}\ZKTimeAdms
OutputBaseFilename=ZKTimeAdmsInstaller
SetupIconFile=app_icon.ico
PrivilegesRequired=admin
DisableProgramGroupPage=yes
DisableStartupPrompt=yes

[Files]
Source: "dist\ZKTimeAdms.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\ZKTimeAdms"; Filename: "{app}\ZKTimeAdms.exe"; IconFilename: "{app}\app_icon.ico"

[Run]
Filename: "{app}\ZKTimeAdms.exe"; Description: "Start ZKTimeAdms"; Flags: nowait postinstall

[Code]
var
  ResultCode: Integer;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Add to Windows startup
    Exec('reg', 'add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "ZKTimeAdms" /t REG_SZ /d "' +
         ExpandConstant('{app}\ZKTimeAdms.exe') + '" /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

    // Add firewall rule to allow port 5015
    Exec('netsh', 'advfirewall firewall add rule name="ZK ADMS 5015" dir=in action=allow protocol=TCP localport=5015',
         '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
