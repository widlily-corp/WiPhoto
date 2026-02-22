
from PyQt6.QtCore import QThread, pyqtSignal
from PIL import Image
from simple_lama_inpainting import SimpleLama


class LocalInpaintingWorker(QThread):
    finished = pyqtSignal(Image.Image)
    error = pyqtSignal(str)

    def __init__(self, original_image, mask_image):
        super().__init__()
        self.original_image = original_image
        self.mask_image = mask_image

    def run(self):
        try:
            print("[LaMa] Старт...")

            # Сохраняем оригинальный размер для восстановления
            orig_w, orig_h = self.original_image.size

            # 1. Подготовка изображения
            if self.original_image.mode != 'RGB':
                img_input = self.original_image.convert('RGB')
            else:
                img_input = self.original_image

            # 2. Подготовка маски
            mask_input = self.mask_image.convert('L')
            mask_input = mask_input.resize(img_input.size, Image.Resampling.NEAREST)

            # 3. Умное уменьшение (Downscaling) для экономии памяти
            max_size = 1280
            needs_resize = False

            if max(orig_w, orig_h) > max_size:
                print(f"[LaMa] Уменьшение с {orig_w}x{orig_h} до {max_size}px...")
                ratio = min(max_size / orig_w, max_size / orig_h)
                new_size = (int(orig_w * ratio), int(orig_h * ratio))

                img_input = img_input.resize(new_size, Image.Resampling.LANCZOS)
                mask_input = mask_input.resize(new_size, Image.Resampling.NEAREST)
                needs_resize = True

            # 4. Обработка нейросетью
            print("[LaMa] Запуск нейросети...")
            lama = SimpleLama()
            result_small = lama(img_input, mask_input)

            # 5. Восстановление размера (Upscaling)
            if needs_resize:
                print(f"[LaMa] Восстановление размера до {orig_w}x{orig_h}...")
                final_image = result_small.resize((orig_w, orig_h), Image.Resampling.LANCZOS)
            else:
                final_image = result_small

            # (Опционально) Можно было бы вклеить только измененную часть в оригинал,
            # но простой ресайз работает стабильнее.

            print("[LaMa] Готово!")
            self.finished.emit(final_image)

        except Exception as e:
            print(f"[LaMa Error] {e}")
            self.error.emit(f"Ошибка нейросети: {str(e)}")