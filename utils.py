# utils.py

# utils.py

import sys
import os
import logging
from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QApplication
from PyQt6.QtGui import QColor, QImage, QPixmap, QColorSpace

logger = logging.getLogger(__name__)


def resource_path(relative_path, warn_if_missing=True):
    """
    Получает абсолютный путь к ресурсу, работает как для dev, так и для PyInstaller.
    """
    try:
        # PyInstaller
        base_path = sys._MEIPASS
    except AttributeError:
        if getattr(sys, 'frozen', False):
            # Nuitka standalone
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))

    full_path = os.path.join(base_path, relative_path)

    # Проверка существования файла (для отладки)
    if warn_if_missing and not os.path.exists(full_path):
        logger.warning(f"Ресурс не найден: {full_path}")

    return full_path


def apply_shadow_effect(widget, blur_radius=20, x_offset=0, y_offset=0, color=None):
    """
    Применяет эффект тени к виджету.

    Args:
        widget: Виджет, к которому применяется эффект
        blur_radius: Радиус размытия тени (по умолчанию 20)
        x_offset: Смещение тени по X (по умолчанию 0)
        y_offset: Смещение тени по Y (по умолчанию 0)
        color: Цвет тени (по умолчанию полупрозрачный черный)
    """
    try:
        shadow = QGraphicsDropShadowEffect(widget)
        shadow.setBlurRadius(blur_radius)
        shadow.setOffset(x_offset, y_offset)

        if color is None:
            color = QColor(0, 0, 0, 100)

        shadow.setColor(color)
        widget.setGraphicsEffect(shadow)
    except Exception as e:
        logger.warning(f"Не удалось применить эффект тени: {e}")


def format_file_size(size_bytes):
    """
    Форматирует размер файла в читаемый вид.

    Args:
        size_bytes: Размер в байтах

    Returns:
        Строка с размером (например, "1.5 MB")
    """
    try:
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"
    except (TypeError, ValueError):
        return "Unknown"


def safe_remove_file(file_path):
    """
    Безопасно удаляет файл с обработкой ошибок.

    Args:
        file_path: Путь к файлу

    Returns:
        tuple: (success: bool, error_message: str or None)
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True, None
        else:
            return False, "Файл не существует"
    except PermissionError:
        return False, "Нет прав доступа"
    except Exception as e:
        return False, str(e)


def ensure_directory_exists(directory_path):
    """
    Гарантирует существование директории, создает если нужно.

    Args:
        directory_path: Путь к директории

    Returns:
        bool: True если директория существует или была создана
    """
    try:
        os.makedirs(directory_path, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Не удалось создать директорию {directory_path}: {e}")
        return False
    
def pil_to_color_managed_pixmap(pil_image, original_icc_profile: bytes = None) -> QPixmap:
    """
    Преобразует PIL Image в QPixmap с точным сопоставлением встроенного ICC-профиля
    изображения и цветового пространства текущего системного монитора.
    """
    from PyQt6.QtGui import QImage, QPixmap, QColorSpace
    from PyQt6.QtWidgets import QApplication

    try:
        # 1. Извлекаем ICC профиль (приоритет у явно переданного оригинального)
        icc_profile = original_icc_profile
        if not icc_profile and hasattr(pil_image, 'info'):
            icc_profile = pil_image.info.get('icc_profile')
        
        # 2. Приводим к формату RGB
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')
        
        img_data = pil_image.tobytes("raw", "RGB")
        q_image = QImage(
            img_data, 
            pil_image.width, 
            pil_image.height, 
            pil_image.width * 3, 
            QImage.Format.Format_RGB888
        )
        
        # 3. Назначаем исходное цветовое пространство изображения
        q_color_space = None
        if icc_profile:
            try:
                q_color_space = QColorSpace.fromIccProfile(icc_profile)
            except Exception:
                pass
        
        # Если профиль не найден или некорректен, считаем изображение стандартным sRGB
        if q_color_space is None or not q_color_space.isValid():
            q_color_space = QColorSpace(QColorSpace.NamedColorSpace.SRgb)
            
        q_image.setColorSpace(q_color_space)
        
        # 4. Выполняем точную конвертацию в цветовой профиль текущего активного экрана
        screen = QApplication.primaryScreen()
        if screen:
            screen_color_space = screen.colorSpace()
            if screen_color_space and screen_color_space.isValid():
                q_image.convertToColorSpace(screen_color_space)
                
        return QPixmap.fromImage(q_image)
    except Exception:
        # Безопасный fallback-режим на случай непредвиденных сбоев
        try:
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            img_data = pil_image.tobytes("raw", "RGB")
            q_image = QImage(
                img_data, 
                pil_image.width, 
                pil_image.height, 
                pil_image.width * 3, 
                QImage.Format.Format_RGB888
            )
            return QPixmap.fromImage(q_image)
        except Exception:
            return QPixmap()