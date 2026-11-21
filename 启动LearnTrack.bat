@echo off
rem ---------------------------------------------------------------------------
rem  LearnTrack one-click launcher (Windows).
rem  Double-click this file. It always runs from its own folder, so tasks.json
rem  is created next to the program instead of somewhere else.
rem  The window stays open after the program ends so error messages are readable.
rem ---------------------------------------------------------------------------
chcp 65001 >nul
title LearnTrack - Personal Learning Task Manager
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

python learntrack_cli.py
if errorlevel 9009 py learntrack_cli.py

echo.
echo ------------------------------------------------------------------------
echo  LearnTrack closed. Press any key to close this window.
echo ------------------------------------------------------------------------
pause >nul
