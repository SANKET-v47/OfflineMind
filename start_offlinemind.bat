@echo off
setlocal enabledelayedexpansion
title OfflineMind - Local AI Assistant

echo =====================================================================
echo                OfflineMind - Offline-First AI Assistant
echo =====================================================================
echo.

:: 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in PATH.
    echo Please install Python 3.10+ and ensure it is added to your PATH.
    pause
    exit /b 1
)

:: 2. Check Ollama daemon
echo [*] Checking local Ollama model runtime...
curl -s http://127.0.0.1:11434/api/tags >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Ollama server is not running on 127.0.0.1:11434.
    if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
        echo [*] Launching Ollama daemon in background...
        start "" "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve
        timeout /t 3 /nobreak >nul
    ) else (
        echo [WARNING] Ollama executable not found at default location.
        echo If Ollama is installed elsewhere, please start it or OfflineMind will run in fallback extractive mode.
    )
) else (
    echo [+] Ollama server is running and ready.
)

:: 3. Launch OfflineMind Desktop GUI
echo [*] Launching OfflineMind Modern Desktop GUI...
echo.
python run_gui.py

if %errorlevel% neq 0 (
    echo.
    echo [!] OfflineMind exited with code %errorlevel%.
    pause
)
