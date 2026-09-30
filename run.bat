@echo off
title Shopee Duet Checker
cd /d "%~dp0"

rem 1. Them cac thu muc Python vao bien moi truong PATH
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%LOCALAPPDATA%\Programs\Python\Python310;%LOCALAPPDATA%\Programs\Python\Python310\Scripts;C:\Program Files\Python312;C:\Program Files\Python311;C:\Program Files\Python310;%PATH%"

rem 2. Tim Python kha dung
set PY_CMD=
where python >nul 2>nul
if not errorlevel 1 (
    set PY_CMD=python
) else (
    where py >nul 2>nul
    if not errorlevel 1 (
        set PY_CMD=py
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
        set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    ) else (
        echo [LOI] Khong tim thay Python tren he thong!
        echo Vui long cai dat Python 3.10+ hoac chay file install.bat de tu dong cai dat.
        pause
        exit /b 1
    )
)

rem 3. Kiem tra thu vien phu thuoc
%PY_CMD% -c "import PyQt6, requests, urllib3, qrcode, gspread" >nul 2>nul
if errorlevel 1 (
    echo Dang cai dat thu vien can thiet (PyQt6, requests, qrcode...)...
    %PY_CMD% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [LOI] Cai dat thu vien that bai!
        pause
        exit /b 1
    )
)

rem 4. Khoi dong ung dung
%PY_CMD% main.py
if errorlevel 1 (
    echo.
    echo ================================================================
    echo [LOI] Ung dung gap loi va da thoat!
    echo Chi tiet loi duoc hien thi o tren hoac ghi trong file crash.log
    echo ================================================================
    pause
)
