@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    python xinput_notch_test.py
) else (
    py -3 xinput_notch_test.py
)
if errorlevel 1 pause
