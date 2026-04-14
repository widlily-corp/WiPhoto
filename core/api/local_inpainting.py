
import logging
from PyQt6.QtCore import QThread, pyqtSignal
from PIL import Image
import numpy as np
import cv2

logger = logging.getLogger(__name__)


class LocalInpaintingWorker(QThread):
    """Enhanced inpainting worker with multi-method support"""
    finished = pyqtSignal(Image.Image)
    error = pyqtSignal(str)

    def __init__(self, original_image, mask_image):
        super().__init__()
        self.original_image = original_image
        self.mask_image = mask_image

    def run(self):
        try:
            logger.info("Старт улучшенного удаления объектов...")

            # Сохраняем оригинальный размер
            orig_w, orig_h = self.original_image.size

            # Подготовка изображения
            if self.original_image.mode != 'RGB':
                img_input = self.original_image.convert('RGB')
            else:
                img_input = self.original_image

            # Подготовка маски
            mask_input = self.mask_image.convert('L')
            mask_input = mask_input.resize(img_input.size, Image.Resampling.NEAREST)

            # Попытка использования LaMa с улучшенными параметрами
            try:
                from simple_lama_inpainting import SimpleLama
                logger.info("Использование нейросетевой модели LaMa...")

                # Оптимальный размер для качества
                max_size = 2048
                needs_resize = False

                if max(orig_w, orig_h) > max_size:
                    logger.info(f"Масштабирование с {orig_w}x{orig_h} до {max_size}px...")
                    ratio = min(max_size / orig_w, max_size / orig_h)
                    new_size = (int(orig_w * ratio), int(orig_h * ratio))

                    img_input = img_input.resize(new_size, Image.Resampling.LANCZOS)
                    mask_input = mask_input.resize(new_size, Image.Resampling.NEAREST)
                    needs_resize = True

                # Обработка нейросетью
                lama = SimpleLama()
                result_small = lama(img_input, mask_input)

                # Восстановление размера с улучшенной интерполяцией
                if needs_resize:
                    logger.info(f"Восстановление размера до {orig_w}x{orig_h}...")
                    final_image = result_small.resize((orig_w, orig_h), Image.Resampling.LANCZOS)
                else:
                    final_image = result_small

                # Постобработка: сглаживание границ
                final_image = self._blend_edges(self.original_image, final_image, mask_input)

                logger.info("LaMa inpainting завершено")
                self.finished.emit(final_image)

            except ImportError:
                # Fallback: использование улучшенного OpenCV inpainting
                logger.info("LaMa недоступна, использование улучшенного OpenCV метода...")
                result = self._opencv_inpaint_enhanced(img_input, mask_input)
                self.finished.emit(result)

        except Exception as e:
            logger.error(f"Ошибка inpainting: {e}")
            self.error.emit(f"Ошибка удаления объекта: {str(e)}")

    def _opencv_inpaint_enhanced(self, img: Image.Image, mask: Image.Image) -> Image.Image:
        """Улучшенный метод OpenCV с комбинацией алгоритмов"""
        # Конвертируем в numpy arrays
        img_np = np.array(img)
        mask_np = np.array(mask)

        # Расширяем маску для лучшего захвата краев
        kernel = np.ones((5, 5), np.uint8)
        mask_dilated = cv2.dilate(mask_np, kernel, iterations=2)

        # Применяем два метода inpainting и смешиваем результаты
        # 1. Telea - быстрый, хорош для текстур
        result1 = cv2.inpaint(img_np, mask_dilated, 10, cv2.INPAINT_TELEA)

        # 2. NS (Navier-Stokes) - медленнее, но лучше для структур
        result2 = cv2.inpaint(img_np, mask_dilated, 10, cv2.INPAINT_NS)

        # Смешиваем результаты (70% Telea, 30% NS)
        result = cv2.addWeighted(result1, 0.7, result2, 0.3, 0)

        # Дополнительная обработка: bilateral filter для сглаживания
        result = cv2.bilateralFilter(result, 9, 75, 75)

        return Image.fromarray(result)

    def _blend_edges(self, original: Image.Image, inpainted: Image.Image, mask: Image.Image) -> Image.Image:
        """Сглаживает края между оригиналом и обработанной областью"""
        try:
            orig_np = np.array(original.convert('RGB'))
            inpaint_np = np.array(inpainted.convert('RGB'))
            mask_np = np.array(mask.resize(original.size, Image.Resampling.NEAREST))

            # Создаем размытую маску для плавного перехода
            mask_float = mask_np.astype(float) / 255.0
            mask_blur = cv2.GaussianBlur(mask_float, (21, 21), 11)
            mask_3ch = np.stack([mask_blur] * 3, axis=2)

            # Плавное смешивание
            result = (inpaint_np * mask_3ch + orig_np * (1 - mask_3ch)).astype(np.uint8)

            return Image.fromarray(result)
        except Exception:
            return inpainted