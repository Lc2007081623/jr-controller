@echo off
cd /d "%~dp0"
python as5600_monitor.py
if errorlevel 1 pause
