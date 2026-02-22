# Building WiPhoto

Инструкции по сборке WiPhoto для Windows и Linux.

## Требования

### Windows
- Python 3.9+ (64-bit)
- pip
- [ExifTool](https://exiftool.org/) (скачать и распаковать в папку `exiftool_files/`)

### Linux
- Python 3.9+
- pip
- ExifTool (`sudo apt install libexiftool-perl` или `sudo dnf install perl-Image-ExifTool`)
- Qt6 библиотеки

## Сборка для Windows

### Автоматическая сборка

Запустите скрипт:
```cmd
build_windows.bat
```

Скрипт автоматически:
1. Проверит Python
2. Установит зависимости
3. Соберёт exe файл
4. Создаст архив `WiPhoto_v1.5.0_Windows.zip` с включённым ExifTool

### Ручная сборка

```cmd
# 1. Установите зависимости
pip install -r requirements.txt

# 2. Соберите exe
python setup.py build

# 3. Скопируйте ExifTool в папку build
xcopy /E /I /Y exiftool_files build\exe.win-amd64-3.11\exiftool_files\

# 4. Архивируйте результат
powershell Compress-Archive -Path build\exe.win-amd64-3.11 -DestinationPath WiPhoto_v1.5.0_Windows.zip
```

## Сборка для Linux

### Автоматическая сборка

Запустите скрипт:
```bash
chmod +x build_linux.sh
./build_linux.sh
```

Скрипт автоматически:
1. Создаст virtual environment
2. Установит зависимости
3. Создаст архив `WiPhoto_v1.5.0_Linux.tar.gz`

### Ручная сборка

```bash
# 1. Создайте виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate

# 2. Установите зависимости
pip install -r requirements.txt

# 3. Создайте папку релиза
mkdir WiPhoto_v1.5.0_Linux
cp -r *.py assets controllers core models views *.qss requirements.txt *.md WiPhoto_v1.5.0_Linux/

# 4. Создайте лаунчер
cat > WiPhoto_v1.5.0_Linux/wiphoto.sh << 'EOF'
#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"
python3 main.py "$@"
EOF
chmod +x WiPhoto_v1.5.0_Linux/wiphoto.sh

# 5. Архивируйте
tar -czf WiPhoto_v1.5.0_Linux.tar.gz WiPhoto_v1.5.0_Linux
```

## Структура релиза

### Windows Archive
```
WiPhoto_v1.5.0_Windows/
├── WiPhoto.exe                 # Главный исполняемый файл
├── exiftool_files/             # ExifTool и зависимости
│   ├── exiftool.pl
│   ├── lib/
│   └── *.dll
├── lib/                        # Python библиотеки
├── assets/                     # Ресурсы приложения
└── *.dll                       # Qt и Python DLL

```

### Linux Archive
```
WiPhoto_v1.5.0_Linux/
├── wiphoto.sh                  # Лаунчер
├── main.py                     # Точка входа
├── requirements.txt            # Зависимости
├── assets/                     # Ресурсы
├── controllers/                # Код приложения
├── core/
├── models/
├── views/
├── *.qss                       # Стили
└── README.md
```

## Распространение

### GitHub Releases

1. Создайте новый релиз на GitHub
2. Загрузите архивы:
   - `WiPhoto_v1.5.0_Windows.zip`
   - `WiPhoto_v1.5.0_Linux.tar.gz`
3. Добавьте release notes с описанием изменений

### Checksums

Для безопасности создайте контрольные суммы:

```bash
# Windows
certutil -hashfile WiPhoto_v1.5.0_Windows.zip SHA256

# Linux
sha256sum WiPhoto_v1.5.0_Linux.tar.gz
```

## Устранение проблем

### Windows

**Проблема**: `exiftool.exe not found`
- **Решение**: Убедитесь что `exiftool_files/` скопирована в папку с exe

**Проблема**: `MSVCP140.dll not found`
- **Решение**: Установите [Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe)

### Linux

**Проблема**: `ModuleNotFoundError: No module named 'PyQt6'`
- **Решение**: `pip install -r requirements.txt`

**Проблема**: `exiftool: command not found`
- **Решение**: `sudo apt install libexiftool-perl` (Ubuntu/Debian)

**Проблема**: Qt platform plugin error
- **Решение**: `sudo apt install qt6-base-dev libqt6gui6`

## Минимизация размера

Для уменьшения размера архива:

1. Используйте UPX для сжатия exe/dll (Windows)
2. Удалите ненужные locale файлы из Qt
3. Используйте `--exclude` при tar для пропуска `__pycache__`

```bash
# Пример для Linux
tar --exclude='__pycache__' --exclude='*.pyc' -czf WiPhoto_v1.5.0_Linux.tar.gz WiPhoto_v1.5.0_Linux
```

## Проверка сборки

После сборки протестируйте:

1. Запуск приложения
2. Сканирование папки с фотографиями
3. Открытие изображения в редакторе
4. Применение различных фильтров
5. Экспорт изображения
6. Просмотр метаданных (ExifTool должен работать)

Все функции должны работать без ошибок.
