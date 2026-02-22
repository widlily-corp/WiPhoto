# core/document_scanner.py

import cv2
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class DocumentCorners:
    """Углы обнаруженного документа"""
    top_left: Tuple[int, int]
    top_right: Tuple[int, int]
    bottom_right: Tuple[int, int]
    bottom_left: Tuple[int, int]


class DocumentScanner:
    """Сканер документов с автоматическим выравниванием"""

    @staticmethod
    def order_points(pts: np.ndarray) -> np.ndarray:
        """Упорядочивает точки в порядке: top-left, top-right, bottom-right, bottom-left"""
        rect = np.zeros((4, 2), dtype="float32")

        # top-left будет иметь наименьшую сумму, bottom-right - наибольшую
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]

        # top-right будет иметь наименьшую разницу, bottom-left - наибольшую
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]

        return rect

    @staticmethod
    def four_point_transform(image: np.ndarray, pts: np.ndarray) -> np.ndarray:
        """Применяет перспективную трансформацию к изображению"""
        rect = DocumentScanner.order_points(pts)
        (tl, tr, br, bl) = rect

        # Вычисляем ширину нового изображения
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))

        # Вычисляем высоту нового изображения
        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))

        # Целевые точки для трансформации
        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]
        ], dtype="float32")

        # Вычисляем матрицу перспективной трансформации
        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))

        return warped

    def detect_document(self, image_path: str) -> Optional[DocumentCorners]:
        """
        Обнаруживает границы документа на изображении

        Args:
            image_path: Путь к изображению

        Returns:
            Углы документа или None если не найдено
        """
        try:
            # Загружаем изображение
            image = cv2.imread(image_path)
            if image is None:
                return None

            # Создаем копию для обработки
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edged = cv2.Canny(blurred, 75, 200)

            # Находим контуры
            contours, _ = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

            # Ищем четырехугольник
            for c in contours:
                peri = cv2.arcLength(c, True)
                approx = cv2.approxPolyDP(c, 0.02 * peri, True)

                if len(approx) == 4:
                    pts = approx.reshape(4, 2)
                    ordered = self.order_points(pts)
                    return DocumentCorners(
                        top_left=tuple(ordered[0]),
                        top_right=tuple(ordered[1]),
                        bottom_right=tuple(ordered[2]),
                        bottom_left=tuple(ordered[3])
                    )

            return None

        except Exception as e:
            print(f"Error detecting document in {image_path}: {e}")
            return None

    def scan_document(self, image_path: str, output_path: str) -> bool:
        """
        Сканирует документ: обнаруживает границы и выравнивает

        Args:
            image_path: Путь к входному изображению
            output_path: Путь для сохранения результата

        Returns:
            True если успешно, False иначе
        """
        try:
            image = cv2.imread(image_path)
            if image is None:
                return False

            corners = self.detect_document(image_path)
            if not corners:
                return False

            # Формируем массив точек
            pts = np.array([
                corners.top_left,
                corners.top_right,
                corners.bottom_right,
                corners.bottom_left
            ], dtype="float32")

            # Применяем трансформацию
            warped = self.four_point_transform(image, pts)

            # Сохраняем результат
            cv2.imwrite(output_path, warped)
            return True

        except Exception as e:
            print(f"Error scanning document from {image_path}: {e}")
            return False
