# core/document_scanner.py

import logging
import cv2
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DocumentCorners:
    """Углы обнаруженного документа"""
    top_left: Tuple[int, int]
    top_right: Tuple[int, int]
    bottom_right: Tuple[int, int]
    bottom_left: Tuple[int, int]


class DocumentScanner:
    """Сканер документов с автоматическим выравниванием и улучшением текста"""

    @staticmethod
    def order_points(pts: np.ndarray) -> np.ndarray:
        """Упорядочивает точки в порядке: top-left, top-right, bottom-right, bottom-left"""
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        return rect

    @staticmethod
    def four_point_transform(image: np.ndarray, pts: np.ndarray) -> np.ndarray:
        """Применяет перспективную трансформацию к изображению"""
        rect = DocumentScanner.order_points(pts)
        (tl, tr, br, bl) = rect

        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))

        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))

        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]
        ], dtype="float32")

        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
        return warped

    def detect_document(self, image_path: str) -> Optional[DocumentCorners]:
        """Обнаруживает границы документа на изображении"""
        try:
            image = cv2.imread(image_path)
            if image is None:
                return None
            return self._detect_from_image(image)
        except Exception as e:
            logger.error(f"Error detecting document in {image_path}: {e}")
            return None

    def _detect_from_image(self, image: np.ndarray) -> Optional[DocumentCorners]:
        """Обнаруживает границы документа в numpy-изображении"""
        h, w = image.shape[:2]

        # Resize for faster processing
        max_dim = 1024
        scale = 1.0
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            resized = cv2.resize(image, None, fx=scale, fy=scale)
        else:
            resized = image

        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Try multiple edge detection strategies
        corners = self._find_quad_contour(blurred, resized)

        if corners is None:
            # Try with morphological closing to connect edges
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            closed = cv2.morphologyEx(blurred, cv2.MORPH_CLOSE, kernel)
            corners = self._find_quad_contour(closed, resized)

        if corners is None:
            # Try adaptive threshold approach
            thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                           cv2.THRESH_BINARY, 11, 2)
            thresh = cv2.bitwise_not(thresh)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            thresh = cv2.dilate(thresh, kernel, iterations=2)
            corners = self._find_quad_from_thresh(thresh, resized)

        if corners is not None and scale != 1.0:
            # Scale corners back to original image size
            corners = DocumentCorners(
                top_left=(int(corners.top_left[0] / scale), int(corners.top_left[1] / scale)),
                top_right=(int(corners.top_right[0] / scale), int(corners.top_right[1] / scale)),
                bottom_right=(int(corners.bottom_right[0] / scale), int(corners.bottom_right[1] / scale)),
                bottom_left=(int(corners.bottom_left[0] / scale), int(corners.bottom_left[1] / scale)),
            )

        return corners

    def _find_quad_contour(self, gray: np.ndarray, original: np.ndarray) -> Optional[DocumentCorners]:
        """Find quadrilateral contour using Canny edge detection"""
        edged = cv2.Canny(gray, 50, 200)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edged = cv2.dilate(edged, kernel, iterations=1)

        contours, _ = cv2.findContours(edged, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]

        h, w = original.shape[:2]
        min_area = h * w * 0.1  # At least 10% of image area

        for c in contours:
            area = cv2.contourArea(c)
            if area < min_area:
                continue

            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)

            if len(approx) == 4:
                pts = approx.reshape(4, 2)
                ordered = self.order_points(pts.astype("float32"))
                return DocumentCorners(
                    top_left=tuple(ordered[0].astype(int)),
                    top_right=tuple(ordered[1].astype(int)),
                    bottom_right=tuple(ordered[2].astype(int)),
                    bottom_left=tuple(ordered[3].astype(int))
                )
        return None

    def _find_quad_from_thresh(self, thresh: np.ndarray, original: np.ndarray) -> Optional[DocumentCorners]:
        """Find quadrilateral from thresholded image"""
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

        h, w = original.shape[:2]
        min_area = h * w * 0.1

        for c in contours:
            if cv2.contourArea(c) < min_area:
                continue
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4:
                pts = approx.reshape(4, 2)
                ordered = self.order_points(pts.astype("float32"))
                return DocumentCorners(
                    top_left=tuple(ordered[0].astype(int)),
                    top_right=tuple(ordered[1].astype(int)),
                    bottom_right=tuple(ordered[2].astype(int)),
                    bottom_left=tuple(ordered[3].astype(int))
                )
        return None

    def enhance_document(self, image: np.ndarray, mode: str = "auto") -> np.ndarray:
        """
        Улучшает изображение документа для читаемости текста.

        Режимы:
        - "auto": автоматический подбор
        - "bw": чёрно-белый (максимум контраста)
        - "clean": чистый документ (адаптивный порог)
        - "color": цветной документ (усиление контраста)
        """
        if mode == "bw":
            return self._enhance_bw(image)
        elif mode == "clean":
            return self._enhance_clean(image)
        elif mode == "color":
            return self._enhance_color(image)
        else:
            # Auto: determine if document is mostly text or has color content
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
            # Check color saturation
            if len(image.shape) == 3:
                hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
                mean_sat = np.mean(hsv[:, :, 1])
                if mean_sat > 40:
                    return self._enhance_color(image)
            return self._enhance_clean(image)

    def _enhance_bw(self, image: np.ndarray) -> np.ndarray:
        """Чёрно-белый режим — максимальный контраст для текста"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        # Adaptive threshold for clean B&W text
        result = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 10
        )
        return cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)

    def _enhance_clean(self, image: np.ndarray) -> np.ndarray:
        """Чистый документ — убирает тени и выравнивает фон"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

        # Remove shadows using large-scale morphological background estimation
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
        bg = cv2.morphologyEx(gray, cv2.MORPH_DILATE, kernel)
        # Normalize: divide by background to remove uneven lighting
        normalized = cv2.divide(gray, bg, scale=255)

        # Sharpen
        sharpened = cv2.GaussianBlur(normalized, (0, 0), 3)
        sharpened = cv2.addWeighted(normalized, 1.5, sharpened, -0.5, 0)

        # CLAHE for local contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(sharpened)

        return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

    def _enhance_color(self, image: np.ndarray) -> np.ndarray:
        """Цветной документ — усиливает контраст, сохраняя цвета"""
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        # CLAHE on L channel
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l = clahe.apply(l)

        # Boost saturation slightly
        enhanced = cv2.merge([l, a, b])
        result = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

        # Sharpen
        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]]) / 1.0
        result = cv2.filter2D(result, -1, kernel * 0.3 + np.eye(3).flatten().reshape(3, 3) * 0.7)

        return result

    def scan_document(self, image_path: str, output_path: str,
                      enhance_mode: str = "auto") -> bool:
        """
        Сканирует документ: обнаруживает границы, выравнивает и улучшает.

        Args:
            image_path: Путь к входному изображению
            output_path: Путь для сохранения результата
            enhance_mode: Режим улучшения ("auto", "bw", "clean", "color", "none")

        Returns:
            True если успешно, False иначе
        """
        try:
            image = cv2.imread(image_path)
            if image is None:
                return False

            corners = self._detect_from_image(image)

            if corners:
                pts = np.array([
                    corners.top_left,
                    corners.top_right,
                    corners.bottom_right,
                    corners.bottom_left
                ], dtype="float32")
                warped = self.four_point_transform(image, pts)
            else:
                # No document edges found — use whole image
                warped = image

            # Enhance
            if enhance_mode != "none":
                warped = self.enhance_document(warped, enhance_mode)

            cv2.imwrite(output_path, warped)
            return True

        except Exception as e:
            logger.error(f"Error scanning document from {image_path}: {e}")
            return False

    def scan_to_numpy(self, image: np.ndarray, enhance_mode: str = "auto") -> np.ndarray:
        """Сканирует документ из numpy-массива, возвращает результат как numpy"""
        corners = self._detect_from_image(image)

        if corners:
            pts = np.array([
                corners.top_left,
                corners.top_right,
                corners.bottom_right,
                corners.bottom_left
            ], dtype="float32")
            warped = self.four_point_transform(image, pts)
        else:
            warped = image.copy()

        if enhance_mode != "none":
            warped = self.enhance_document(warped, enhance_mode)

        return warped

    def get_preview_with_corners(self, image: np.ndarray) -> Tuple[np.ndarray, Optional[DocumentCorners]]:
        """Возвращает изображение с отмеченными углами документа для превью"""
        corners = self._detect_from_image(image)
        preview = image.copy()

        if corners:
            pts = np.array([
                corners.top_left, corners.top_right,
                corners.bottom_right, corners.bottom_left
            ], dtype=np.int32)
            cv2.polylines(preview, [pts], True, (0, 255, 0), 3)
            for pt in pts:
                cv2.circle(preview, tuple(pt), 8, (0, 0, 255), -1)

        return preview, corners
