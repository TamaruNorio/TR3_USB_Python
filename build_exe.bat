@echo off
setlocal enableextensions enabledelayedexpansion

REM ============================================================
REM TR3_USB_Python - PyInstaller build script (robust ASCII-only)
REM ============================================================

REM [1] normalize working dir
cd /d "%~dp0"

REM [2] locate target script
set "SCRIPT_PATH="
if exist "tr3_usb_gui.py" set "SCRIPT_PATH=%cd%\tr3_usb_gui.py"
if not defined SCRIPT_PATH if exist "python\tr3_usb_gui.py" set "SCRIPT_PATH=%cd%\python\tr3_usb_gui.py"

if not defined SCRIPT_PATH (
  echo [ERROR] Could not find "tr3_usb_gui.py" in:
  echo         %cd%  or  %cd%\python
  pause
  exit /b 1
)

REM [3] find python launcher
set "PY_CMD="
where py >nul 2>nul && set "PY_CMD=py"
if not defined PY_CMD where python >nul 2>nul && set "PY_CMD=python"
if not defined PY_CMD where python3 >nul 2>nul && set "PY_CMD=python3"

if not defined PY_CMD (
  echo [ERROR] Python was not found on PATH.
  pause
  exit /b 1
)

%PY_CMD% --version 2>nul

REM [4] ensure pyinstaller
%PY_CMD% -m pyinstaller --version >nul 2>nul
if errorlevel 1 (
  echo [INFO] Installing/upgrading pip and PyInstaller...
  %PY_CMD% -m pip install --upgrade pip
  if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip.
    pause
    exit /b 1
  )
  %PY_CMD% -m pip install --upgrade pyinstaller
  if errorlevel 1 (
    echo [ERROR] Failed to install PyInstaller.
    pause
    exit /b 1
  )
)

REM [5] clean old artifacts
echo [INFO] Cleaning old artifacts...
if exist "build" rmdir /s /q "build"
if exist "dist"  rmdir /s /q "dist"
del /q /f "tr3_usb_gui.spec" 2>nul
del /q /f "*.spec" 2>nul

REM [6] build options
set "APP_NAME=tr3_usb_gui"

REM Optional: set an icon file path (uncomment and edit if needed)
REM set "ICON_FILE=app.ico"

REM Optional: add data, format: src;dest (Windows uses semicolon)
REM Example: set "ADD_DATAS=--add-data assets;assets"
set "ICON_OPT="
if defined ICON_FILE if exist "%ICON_FILE%" set "ICON_OPT=--icon ""%ICON_FILE%"""

set "DATA_OPTS="
if defined ADD_DATAS set "DATA_OPTS=%ADD_DATAS%"

REM Compose args on one line (no carets, no trailing comments)
set "PYI_ARGS=--onefile --noconsole --name ""%APP_NAME%"" --clean"
if defined ICON_OPT set "PYI_ARGS=%PYI_ARGS% %ICON_OPT%"
if defined DATA_OPTS set "PYI_ARGS=%PYI_ARGS% %DATA_OPTS%"

echo [INFO] Building executable...
%PY_CMD% -m PyInstaller %PYI_ARGS% "%SCRIPT_PATH%"
if errorlevel 1 (
  echo [ERROR] Build failed. See logs above.
  pause
  exit /b 1
)

REM [7] result
if exist "dist\%APP_NAME%.exe" (
  echo [SUCCESS] Build completed.
  echo          Output: "%cd%\dist\%APP_NAME%.exe"
) else (
  echo [WARN] Build finished but exe not found at expected path.
  echo       Please check the "dist" folder.
)

echo.
echo Tips:
echo  - To show a console, replace --noconsole with --console.
echo  - To bundle resources, set ADD_DATAS, e.g.:
echo    set "ADD_DATAS=--add-data assets;assets"
pause
exit /b 0
