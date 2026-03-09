@echo off
chcp 65001 >nul
echo ========================================
echo WiPhoto v2.1.1 Windows Build (Nuitka)
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found! Install Python 3.10+ from python.org
    pause
    exit /b 1
)

:: Setup venv
if not exist ".venv\Scripts\activate.bat" (
    echo Creating virtual environment...
    python -m venv .venv
)
call .venv\Scripts\activate.bat

:: Install dependencies
echo Installing dependencies...
pip install --upgrade pip wheel
pip install -r requirements.txt
pip install pillow-heif
pip install nuitka ordered-set zstandard

:: Download ExifTool if missing
if not exist "exiftool_files\exiftool.exe" (
    echo Downloading ExifTool...
    if not exist exiftool_files mkdir exiftool_files
    powershell -Command "Invoke-WebRequest -Uri 'https://sourceforge.net/projects/exiftool/files/exiftool-13.52_64.zip/download' -OutFile 'exiftool.zip'"
    powershell -Command "Expand-Archive -Path 'exiftool.zip' -DestinationPath 'exiftool_files' -Force"
    powershell -Command "Get-ChildItem 'exiftool_files' -Filter 'exiftool*.exe' | Where-Object { $_.Name -ne 'exiftool.exe' } | ForEach-Object { Rename-Item $_.FullName 'exiftool.exe' }"
    del exiftool.zip
    echo ExifTool downloaded OK
)

:: Clean
echo.
echo Cleaning previous builds...
if exist build\main.dist rmdir /s /q build\main.dist
if exist build\main.build rmdir /s /q build\main.build
if exist dist\WiPhoto_Windows rmdir /s /q dist\WiPhoto_Windows
if not exist dist mkdir dist

echo.
echo ========================================
echo Building WiPhoto v2.1.1...
echo This may take 15-30 minutes...
echo ========================================
echo.

python -m nuitka ^
    --standalone ^
    --enable-plugin=pyqt6 ^
    --include-data-dir=assets=assets ^
    --include-data-dir=exiftool_files=exiftool_files ^
    --include-data-file=pro_dark.qss=pro_dark.qss ^
    --include-package=cv2 ^
    --include-package=PIL ^
    --include-package=numpy ^
    --include-package=rawpy ^
    --include-package=imagehash ^
    --include-package=skimage ^
    --include-package=pillow_heif ^
    --include-package-data=cv2 ^
    --nofollow-import-to=matplotlib ^
    --nofollow-import-to=scipy ^
    --nofollow-import-to=tkinter ^
    --nofollow-import-to=torch ^
    --nofollow-import-to=torchvision ^
    --nofollow-import-to=simple_lama_inpainting ^
    --windows-icon-from-ico=assets\icon.ico ^
    --windows-console-mode=disable ^
    --company-name="Widlily Corporation" ^
    --product-name="WiPhoto" ^
    --file-version=2.1.1.0 ^
    --product-version=2.1.1 ^
    --file-description="WiPhoto - Professional Photo Manager" ^
    --output-dir=build ^
    main.py

if errorlevel 1 (
    echo Build FAILED!
    pause
    exit /b 1
)

echo.
echo Creating distribution...
mkdir dist\WiPhoto_Windows
xcopy /e /i /y build\main.dist dist\WiPhoto_Windows
rename dist\WiPhoto_Windows\main.exe WiPhoto.exe

echo.
echo Creating ZIP archive...
cd dist
powershell -Command "Compress-Archive -Path WiPhoto_Windows -DestinationPath WiPhoto_v2.1.1_Windows.zip -Force"
cd ..

if exist dist\WiPhoto_v2.1.1_Windows.zip (
    echo.
    echo ========================================
    echo Build completed!
    echo ========================================
    echo.
    echo Executable: dist\WiPhoto_Windows\WiPhoto.exe
    echo Archive: dist\WiPhoto_v2.1.1_Windows.zip
    echo.
) else (
    echo Archive creation FAILED!
)

pause
