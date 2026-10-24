@echo off
cd /d "%~dp0"
python serial_notch_bridge.py
if errorlevel 1 pause
