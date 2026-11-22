@echo off
chcp 65001 >nul
cd /d "%~dp0"
python comm_tool.py --port COM3
pause
