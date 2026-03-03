# Компиляция WiPhoto под Ubuntu/Linux

## Быстрая сборка (AppImage)

```bash
# 1. Установка зависимостей
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git libexiftool-perl

# 2. Клонирование репозитория
git clone https://github.com/widlily-corp/WiPhoto.git
cd WiPhoto

# 3. Создание виртуального окружения
python3 -m venv .venv
source .venv/bin/activate

# 4. Установка зависимостей
pip install -r requirements.txt
pip install pyinstaller

# 5. Сборка исполняемого файла
pyinstaller --name WiPhoto \
    --windowed \
    --icon assets/icon.ico \
    --add-data "assets:assets" \
    --add-data "liquid_glass.qss:." \
    main.py

# 6. Архивирование
cd dist
tar -czf WiPhoto_v1.5.0_Linux_x64.tar.gz WiPhoto/
```

## Результат

Готовая сборка: `dist/WiPhoto_v1.5.0_Linux_x64.tar.gz`

## Запуск

```bash
tar -xzf WiPhoto_v1.5.0_Linux_x64.tar.gz
cd WiPhoto
./WiPhoto
```

## Альтернатива: Запуск из исходников

```bash
# Распаковать
tar -xzf WiPhoto_v1.5.0_Linux.tar.gz
cd WiPhoto_v1.5.0_Linux

# Установить зависимости
pip install -r requirements.txt

# Запустить
./wiphoto.sh
# или
python3 main.py
```
