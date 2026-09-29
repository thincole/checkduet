@echo off
title Shopee Duet Checker
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [LOI] Khong tim thay Python. Hay cai Python 3.10+ va tick "Add Python to PATH".
    pause
    exit /b 1
)

python -c "import PyQt6, requests, urllib3, qrcode, gspread" >nul 2>nul
if errorlevel 1 (
    echo Dang cai dat thu vien...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [LOI] Cai dat thu vien that bai.
        pause
        exit /b 1
    )
)

pythonw main.py
if errorlevel 1 (
    echo.
    echo [LOI] Ung dung thoat voi loi. Xem thong bao phia tren.
    pause
)
