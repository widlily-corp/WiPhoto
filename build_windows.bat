@echo off
echo ========================================
echo WiPhoto Windows Build Script
echo ========================================
echo.

REM Activate virtual environment if exists
if exist .venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
)

REM Clean previous builds
echo Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist\WiPhoto rmdir /s /q dist\WiPhoto

REM Build with PyInstaller
echo.
echo Building WiPhoto...
pyinstaller WiPhoto.spec

REM Check if build was successful
if exist dist\WiPhoto\WiPhoto.exe (
    echo.
    echo ========================================
    echo Build completed successfully!
    echo Executable location: dist\WiPhoto\WiPhoto.exe
    echo ========================================
) else (
    echo.
    echo ========================================
    echo Build FAILED!
    echo Check the output above for errors.
    echo ========================================
    exit /b 1
)

echo.
pause
