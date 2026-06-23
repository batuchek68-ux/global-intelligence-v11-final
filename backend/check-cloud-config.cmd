@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0check-cloud-config.ps1" %*
exit /b %ERRORLEVEL%

