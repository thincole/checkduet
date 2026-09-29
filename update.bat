@echo off
title Shopee Duet Checker - Cap Nhat Tu GitHub
cd /d "%~dp0"

echo ================================================================
echo        SHOPEE DUET CHECKER - CAP NHAT MA NGUON TU DONG
echo ================================================================
echo.

rem 1. Kiem tra Git
where git >nul 2>nul
if errorlevel 1 (
    echo [LOI] Khong tim thay Git tren may tinh nay!
    echo De tu dong cap nhat ma nguon, ban can cai dat Git:
    echo https://git-scm.com/
    echo.
    echo Hay cai dat Git roi chay lai file update.bat nay.
    pause
    exit /b 1
)

rem 2. Kiem tra Python
where python >nul 2>nul
if errorlevel 1 (
    echo [CANH BAO] Khong tim thay Python trong bien moi truong PATH.
    echo Ban can cai dat Python 3.10+ de chay phan mem.
    echo.
)

rem 3. Kiem tra va dong bo tu Git
set REPO_URL=https://github.com/thincole/checkduet.git

if exist ".git" (
    echo [*] Dang ket noi va kiem tra ban cap nhat tu GitHub...
    git remote set-url origin %REPO_URL% 2>nul
    
    rem Tam luu thay doi cuc bo neu co
    git stash --quiet 2>nul

    git pull origin main
    if errorlevel 1 (
        echo.
        echo [CANH BAO] Qua trinh cap nhat gap xung dot voi file cuc bo.
        set /p "FORCE_UPDATE=Ban co muon ghi de toan bo theo ban goc GitHub khong? [Y/N]: "
        if /i "%FORCE_UPDATE%"=="Y" (
            git fetch origin main
            git reset --hard origin/main
            echo [OK] Da dong bo hoan toan ve ban moi nhat tren GitHub!
        ) else (
            echo Bo qua dong bo. Giu nguyen ma nguon hien tai tren may nay.
            pause
            exit /b 1
        )
    ) else (
        rem Khoi phuc thay doi cuc bo neu co
        git stash pop --quiet >nul 2>nul
    )
) else (
    echo [*] Chua co cau hinh Git tai thu muc nay. Dang thiet lap ket noi...
    git init
    git remote add origin %REPO_URL%
    git fetch origin main
    if errorlevel 1 (
        echo [LOI] Khong the tai ma nguon tu %REPO_URL%.
        echo Vui long kiem tra ket noi mang hoac repository GitHub.
        pause
        exit /b 1
    )
    git reset --hard origin/main
    git branch -M main
    git branch --set-upstream-to=origin/main main 2>nul
)

rem 4. Dam bao cac thu muc can thiet
if not exist "data" mkdir "data"
if not exist "results" mkdir "results"
if not exist "debug" mkdir "debug"

if not exist "settings.json" (
    if exist "settings.example.json" (
        echo [*] Khoi tao settings.json tu settings.example.json...
        copy "settings.example.json" "settings.json" >nul
    )
)

rem 5. Doc phien ban hien tai
set "CURRENT_VER=1.1"
if exist "version.txt" (
    for /f "usebackq delims=" %%v in ("version.txt") do set "CURRENT_VER=%%v"
)

rem 6. Cap nhat thu vien Python
where python >nul 2>nul
if not errorlevel 1 (
    if exist "requirements.txt" (
        echo.
        echo [*] Kiem tra va cai dat thu vien can thiet (PyQt6, requests...)...
        python -m pip install -r requirements.txt --quiet
    )
)

echo.
echo ================================================================
echo  [THANH CONG] Da cap nhat xong phien ban moi nhat: v%CURRENT_VER%!
echo ================================================================
echo.

rem 7. Hoi khoi dong ung dung
set /p "LAUNCH=Ban co muon khoi dong Shopee Duet Checker ngay bay gio khong? [Y/N, mac dinh Y]: "
if "%LAUNCH%"=="" set "LAUNCH=Y"
if /i "%LAUNCH%"=="Y" (
    echo Dang khoi dong ung dung...
    start "" run.bat
)
