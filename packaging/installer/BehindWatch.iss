#ifndef MyAppVersion
  #error MyAppVersion must be supplied by the build script
#endif
#define MyAppName "BehindWatch"

[Setup]
AppId={{714EA088-174C-4650-85B0-A2CC2E7EB47F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=zensoku142
AppPublisherURL=https://github.com/zensoku142/BehindWatch
AppSupportURL=https://github.com/zensoku142/BehindWatch/issues
AppUpdatesURL=https://github.com/zensoku142/BehindWatch/releases
DefaultDirName={localappdata}\Programs\BehindWatch
DefaultGroupName=BehindWatch
PrivilegesRequired=lowest
UsePreviousAppDir=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist-installer
OutputBaseFilename=BehindWatch-Setup-v{#MyAppVersion}-x64
SetupIconFile=..\..\assets\BehindWatch.ico
UninstallDisplayIcon={app}\BehindWatch.exe
; 使用更大压缩字典减小下载体积，不改变安装后的文件及运行内存。
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
DisableProgramGroupPage=yes

[Languages]
Name: "chinesesimplified"; MessagesFile: "languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "..\..\dist\BehindWatch\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userdesktop}\BehindWatch"; Filename: "{app}\BehindWatch.exe"; Tasks: desktopicon
Name: "{group}\BehindWatch"; Filename: "{app}\BehindWatch.exe"
Name: "{group}\卸载 BehindWatch"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\BehindWatch.exe"; Description: "{cm:LaunchProgram,BehindWatch}"; Flags: nowait postinstall skipifsilent; Check: not IsUpdateMode
Filename: "{app}\BehindWatch.exe"; Flags: nowait skipifdoesntexist; Check: IsUpdateMode

[Code]
function IsUpdateMode: Boolean;
var I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), '/BEHINDWATCHUPDATE') = 0 then
    begin
      Result := True;
      Exit;
    end;
end;
