
import requests
from PyQt6.QtCore import QThread, pyqtSignal
from PIL import Image
import io

class ClipDropWorker(QThread):
    finished = pyqtSignal(Image.Image)
    error = pyqtSignal(str)

    def __init__(self, api_key, original_image, mask_image):
        super().__init__()
        self.api_key = api_key
        self.original_image = original_image
        self.mask_image = mask_image

    def run(self):
        if not self.api_key:
            self.error.emit("API ключ ClipDrop не установлен. Перейдите в настройки.")
            return

        try:
            # Конвертация изображений в байты
            img_byte_arr = io.BytesIO()
            self.original_image.save(img_byte_arr, format='PNG')
            img_bytes = img_byte_arr.getvalue()

            mask_byte_arr = io.BytesIO()
            # Убедимся, что маска ч/б
            self.mask_image.convert("L").save(mask_byte_arr, format='PNG')
            mask_bytes = mask_byte_arr.getvalue()

            response = requests.post(
                'https://clipdrop-api.co/cleanup/v1',
                files={
                    'image_file': ('image.png', img_bytes, 'image/png'),
                    'mask_file': ('mask.png', mask_bytes, 'image/png')
                },
                headers={'x-api-key': self.api_key}
            )

            if response.ok:
                result_image = Image.open(io.BytesIO(response.content))
                result_image.load() # Загружаем в память
                self.finished.emit(result_image)
            else:
                error_msg = f"Ошибка API ({response.status_code}): {response.text}"
                if response.status_code == 402:
                    error_msg = "Закончились кредиты API ClipDrop."
                elif response.status_code == 403:
                    error_msg = "Неверный API ключ."
                self.error.emit(error_msg)

        except Exception as e:
            self.error.emit(f"Ошибка сети: {str(e)}")