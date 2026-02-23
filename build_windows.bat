@echo off
REM Build script for Windows

echo ====================================
echo WiPhoto Windows Build Script
echo ====================================

echo.
echo Step 1: Checking Python environment...
python --version
if errorlevel 1 (
    echo ERROR: Python not found!
    exit /b 1
)

echo.
echo Step 2: Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies!
    exit /b 1
)

echo.
echo Step 3: Building executable...
python setup.py build
if errorlevel 1 (
    echo ERROR: Build failed!
    exit /b 1
)

echo.
echo Step 4: Creating release archive...
set BUILD_DIR=build\exe.win-amd64-3.11
set RELEASE_DIR=WiPhoto_v1.5.0_Windows

if exist %RELEASE_DIR% rmdir /s /q %RELEASE_DIR%
mkdir %RELEASE_DIR%

xcopy /E /I /Y %BUILD_DIR%\* %RELEASE_DIR%\

REM Copy ExifTool files
echo Copying ExifTool files...
xcopy /E /I /Y exiftool_files %RELEASE_DIR%\exiftool_files\

echo.
echo Step 5: Creating ZIP archive...
powershell Compress-Archive -Path %RELEASE_DIR% -DestinationPath %RELEASE_DIR%.zip -Force

echo.
echo ====================================
echo Build completed successfully!
echo Release: %RELEASE_DIR%.zip
echo ====================================
