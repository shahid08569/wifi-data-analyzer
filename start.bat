@echo off
title WiFi & Hotspot Data Analyzer
echo ========================================================
echo        WiFi & Hotspot Data Bandwidth Analyzer
echo ========================================================
echo Starting Backend API and Web Dashboard...
echo.

cd /d "%~dp0backend"

:: Check if Python is available via py or python
where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo Using Python Launcher (py)...
    py app.py
    goto end
)

where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo Using Python...
    python app.py
    goto end
)

echo ERROR: Python was not found in your system PATH!
pause

:end
