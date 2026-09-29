@echo off
title Shopee Duet Checker - Cai Dat Moi Truong Tu Dong
cd /d "%~dp0"

echo ================================================================
echo        SHOPEE DUET CHECKER - CAI DAT MOI TRUONG TU DONG
echo ================================================================
echo Script nay se tu dong kiem tra va cai dat day du:
echo 1. Python 3.12 (Kem tick PATH tu dong)
echo 2. Git (De cap nhat code tu dong)
echo 3. Cac thu vien Python can thiet (PyQt6, requests, qrcode...)
echo 4. Khoi tao thu muc va file cau hinh
echo ================================================================
echo.

rem Cap nhat PATH hien tai phong truong hop vua moi cai dat
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%LOCALAPPDATA%\Programs\Python\Python310;%LOCALAPPDATA%\Programs\Python\Python310\Scripts;C:\Program Files\Git\cmd;%PATH%"

rem ---------------------------------------------------------------
rem BUOC 1: KIEM TRA & CAI DAT PYTHON
rem ---------------------------------------------------------------
echo [1/4] Kiem tra Python...
set PY_CMD=
where python >nul 2>nul
if not errorlevel 1 (
    set PY_CMD=python
    goto PYTHON_FOUND
)

where py >nul 2>nul
if not errorlevel 1 (
    set PY_CMD=py
    goto PYTHON_FOUND
)

if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto PYTHON_FOUND
)

if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    goto PYTHON_FOUND
)

echo [*] Chua tim thay Python. Dang tien hanh tu dong cai dat Python 3.12...
echo Vui long cho trong giay lat (khoang 1-2 phut tuy toc do mang)...

rem Thu dung winget truoc
where winget >nul 2>nul
if not errorlevel 1 (
    echo [*] Dang cai Python qua Windows Package Manager...
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements --silent
    if not errorlevel 1 goto REFRESH_PYTHON
)

rem Neu khong co winget, tai installer chinh thuc tu python.org
echo [*] Dang tai bo cai dat Python 3.12 tu python.org...
set "PY_INSTALLER=%TEMP%\python_installer_3.12.exe"
curl.exe -fSL -o "%PY_INSTALLER%" "https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe"
if errorlevel 1 (
    echo [LOI] Khong the tai Python installer. Vui long kiem tra ket noi mang.
    echo Ban co the tu tai va cai Python tai: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [*] Dang chay cai dat Python 3.12 (tu dong them PATH)...
"%PY_INSTALLER%" /passive InstallAllUsers=0 PrependPath=1 Include_test=0
del /f /q "%PY_INSTALLER%" >nul 2>nul

:REFRESH_PYTHON
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
) else (
    set PY_CMD=python
)

:PYTHON_FOUND
:PYTHON_READY
echo [OK] Python da san sang:
%PY_CMD% --version

rem ---------------------------------------------------------------
rem BUOC 2: KIEM TRA & CAI DAT GIT
rem ---------------------------------------------------------------
echo.
echo [2/4] Kiem tra Git...
where git >nul 2>nul
if not errorlevel 1 (
    echo [OK] Da tim thay Git tren he thong:
    git --version
    goto GIT_READY
)

echo [*] Chua tim thay Git. Dang tien hanh tu dong cai dat Git...
where winget >nul 2>nul
if not errorlevel 1 (
    echo [*] Dang cai Git qua winget...
    winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements --silent
    if not errorlevel 1 (
        set "PATH=C:\Program Files\Git\cmd;%PATH%"
        goto GIT_READY
    )
)

echo [*] Dang tai bo cai dat Git...
set "GIT_INSTALLER=%TEMP%\git_installer.exe"
curl.exe -fSL -o "%GIT_INSTALLER%" "https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/Git-2.47.1-64-bit.exe"
if not errorlevel 1 (
    echo [*] Dang cai dat Git chay ngam...
    "%GIT_INSTALLER%" /VERYSILENT /NORESTART
    del /f /q "%GIT_INSTALLER%" >nul 2>nul
    set "PATH=C:\Program Files\Git\cmd;%PATH%"
) else (
    echo [CANH BAO] Khong the tu dong tai Git. Ban co the tu cai Git tai https://git-scm.com/ sau.
)

:GIT_READY
where git >nul 2>nul
if not errorlevel 1 (
    echo [OK] Git da san sang.
    git config user.name >nul 2>nul
    if errorlevel 1 (
        git config --global user.name "ShopeeDuetUser"
        git config --global user.email "user@shopeeduet.local"
    )
)

rem ---------------------------------------------------------------
rem BUOC 3: CAI DAT CAC THU VIEN PYTHON (REQUIREMENTS)
rem ---------------------------------------------------------------
echo.
echo [3/4] Cai dat cac thu vien Python can thiet...
%PY_CMD% -m pip install --upgrade pip --quiet
if not exist "requirements.txt" goto INSTALL_DEFAULT_PKGS

echo [*] Dang cai dat tu requirements.txt...
%PY_CMD% -m pip install -r requirements.txt
if errorlevel 1 (
    echo [LOI] Cai dat thu vien that bai!
    pause
    exit /b 1
)
goto PKGS_DONE

:INSTALL_DEFAULT_PKGS
echo [*] Cai dat truc tiep cac thu vien co ban...
%PY_CMD% -m pip install PyQt6 requests urllib3 qrcode gspread

:PKGS_DONE
echo [OK] Tat ca thu vien Python da duoc cai dat day du!

rem ---------------------------------------------------------------
rem BUOC 4: KHOI TAO THU MUC VA CAU HINH
rem ---------------------------------------------------------------
echo.
echo [4/4] Kiem tra thu muc va file cau hinh...
if not exist "data" mkdir "data"
if not exist "results" mkdir "results"
if not exist "debug" mkdir "debug"

if not exist "settings.json" (
    if exist "settings.example.json" (
        echo [*] Khoi tao settings.json tu settings.example.json...
        copy "settings.example.json" "settings.json" >nul
    )
)

rem Tao shortcut ra Desktop de tien mo app
echo.
echo [*] Dang tao loi tat Shortcut ngoai man hinh Desktop...
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([System.IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), 'Shopee Duet Checker.lnk')); $s.TargetPath = '%~dp0run.bat'; $s.WorkingDirectory = '%~dp0'; $s.Description = 'Shopee Duet Checker'; $s.Save()" >nul 2>nul
if not errorlevel 1 (
    echo [OK] Da tao loi tat 'Shopee Duet Checker' ngoai man hinh Desktop!
)

echo.
echo ================================================================
echo  [THANH CONG] MOI TRUONG DA DUOC CAI DAT HOAN TAT 100%!
echo ================================================================
echo.

set /p "LAUNCH=Ban co muon khoi dong Shopee Duet Checker ngay bay gio khong? [Y/N, mac dinh Y]: "
if "%LAUNCH%"=="" set "LAUNCH=Y"
if /i "%LAUNCH%"=="Y" (
    echo Dang khoi dong ung dung...
    start "" run.bat
)
