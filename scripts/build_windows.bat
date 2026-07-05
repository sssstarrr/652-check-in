@echo off
setlocal
cd /d "%~dp0\.."
python -m pip install -r requirements.txt
python scripts\build_pyinstaller.py
endlocal
