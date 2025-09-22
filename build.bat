@echo off
setlocal

REM Define o nome do projeto para ser usado nos caminhos e no executável
set PROJECT_NAME=MyOps

echo =========================================================
echo       INICIANDO SCRIPT DE BUILD PARA %PROJECT_NAME%
echo =========================================================
echo.

REM --- Passo 1: Limpeza de compilações anteriores ---
echo [1/5] Limpando builds anteriores (pastas build, dist e .spec)...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist %PROJECT_NAME%.spec del %PROJECT_NAME%.spec
echo Limpeza concluida.
echo.

REM --- Passo 2: Criação e configuração do ambiente virtual ---
echo [2/5] Verificando e configurando o ambiente virtual (venv)...
if not exist venv (
    echo Criando novo ambiente virtual...
    python -m venv venv
)
call .\venv\Scripts\activate.bat
echo Ambiente virtual ativado.
echo.

REM --- Passo 3: Instalação das dependências ---
echo [3/5] Instalando/atualizando dependencias do requirements.txt...
pip install -r requirements.txt
echo.
echo [4/5] Garantindo que o PyInstaller esta instalado no venv...
pip install pyinstaller
echo.

REM --- Passo 4: Executando o PyInstaller com todas as opções ---
echo [5/5] Compilando a aplicacao com PyInstaller...
pyinstaller ^
    --name %PROJECT_NAME% ^
    --windowed ^
    --onedir ^
    --clean ^
    --icon="assets/icone.ico" ^
    --add-data "assets;assets" ^
    --add-data "config.ini;." ^
    --add-data "license.key;." ^
    main_app.py

REM --- Passo 5: Verificação e mensagem final ---
echo.
if exist "dist\%PROJECT_NAME%\%PROJECT_NAME%.exe" (
    echo =========================================================
    echo   Compilacao concluida com SUCESSO!
    echo   Sua aplicacao esta pronta na pasta: dist\%PROJECT_NAME%
    echo =========================================================
) else (
    echo XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
    echo   Ocorreu um ERRO durante a compilacao.
    echo   Verifique o log do PyInstaller acima para detalhes.
    echo XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
)
echo.
pause
endlocal