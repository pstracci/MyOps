; Script para o Inno Setup do MyOps (gerado automaticamente)

[Setup]
AppName=MyOps
AppVersion=2.7.0
AppPublisher=MyOps Team
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
DefaultDirName={autopf}\MyOps
DefaultGroupName=MyOps
PrivilegesRequired=lowest
OutputBaseFilename=MyOps_Setup_2.7.0
OutputDir=Output
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\MyOps.exe

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Todos os arquivos do app, exceto log e config (sempre atualizados)
Source: "dist\MyOps\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "myops_debug.log,config.ini"
; config.ini: apenas instalado se nao existir (preserva conexoes do usuario)
Source: "dist\MyOps\config.ini"; DestDir: "{app}"; Flags: onlyifdoesntexist

[Icons]
Name: "{group}\MyOps"; Filename: "{app}\MyOps.exe"; WorkingDir: "{app}"
Name: "{group}\{cm:UninstallProgram,MyOps}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\MyOps"; Filename: "{app}\MyOps.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\MyOps.exe"; Description: "{cm:LaunchProgram,MyOps}"; Flags: nowait postinstall shellexec
