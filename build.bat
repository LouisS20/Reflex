@echo off
chcp 65001 >nul
REM Cree Reflex.exe (un seul fichier, sans console) dans le dossier dist
python -m pip install -r requirements.txt pyinstaller
python icon.py
python -m PyInstaller --noconsole --onefile --name Reflex --icon reflex.ico --collect-all customtkinter main.py
if exist dist\Reflex.exe (echo. & echo Termine : dist\Reflex.exe) else (echo. & echo La compilation a echoue.)
pause
