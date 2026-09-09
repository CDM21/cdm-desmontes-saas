@echo off
cd /d "%~dp0"
if not exist "backend\.env" copy /Y "backend\.env.example" "backend\.env" >nul
start notepad "backend\.env"
echo.
echo Preencha as credenciais oficiais das aplicacoes e salve o arquivo.
echo Depois reinicie o backend.
pause
