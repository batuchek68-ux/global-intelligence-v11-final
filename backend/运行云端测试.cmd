@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-cloud-test.ps1" %*
exit /b %ERRORLEVEL%
