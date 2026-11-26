@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PYTHON_CMD=python"
where python >nul 2>nul
if errorlevel 1 set "PYTHON_CMD=py -3"

%PYTHON_CMD% audio_downloader.py
if errorlevel 1 goto failed
exit /b 0

:failed
echo.
echo The audio downloader exited with an error.
echo Review the messages above, then run this file again.
pause
exit /b 1
