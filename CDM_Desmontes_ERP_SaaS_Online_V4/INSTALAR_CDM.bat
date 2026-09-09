@echo off
setlocal
cd /d "%~dp0"
echo ========================================
echo   CDM DESMONTES - INSTALACAO LOCAL
echo ========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERRO] Python nao encontrado. Instale Python 3.10 ou superior.
  pause
  exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
  echo [ERRO] Node.js/npm nao encontrado. Instale Node.js LTS.
  pause
  exit /b 1
)

if not exist "backend\venv\Scripts\python.exe" (
  echo [1/4] Criando ambiente Python...
  python -m venv "backend\venv"
)

echo [2/4] Instalando backend...
call "backend\venv\Scripts\activate.bat"
python -m pip install -r "backend\requirements.txt"
if errorlevel 1 goto :erro

if not exist "backend\.env" (
  echo [3/4] Criando backend\.env...
  copy /Y "backend\.env.example" "backend\.env" >nul
) else (
  echo [3/4] backend\.env ja existe.
)

echo [4/4] Instalando frontend...
pushd frontend
call npm install
if errorlevel 1 (
  popd
  goto :erro
)
popd

echo.
echo ========================================
echo INSTALACAO CONCLUIDA.
echo Agora execute INICIAR_CDM.bat
echo ========================================
pause
exit /b 0

:erro
echo.
echo [ERRO] A instalacao nao terminou. Copie a mensagem acima e envie no ChatGPT.
pause
exit /b 1
