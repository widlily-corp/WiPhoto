# utils.py

import sys
import os
from PyQt6.QtWidgets import QGraphicsDropShadowEffect
from PyQt6.QtGui import QColor


def resource_path(relative_path):
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
            base_path = os.path.abspath(".")

    full_path = os.path.join(base_path, relative_path)

    # Проверка существования файла (для отладки)
    if not os.path.exists(full_path):
        print(f"ПРЕДУПРЕЖДЕНИЕ: Ресурс не найден: {full_path}")

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
        print(f"Не удалось применить эффект тени: {e}")


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
    except:
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
        print(f"Не удалось создать директорию {directory_path}: {e}")
        return False