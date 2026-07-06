@echo off
setlocal

echo.
echo ================================================================
echo    MINGCODE v1.4.0 - Build Installer
echo ================================================================
echo.

set "PROJECT_DIR=%~dp0"
set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
cd /d "%PROJECT_DIR%"

echo [1/4] Checking PyInstaller...
python -m PyInstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo       PyInstaller not found, installing...
    python -m pip install pyinstaller
    if %errorlevel% neq 0 (
        echo       Trying Tsinghua mirror...
        python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple pyinstaller
    )
)
for /f "tokens=*" %%i in ('python -m PyInstaller --version 2^>^&1') do set PVER=%%i
echo       PyInstaller version: %PVER% OK

echo.
echo [2/4] Cleaning old build files...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
echo       Cleaned OK

echo.
echo [3/4] Building exe with PyInstaller...
python -m PyInstaller mingcode.spec --clean --noconfirm
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)
if not exist "dist\mingcode.exe" (
    echo.
    echo [ERROR] mingcode.exe not found, build may have failed
    pause
    exit /b 1
)
echo       Build successful: dist\mingcode.exe OK

echo.
echo [4/4] Checking Inno Setup...
set "ISCC_EXE="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC_EXE=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    goto found_iscc
)
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC_EXE=C:\Program Files\Inno Setup 6\ISCC.exe"
    goto found_iscc
)

echo.
echo ================================================================
echo.
echo   [OK] exe build completed!
echo.
echo   Output: %PROJECT_DIR%\dist\mingcode.exe
echo.
echo   [NOTICE] Inno Setup not detected. Cannot create graphical installer.
echo   To create a standard setup wizard:
echo     1. Download Inno Setup: https://jrsoftware.org/isdl.php
echo     2. Install it, then re-run this script
echo.
echo   You can also distribute dist\mingcode.exe directly and
echo   add its location to PATH manually.
echo.
echo ================================================================
pause
exit /b 0

:found_iscc
echo       Inno Setup found OK
echo.
echo       Compiling installer...
"%ISCC_EXE%" "setup.iss"
if %errorlevel% equ 0 (
    echo.
    echo ================================================================
    echo.
    echo   [SUCCESS] Build complete!
    echo.
    echo   Executable: %PROJECT_DIR%\dist\mingcode.exe
    echo   Installer:  %PROJECT_DIR%\dist\MINGCODE-Setup-1.4.0.exe
    echo.
    echo   You can now distribute MINGCODE-Setup-1.4.0.exe to users.
    echo   They double-click it to install.
    echo.
    echo ================================================================
) else (
    echo.
    echo [WARNING] Installer compilation failed, but exe is ready
    echo   Location: %PROJECT_DIR%\dist\mingcode.exe
)

echo.
pause
