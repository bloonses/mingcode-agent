@echo off
REM MINGCODE-LC build script
setlocal

echo [1/3] Installing dependencies...
uv sync
if errorlevel 1 goto :error

echo [2/3] Building exe with PyInstaller...
uv run pyinstaller mingcode-lc.spec --clean --noconfirm
if errorlevel 1 goto :error

echo [3/3] Build complete. Output in dist\mingcode-lc\
dir dist\mingcode-lc\mingcode-lc.exe
goto :end

:error
echo Build failed.
exit /b 1

:end
endlocal
