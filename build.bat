@echo off
setlocal

REM --- CONFIGURACOES ---
set PROJECT_NAME=MyOps
set MAIN_SCRIPT=main_app.py
set REQUIREMENTS_FILE=requirements.txt
set INSTALLER_SCRIPT=MyOps_Installer.iss
set ISCC="C:\Program Files (x86)\Inno Setup 6\iscc.exe"

echo =========================================================
echo       INICIANDO BUILD COMPLETO DO %PROJECT_NAME%
echo =========================================================
echo.

REM --- Passo 1: Leitura da vers?o ---
echo [1/8] Lendo a versao do arquivo __version__.py...
for /f "tokens=2 delims==" %%i in (__version__.py) do (
    set APP_VERSION=%%i
)
set APP_VERSION=%APP_VERSION: =%
set APP_VERSION=%APP_VERSION:"=%
set APP_VERSION=%APP_VERSION:'=%

if not defined APP_VERSION (
    echo [ERRO] Nao foi possivel ler a versao do __version__.py.
    goto:error
)
echo       Versao da aplicacao: %APP_VERSION%
echo.

REM --- Passo 2: Limpeza ---
echo [2/8] Limpando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist Output rmdir /s /q Output
if exist %PROJECT_NAME%.spec del %PROJECT_NAME%.spec
if exist %INSTALLER_SCRIPT% del %INSTALLER_SCRIPT%
echo       Limpeza concluida.
echo.

REM --- Passo 3: Ambiente Virtual ---
echo [3/8] Configurando o ambiente virtual (venv)...
if not exist venv (
    echo       Criando novo ambiente virtual...
    py -m venv venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar o ambiente virtual.
        goto:error
    )
)
call .\venv\Scripts\activate.bat
echo       Ambiente virtual ativado.
echo.

REM --- Passo 4: Dependencias ---
echo [4/8] Instalando dependencias do %REQUIREMENTS_FILE%...
pip install -r %REQUIREMENTS_FILE%
if errorlevel 1 (
    echo [ERRO] Falha ao instalar as dependencias.
    goto:error
)
echo.

REM --- Passo 5: Compilando com PyInstaller ---
echo [5/8] Compilando a aplicacao com PyInstaller...
pyinstaller ^
    --name %PROJECT_NAME% ^
    --windowed ^
    --onedir ^
    --clean ^
    --icon="assets/icone.ico" ^
    --add-data "assets;assets" ^
    %MAIN_SCRIPT%
if errorlevel 1 (
    echo [ERRO] O PyInstaller encontrou um problema durante a compilacao.
    goto:error
)
echo.

REM --- Passo 5.5: Copiando arquivos essenciais ---
echo [6/8] Garantindo a presenca de arquivos essenciais no diretorio de saida...
set DEST_DIR=dist\%PROJECT_NAME%

echo       Copiando a pasta 'assets'...
xcopy assets "%DEST_DIR%\assets\" /E /I /Y
if errorlevel 1 (
    echo [ERRO] Falha ao copiar a pasta 'assets'.
    goto:error
)

REM config.ini: prioriza a versao instalada (que tem as conexoes do usuario).
REM Se ja existe uma instalacao com config.ini, usa ela como template para o
REM novo pacote. Caso contrario, usa o config.ini de desenvolvimento.
REM O Inno Setup ainda aplica onlyifdoesntexist como segunda camada de protecao.
echo       Copiando 'config.ini'...
set INSTALLED_CONFIG=%LOCALAPPDATA%\Programs\MyOps\config.ini
if exist "%INSTALLED_CONFIG%" (
    echo       [INFO] config.ini do usuario encontrado em %INSTALLED_CONFIG%
    echo       [INFO] Usando versao instalada para preservar conexoes.
    copy /Y "%INSTALLED_CONFIG%" "%DEST_DIR%\"
) else (
    echo       [INFO] Nenhuma instalacao anterior encontrada. Usando config.ini de desenvolvimento.
    copy /Y config.ini "%DEST_DIR%\"
)
echo       Copia finalizada.
echo.

REM --- Passo 6: Gerando o script do Inno Setup ---
echo [7/8] Gerando o script do instalador (%INSTALLER_SCRIPT%)...
(
    echo ; Script para o Inno Setup do MyOps (gerado automaticamente^)
    echo.
    echo [Setup]
    echo AppName=%PROJECT_NAME%
    echo AppVersion=%APP_VERSION%
    echo AppPublisher=MyOps Team
    echo AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
    echo DefaultDirName={autopf}\%PROJECT_NAME%
    echo DefaultGroupName=%PROJECT_NAME%
    echo PrivilegesRequired=lowest
    echo OutputBaseFilename=%PROJECT_NAME%_Setup_%APP_VERSION%
    echo OutputDir=Output
    echo Compression=lzma
    echo SolidCompression=yes
    echo WizardStyle=modern
    echo UninstallDisplayIcon={app}\%PROJECT_NAME%.exe
    echo.
    echo [Languages]
    echo Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
    echo.
    echo [Tasks]
    echo Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
    echo.
    echo [Files]
    echo ; Todos os arquivos do app, exceto log e config (sempre atualizados^)
    echo Source: "%DEST_DIR%\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "myops_debug.log,config.ini"
    echo ; config.ini: apenas instalado se nao existir (preserva conexoes do usuario^)
    echo Source: "%DEST_DIR%\config.ini"; DestDir: "{app}"; Flags: onlyifdoesntexist
    echo.
    echo [Icons]
    echo Name: "{group}\%PROJECT_NAME%"; Filename: "{app}\%PROJECT_NAME%.exe"; WorkingDir: "{app}"
    echo Name: "{group}\{cm:UninstallProgram,%PROJECT_NAME%}"; Filename: "{uninstallexe}"
    echo Name: "{autodesktop}\%PROJECT_NAME%"; Filename: "{app}\%PROJECT_NAME%.exe"; WorkingDir: "{app}"; Tasks: desktopicon
    echo.
    echo [Run]
    echo Filename: "{app}\%PROJECT_NAME%.exe"; Description: "{cm:LaunchProgram,%PROJECT_NAME%}"; Flags: nowait postinstall shellexec
) > %INSTALLER_SCRIPT%
echo       Script do instalador gerado com sucesso.
echo.

REM --- Passo 7: Compilando o instalador e instalando ---
echo [8/8] Compilando instalador com Inno Setup e instalando...
%ISCC% %INSTALLER_SCRIPT%
if errorlevel 1 (
    echo [ERRO] O Inno Setup falhou ao compilar o instalador.
    goto:error
)
echo       Instalador compilado. Instalando silenciosamente...
for /f "delims=" %%f in ('dir /b Output\%PROJECT_NAME%_Setup_*.exe 2^>nul') do set SETUP_FILE=Output\%%f
if not defined SETUP_FILE (
    echo [ERRO] Arquivo de instalador nao encontrado em Output\.
    goto:error
)
"%SETUP_FILE%" /VERYSILENT /NORESTART /TASKS="desktopicon"
if errorlevel 1 (
    echo [ERRO] A instalacao falhou.
    goto:error
)
echo       Instalacao concluida.
echo.

goto:success

:success
echo =========================================================
echo   BUILD E INSTALACAO CONCLUIDOS COM SUCESSO!
echo   Versao: %APP_VERSION%
echo   O atalho existente continua funcionando.
echo   Dados de conexoes do usuario foram preservados.
echo =========================================================
goto:end

:error
echo XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
echo   O PROCESSO DE BUILD FALHOU.
echo   Verifique a mensagem de erro acima.
echo XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

:end
pause
endlocal
