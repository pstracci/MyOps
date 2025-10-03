; Script para o Inno Setup do MyOps (gerado automaticamente)

[Setup]
AppName=MyOps
AppVersion=2.1.0
AppPublisher=MyOps Team
DefaultDirName={autopf}\MyOps
DefaultGroupName=MyOps
PrivilegesRequired=lowest
OutputBaseFilename=MyOps_Setup_2.1.0
OutputDir=Output
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\MyOps.exe

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\MyOps\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "myops_debug.log"

[Icons]
Name: "{group}\MyOps"; Filename: "{app}\MyOps.exe"
Name: "{group}\{cm:UninstallProgram,MyOps}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\MyOps"; Filename: "{app}\MyOps.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MyOps.exe"; Description: "{cm:LaunchProgram,MyOps}"; Flags: nowait postinstall shellexec
