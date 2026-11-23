@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "ROOT=%~dp0"
if not exist "%ROOT%assets\learn_track.png" (
    python -c "import ui_theme, pathlib; ui_theme.ensure_assets(pathlib.Path('.'))"
)

python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name LearnTrack ^
    --icon "%ROOT%assets\learn_track.ico" ^
    --add-data "%ROOT%assets;assets" ^
    --distpath "." ^
    --workpath "build\pyinstaller" ^
    --specpath "build" ^
    --exclude-module PySide6.QtWebEngineCore ^
    --exclude-module PySide6.QtWebEngineWidgets ^
    --exclude-module PySide6.QtWebEngineQuick ^
    --exclude-module PySide6.QtQml ^
    --exclude-module PySide6.QtQuick ^
    --exclude-module PySide6.QtQuickWidgets ^
    --exclude-module PySide6.QtMultimedia ^
    --exclude-module PySide6.QtMultimediaWidgets ^
    --exclude-module PySide6.Qt3DCore ^
    --exclude-module PySide6.QtCharts ^
    --exclude-module PySide6.QtDataVisualization ^
    --exclude-module PySide6.QtBluetooth ^
    --exclude-module PySide6.QtSql ^
    --exclude-module tkinter ^
    learntrack_ui.py

if exist "LearnTrack.exe" (
    echo.
    echo Build finished: %cd%\LearnTrack.exe
) else (
    echo.
    echo Build failed. Check the log above.
)
