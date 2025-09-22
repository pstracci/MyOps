; Script para o Inno Setup do MyOps
; Criado em 21/09/2025

[Setup]
; --- Informações básicas do aplicativo ---
AppName=MyOps
AppVersion=1.0.0
AppPublisher=MyOps Team
DefaultDirName={autopf}\MyOps
DefaultGroupName=MyOps
PrivilegesRequired=lowest
OutputBaseFilename=MyOps_Setup_1.0.0
Compression=lzma
SolidCompression=yes

; --- Aparência do assistente de instalação (Wizard) ---
WizardStyle=modern
; Imagem grande que aparece à esquerda do assistente
WizardImageFile=build_assets\fundo.bmp
; Imagem pequena que aparece no canto superior direito
WizardSmallImageFile=build_assets\fundo.bmp
; Ícone que aparecerá em "Adicionar/Remover Programas"
UninstallDisplayIcon={app}\MyOps.exe


[Languages]
; Define o idioma do instalador para Português do Brasil
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"


[Tasks]
; --- Tarefas opcionais que o usuário pode selecionar ---
; Opção para criar um atalho na área de trabalho (desmarcada por padrão)
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked


[Files]
; --- Arquivos que serão incluídos no instalador ---
; Copia TODO o conteúdo da pasta 'dist\MyOps' para o diretório de instalação '{app}'
; recursesubdirs: inclui todas as subpastas (_internal, assets)
; Excludes: Especifica arquivos a NÃO serem incluídos (não queremos o log de debug)
Source: "dist\MyOps\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "myops_debug.log"

; Nota: A sintaxe acima é a forma mais eficiente de incluir todos os seus arquivos.


[Icons]
; --- Atalhos que serão criados no Menu Iniciar e na Área de Trabalho ---
; Atalho principal no Menu Iniciar
Name: "{group}\MyOps"; Filename: "{app}\MyOps.exe"

; Atalho para o desinstalador no Menu Iniciar
Name: "{group}\{cm:UninstallProgram,MyOps}"; Filename: "{uninstallexe}"

; Atalho na Área de Trabalho (só será criado se a tarefa 'desktopicon' for marcada)
Name: "{autodesktop}\MyOps"; Filename: "{app}\MyOps.exe"; Tasks: desktopicon


[Run]
; --- Ações a serem executadas no final da instalação ---
; Opção para iniciar o MyOps (marcada por padrão)
Filename: "{app}\MyOps.exe"; Description: "{cm:LaunchProgram,MyOps}"; Flags: nowait postinstall shellexec

; Opção para visualizar o arquivo LEIA-ME.txt (desmarcada por padrão)
Filename: "{app}\LEIA-ME.txt"; Description: "Visualizar o arquivo LEIA-ME"; Flags: nowait postinstall shellexec unchecked