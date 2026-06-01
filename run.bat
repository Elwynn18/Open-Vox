@echo off
REM Lanceur OpenVox : active le venv et demarre l'app sans fenetre console.
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Environnement introuvable. Lance d'abord l'installation ^(voir README^).
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" main.py
