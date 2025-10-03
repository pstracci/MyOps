@echo off
setlocal

REM --- CONFIGURACOES ---
set PROJECT_NAME=MyOps
set MAIN_SCRIPT=main_app.py
set REQUIREMENTS_FILE=requirements.txt
set INSTALLER_SCRIPT=MyOps_Installer.iss

echo =========================================================
echo       INICIANDO ETAPA 1: PREPARACAO E BUILD
echo =========================================================
echo.

REM --- Passo 1: Leitura da versão ---
echo [1/7] Lendo a versao do arquivo __version__.py...
for /f "tokens=2 delims==" %%i in (__version__.py) do (
    set APP_VERSION=%%i
)
rem Limpa espacos, aspas duplas e aspas simples da variavel
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
echo [2/7] Limpando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist Output rmdir /s /q Output
if exist %PROJECT_NAME%.spec del %PROJECT_NAME%.spec
if exist %INSTALLER_SCRIPT% del %INSTALLER_SCRIPT%
echo       Limpeza concluida.
echo.

REM --- Passo 3: Ambiente Virtual ---
echo [3/7] Configurando o ambiente virtual (venv)...
if not exist venv (
    echo       Criando novo ambiente virtual...
    py -m venv venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar o ambiente virtual. Verifique se o Python esta instalado corretamente.
        goto:error
    )
)
call .\venv\Scripts\activate.bat
echo       Ambiente virtual ativado.
echo.

REM --- Passo 4: Dependencias ---
echo [4/7] Instalando dependencias do %REQUIREMENTS_FILE%...
pip install -r %REQUIREMENTS_FILE%
if errorlevel 1 (
    echo [ERRO] Falha ao instalar as dependencias. Verifique o arquivo %REQUIREMENTS_FILE%.
    goto:error
)
echo.

REM --- Passo 5: Compilando com PyInstaller ---
echo [5/7] Compilando a aplicacao com PyInstaller...
pyinstaller ^
    --name %PROJECT_NAME% ^
    --windowed ^
    --onedir ^
    --clean ^
    --icon="assets/icone.ico" ^
    --add-data "assets;assets" ^
    --add-data "config.ini;." ^
    --add-data "license.key;." ^
    %MAIN_SCRIPT%
if errorlevel 1 (
    echo [ERRO] O PyInstaller encontrou um problema durante a compilacao.
    goto:error
)
echo.

REM --- Passo 5.5: Forcando a Copia de Arquivos Essenciais para o Diretorio Final ---
echo [6/7] Garantindo a presenca de arquivos essenciais no diretorio de saida...
set DEST_DIR=dist\%PROJECT_NAME%

rem XCOPY para copiar a pasta assets e todo o seu conteudo
echo       Copiando a pasta 'assets'...
xcopy assets "%DEST_DIR%\assets\" /E /I /Y
if errorlevel 1 (
    echo [ERRO] Falha ao copiar a pasta 'assets'.
    goto:error
)

rem COPY para copiar arquivos individuais
echo       Copiando 'config.ini' e 'license.key'...
copy /Y config.ini "%DEST_DIR%\"
copy /Y license.key "%DEST_DIR%\"
echo       Copia finalizada.
echo.

REM --- Passo 6: Gerando o script do Inno Setup ---
echo [7/7] Gerando o script do instalador (%INSTALLER_SCRIPT%)...
(
    echo ; Script para o Inno Setup do MyOps (gerado automaticamente^)
    echo.
    echo [Setup]
    echo AppName=%PROJECT_NAME%
    echo AppVersion=%APP_VERSION%
    echo AppPublisher=MyOps Team
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
    echo Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
    echo.
    echo [Files]
    echo Source: "%DEST_DIR%\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "myops_debug.log"
    echo.
    echo [Icons]
    echo Name: "{group}\%PROJECT_NAME%"; Filename: "{app}\%PROJECT_NAME%.exe"
    echo Name: "{group}\{cm:UninstallProgram,%PROJECT_NAME%}"; Filename: "{uninstallexe}"
    echo Name: "{autodesktop}\%PROJECT_NAME%"; Filename: "{app}\%PROJECT_NAME%.exe"; Tasks: desktopicon
    echo.
    echo [Run]
    echo Filename: "{app}\%PROJECT_NAME%.exe"; Description: "{cm:LaunchProgram,%PROJECT_NAME%}"; Flags: nowait postinstall shellexec
) > %INSTALLER_SCRIPT%
echo       Script do instalador gerado com sucesso.
echo.

goto:success

:success
echo =========================================================
echo   ETAPA 1 (PREPARACAO) CONCLUIDA COM SUCESSO!
echo.
echo   - A pasta '%DEST_DIR%' contem os arquivos da aplicacao.
echo   - O script '%INSTALLER_SCRIPT%' foi gerado com a versao correta.
echo.
echo   >> PROXIMO PASSO: Verifique a pasta e execute 'compile_installer.bat'.
echo =========================================================
goto:end

:error
echo XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
echo   O PROCESSO DE BUILD FALHOU.
echo   Verifique a mensagem de erro acima para mais detalhes.
echo XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

:end
pause
endlocal