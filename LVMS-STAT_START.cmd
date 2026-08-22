@echo off
chcp 65001 >nul
setlocal EnableExtensions
title LVMS-STAT - START

set "IVANTI=C:\Program Files (x86)\Ivanti\Workspace Control\pwrgate.exe"
set "SCRIPT=%~dp0start_python_felles.py"
set "PYCMD=import runpy; runpy.run_path(r'%SCRIPT%', run_name='__main__')"

if not exist "%IVANTI%" goto :NOIVANTI
if not exist "%SCRIPT%" goto :NOSCRIPT

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Set-Clipboard -Value $env:PYCMD; Start-Process -FilePath $env:IVANTI -ArgumentList '15694'"
if errorlevel 1 goto :FAILED

echo Startkommandoen er kopiert, og Python FELLES er apnet.
echo Vent pa ^>^>^>, trykk Ctrl+V og deretter Enter.
pause
goto :EOF

:NOIVANTI
echo Finner ikke Ivanti PowerGate.
pause
goto :EOF

:NOSCRIPT
echo Finner ikke start_python_felles.py i prosjektmappen.
pause
goto :EOF

:FAILED
echo Klarte ikke a apne Python FELLES.
pause
