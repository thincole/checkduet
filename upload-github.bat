@echo off
title Shopee Duet Checker - Upload GitHub
cd /d "%~dp0"

echo ================================================================
echo           SHOPEE DUET CHECKER - UPLOAD CODE LEN GITHUB
echo ================================================================
echo.

rem 1. Kiem tra Git
where git >nul 2>nul
if errorlevel 1 (
    echo [LOI] Khong tim thay Git tren may tinh!
    echo Vui long cai dat Git tai: https://git-scm.com/
    echo Sau khi cai xong, hay mo lai file nay.
    echo.
    pause
    exit /b 1
)

rem 2. Kiem tra Python
set PY_CMD=python
where python >nul 2>nul
if errorlevel 1 (
    where py >nul 2>nul
    if not errorlevel 1 (
        set PY_CMD=py
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
        set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    ) else (
        echo [LOI] Khong tim thay Python!
        echo Vui long cai dat Python 3.10+ va tick vao "Add Python to PATH".
        echo.
        pause
        exit /b 1
    )
)

rem 3. Thiet lap thong tin Git user neu chua co (tranh loi unable to auto-detect email)
git config user.name >nul 2>nul
if errorlevel 1 (
    echo [*] Thiet lap thong tin Git user: thincole...
    git config user.name "thincole"
    git config user.email "thincole@users.noreply.github.com"
)

rem 4. Lay thong tin phien ban
for /f "delims=" %%v in ('%PY_CMD% utils\version_mgr.py --current') do set "CUR_VER=%%v"
for /f "delims=" %%v in ('%PY_CMD% utils\version_mgr.py --next') do set "NEXT_VER=%%v"

echo Repository : https://github.com/thincole/checkduet
echo Phien ban hien tai : %CUR_VER%
echo Phien ban de xuat  : %NEXT_VER%
echo.

set /p "INPUT_VER=Nhap phien ban moi [Nhan Enter de chon %NEXT_VER%]: "
if "%INPUT_VER%"=="" set "INPUT_VER=%NEXT_VER%"

rem Cap nhat version.txt
for /f "delims=" %%v in ('%PY_CMD% utils\version_mgr.py --set "%INPUT_VER%"') do set "TARGET_VER=%%v"
echo.
echo [OK] Da dat phien ban: v%TARGET_VER%
echo.

rem 5. Khoi tao Git neu chua co
if not exist ".git" (
    echo [*] Khoi tao Git repository cuc bo...
    git init
    git branch -M main
)

rem 6. Cau hinh Remote Origin
git remote get-url origin >nul 2>nul
if errorlevel 1 (
    echo [*] Them remote origin: https://github.com/thincole/checkduet.git
    git remote add origin https://github.com/thincole/checkduet.git
) else (
    git remote set-url origin https://github.com/thincole/checkduet.git
)

rem 7. Nhap Commit Message
set /p "COMMIT_MSG=Nhap noi dung commit [Nhan Enter de dung 'Release v%TARGET_VER%']: "
if "%COMMIT_MSG%"=="" set "COMMIT_MSG=Release v%TARGET_VER%"

rem 8. Them file va commit
echo.
echo [*] Dang chuan bi cac tep tin de commit (database trang + settings)...
git add .

rem Kiem tra thay doi can commit
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "%COMMIT_MSG%"
    if errorlevel 1 (
        echo [LOI] Commit that bai!
        pause
        exit /b 1
    )
) else (
    echo [*] Khong co file ma nguon nao moi can commit them.
)

rem 9. Day code len GitHub
echo.
echo [*] Dang day code len GitHub branch main (https://github.com/thincole/checkduet)...
git push -u origin main
if errorlevel 1 (
    echo.
    echo ================================================================
    echo [CANH BAO] Push that bai! Co the do:
    echo 1. Ban chua dang nhap GitHub tren may nay hoac khong co quyen push.
    echo 2. Tren GitHub da co commit gay lech nhanh (non-fast-forward).
    echo ================================================================
    echo.
    set /p "RETRY_REBASE=Ban co muon thu keo ve voi rebase roi day lai khong? [Y/N]: "
    if /i "%RETRY_REBASE%"=="Y" (
        git pull --rebase origin main
        git push -u origin main
        if errorlevel 1 (
            echo [LOI] Van khong the push len GitHub. Vui long kiem tra quyen repository.
            pause
            exit /b 1
        )
    ) else (
        pause
        exit /b 1
    )
)

echo.
echo ================================================================
echo  [THANH CONG] Da day phien ban v%TARGET_VER% len GitHub thanh cong!
echo  URL: https://github.com/thincole/checkduet
echo ================================================================
echo.
pause
