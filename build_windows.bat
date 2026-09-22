@echo off
chcp 65001 >nul
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m PyInstaller --clean --noconfirm HR_Analysis_Assistant.spec
) else (
    python -m PyInstaller --clean --noconfirm HR_Analysis_Assistant.spec
)

echo.
echo Build complete: dist\HR_Analysis_Assistant.exe
pause
