@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    python serial_notch_bridge.py
) else (
    py -3 serial_notch_bridge.py
)
if errorlevel 1 pause
