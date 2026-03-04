@echo off
REM ========================================
REM WiPhoto Windows Build Script (Nuitka)
REM ========================================

echo ========================================
echo WiPhoto Windows Build with Nuitka
echo ========================================
echo.

REM Activate virtual environment
if exist .venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
) else (
    echo ERROR: Virtual environment not found!
    echo Please run: python -m venv .venv
    pause
    exit /b 1
)

REM Check if Nuitka is installed
python -c "import nuitka" 2>nul
if errorlevel 1 (
    echo Installing Nuitka...
    pip install nuitka ordered-set zstandard
)

REM Clean previous builds
echo.
echo Cleaning previous builds...
if exist build\wiphoto.dist rmdir /s /q build\wiphoto.dist
if exist build\wiphoto.build rmdir /s /q build\wiphoto.build
if exist dist\WiPhoto_Windows rmdir /s /q dist\WiPhoto_Windows

REM Create dist directory
if not exist dist mkdir dist

echo.
echo ========================================
echo Building WiPhoto with Nuitka...
echo This may take 10-20 minutes...
echo ========================================
echo.

REM Build with Nuitka
python -m nuitka ^
    --standalone ^
    --onefile ^
    --windows-console-mode=disable ^
    --enable-plugin=pyqt6 ^
    --include-data-dir=assets=assets ^
    --include-data-file=liquid_glass.qss=liquid_glass.qss ^
    --include-data-dir=exiftool_files=exiftool_files ^
    --include-package=cv2 ^
    --include-package=PIL ^
    --include-package=numpy ^
    --include-package=rawpy ^
    --include-package=imagehash ^
    --include-package=skimage ^
    --include-package=simple_lama_inpainting ^
    --include-package=torch ^
    --include-package=torchvision ^
    --include-package-data=cv2 ^
    --include-package-data=simple_lama_inpainting ^
    --include-package-data=torch ^
    --nofollow-import-to=matplotlib ^
    --nofollow-import-to=scipy ^
    --nofollow-import-to=tkinter ^
    --windows-icon-from-ico=assets\icon.ico ^
    --company-name="Widlily Corporation" ^
    --product-name="WiPhoto" ^
    --file-version=1.5.1.0 ^
    --product-version=1.5.1 ^
    --file-description="WiPhoto - Professional Photo Manager" ^
    --output-dir=build ^
    main.py

if errorlevel 1 (
    echo.
    echo ========================================
    echo Build FAILED!
    echo Check the output above for errors.
    echo ========================================
    pause
    exit /b 1
)

echo.
echo ========================================
echo Creating distribution package...
echo ========================================

REM Create distribution directory
mkdir dist\WiPhoto_Windows

REM Copy executable
copy build\main.exe dist\WiPhoto_Windows\WiPhoto.exe

REM Copy data files
xcopy /E /I /Y assets dist\WiPhoto_Windows\assets
copy /Y liquid_glass.qss dist\WiPhoto_Windows\
xcopy /E /I /Y exiftool_files dist\WiPhoto_Windows\exiftool_files

REM Create README
echo WiPhoto v1.5.1 > dist\WiPhoto_Windows\README.txt
echo. >> dist\WiPhoto_Windows\README.txt
echo Run WiPhoto.exe to start the application. >> dist\WiPhoto_Windows\README.txt
echo. >> dist\WiPhoto_Windows\README.txt
echo For more information visit: >> dist\WiPhoto_Windows\README.txt
echo https://github.com/widlily-corp/WiPhoto >> dist\WiPhoto_Windows\README.txt

echo.
echo ========================================
echo Creating ZIP archive...
echo ========================================

REM Create ZIP archive
cd dist
powershell -Command "Compress-Archive -Path WiPhoto_Windows -DestinationPath WiPhoto_v1.5.1_Windows.zip -Force -CompressionLevel Optimal"
cd ..

if exist dist\WiPhoto_v1.5.1_Windows.zip (
    echo.
    echo ========================================
    echo Build completed successfully!
    echo ========================================
    echo.
    echo Executable: dist\WiPhoto_Windows\WiPhoto.exe
    echo Archive: dist\WiPhoto_v1.5.1_Windows.zip
    echo.
    for %%A in (dist\WiPhoto_v1.5.1_Windows.zip) do echo Archive size: %%~zA bytes
    echo.
) else (
    echo.
    echo ========================================
    echo Archive creation FAILED!
    echo ========================================
)

echo.
pause
