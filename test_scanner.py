import sys
import time
from core.analyzer import process_single_file

test_file = r"c:\Users\Widlily\PycharmProjects\WiPhoto\test_media\portrait_01.jpg"
print(f"Тестирую файл: {test_file}")
print("Начало обработки...")

start = time.time()
result = process_single_file(test_file)
elapsed = time.time() - start

if result:
    print(f"✓ Успешно! Время: {elapsed:.2f}сек")
    print(f"  Thumbnail: {result.get('thumbnail_path')}")
    print(f"  Размер: {result.get('width')}x{result.get('height')}")
    print(f"  Камера: {result.get('camera_model')}")
else:
    print(f"✗ Ошибка обработки")
    sys.exit(1)
