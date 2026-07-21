@echo off
echo ==========================================================
echo   Carga Retroativa Inventario Siemens - Setup e Inicializacao
echo ==========================================================
echo.

:: Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado. Instale Python 3.10+ e tente novamente.
    pause
    exit /b 1
)
python --version

:: Cria o ambiente virtual
if not exist ".venv\" (
    echo.
    echo [1/3] Criando ambiente virtual .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar o ambiente virtual.
        pause
        exit /b 1
    )
    echo [OK] Ambiente virtual criado.
) else (
    echo [OK] Ambiente virtual .venv ja existe.
)

:: Instala dependencias
echo.
echo [2/3] Instalando dependencias...
.venv\Scripts\pip install --upgrade pip --quiet
.venv\Scripts\pip install -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias.
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas com sucesso.

:: Verifica .env
echo.
if not exist ".env" (
    echo [AVISO] Arquivo .env nao encontrado! Configure suas credenciais.
) else (
    echo [OK] Arquivo .env encontrado.
)

:: Inicia Flask
echo.
echo [3/3] Iniciando servidor Flask em http://localhost:5001
echo       Pressione Ctrl+C para parar.
echo.
.venv\Scripts\python app.py

pause
