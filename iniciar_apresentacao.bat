@echo off
setlocal EnableExtensions
title Iniciador - Laminacao TANDEM

cd /d "%~dp0"

echo.
echo === Middleware de supervisao termica TANDEM ===
echo Pasta do projeto: %CD%
echo.

set "PYTHON_EXE="

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
    echo Usando o Python do ambiente virtual .venv.
) else (
    for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%P"
    if defined PYTHON_EXE (
        echo Ambiente .venv nao encontrado. Usando Python localizado pelo Launcher.
    ) else (
        for /f "delims=" %%P in ('python -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_EXE=%%P"
        if defined PYTHON_EXE (
            echo Ambiente .venv nao encontrado. Usando Python do sistema.
        )
    )
)

if not defined PYTHON_EXE (
    echo ERRO: Python nao foi encontrado.
    echo Instale Python 3.11 ou mais novo, ou crie .venv na pasta do projeto.
    pause
    exit /b 1
)

echo.
echo [1/4] Iniciando o broker MQTT pelo Docker...
docker compose up -d
if errorlevel 1 (
    echo.
    echo ERRO: nao foi possivel iniciar o Docker Compose.
    echo Abra o Docker Desktop e confirme que ele esta em execucao.
    pause
    exit /b 1
)

echo [2/4] Abrindo os tres controladores...
start "TANDEM - Controlador 1" cmd /k ""%PYTHON_EXE%" controlador.py 1"
start "TANDEM - Controlador 2" cmd /k ""%PYTHON_EXE%" controlador.py 2"
start "TANDEM - Controlador 3" cmd /k ""%PYTHON_EXE%" controlador.py 3"

timeout /t 2 /nobreak >nul

echo [3/4] Abrindo sensores e atuadores...
start "TANDEM - Campo (sensores e atuadores)" cmd /k ""%PYTHON_EXE%" iniciar_campo.py"

timeout /t 2 /nobreak >nul

echo [4/4] Abrindo o cliente do operador...
start "TANDEM - Cliente do operador" cmd /k ""%PYTHON_EXE%" cliente.py"

echo.
echo Sistema iniciado.
echo.
echo MQTT Explorer - somente observacao:
echo   Host: localhost
echo   Porta: 1883
echo   Sem usuario e senha
echo   Assine o topico: laminacao/#
echo.
echo Para encerrar, feche as janelas dos processos e execute:
echo   docker compose down
echo.
pause
