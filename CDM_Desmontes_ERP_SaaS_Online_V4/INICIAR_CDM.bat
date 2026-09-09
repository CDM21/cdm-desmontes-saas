@echo off
setlocal
cd /d "%~dp0"

if not exist "backend\venv\Scripts\python.exe" (
  echo O sistema ainda nao foi instalado.
  echo Execute primeiro: INSTALAR_CDM.bat
  pause
  exit /b 1
)

if not exist "frontend\node_modules" (
  echo O frontend ainda nao foi instalado.
  echo Execute primeiro: INSTALAR_CDM.bat
  pause
  exit /b 1
)

start "CDM Backend" cmd /k "cd /d ""%~dp0backend"" && call venv\Scripts\activate.bat && uvicorn app.main:app --reload"
start "CDM Frontend" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"

timeout /t 4 /nobreak >nul
start "" http://localhost:5173
exit /b 0
