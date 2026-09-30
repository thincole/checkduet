@echo off
title Shopee Duet Checker
cd /d "%~dp0"

set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%LOCALAPPDATA%\Programs\Python\Python310;%LOCALAPPDATA%\Programs\Python\Python310\Scripts;C:\Program Files\Python312;C:\Program Files\Python311;C:\Program Files\Python310;%PATH%"

set PY_CMD=
where python >nul 2>nul
if not errorlevel 1 (
    set PY_CMD=python
    goto PYTHON_OK
)

where py >nul 2>nul
if not errorlevel 1 (
    set PY_CMD=py
    goto PYTHON_OK
)

if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto PYTHON_OK
)

if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    goto PYTHON_OK
)

echo [LOI] Khong tim thay Python tren he thong!
echo Vui long cai dat Python 3.10+ hoac chay file install.bat de tu dong cai dat.
pause
exit /b 1

:PYTHON_OK
rem Kiem tra thu vien phu thuoc
%PY_CMD% -c "import PyQt6, requests, urllib3, qrcode, gspread" >nul 2>nul
if not errorlevel 1 goto START_APP

echo Dang cai dat cac thu vien can thiet, vui long cho trong giay lat...
%PY_CMD% -m pip install -r requirements.txt
if errorlevel 1 goto PIP_FAIL

:START_APP
%PY_CMD% main.py
if errorlevel 1 goto APP_ERROR
goto APP_END

:PIP_FAIL
echo.
echo [LOI] Cai dat thu vien that bai!
pause
exit /b 1

:APP_ERROR
echo.
echo ================================================================
echo [LOI] Ung dung gap loi va da thoat!
echo Chi tiet loi duoc hien thi o tren hoac ghi trong file crash.log
echo ================================================================
pause
exit /b 1

:APP_END
