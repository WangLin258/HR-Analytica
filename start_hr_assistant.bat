@echo off
rem HR Analytica launcher - starts server and opens browser (non-blocking)
cd /d "%~dp0"
start "" /b powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0start_hr_assistant.ps1"
