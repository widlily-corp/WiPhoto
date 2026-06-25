# core/document_scanner.py

import logging
import cv2
import numpy as np
from typing import Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DocumentCorners:
    """Углы обнаруженного документа"""
    top_left: Tuple[int, int]
    top_right: Tuple[int, int]
    bottom_right: Tuple[int, int]
    bottom_left: Tuple[int, int]

    def as_array(self) -> np.ndarray:
        return np.array([self.top_left, self.top_right,
                         self.bottom_right, self.bottom_left], dtype="float32")

    @staticmethod
    def from_array(pts: np.ndarray) -> 'DocumentCorners':
        ordered = DocumentScanner.order_points(pts.astype("float32"))
        return DocumentCorners(
            top_left=tuple(ordered[0].astype(int)),
            top_right=tuple(ordered[1].astype(int)),
            bottom_right=tuple(ordered[2].astype(int)),
            bottom_left=tuple(ordered[3].astype(int)),
        )


class DocumentScanner:
    """Сканер документов с автоматическим выравниванием и улучшением текста"""

    @staticmethod
    def order_points(pts: np.ndarray) -> np.ndarray:
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
        rect = DocumentScanner.order_points(pts)
        (tl, tr, br, bl) = rect

        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))

        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))

        if maxWidth < 10 or maxHeight < 10:
            return image

        dst = np.array([
            [0, 0], [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]
        ], dtype="float32")

        M = cv2.getPerspectiveTransform(rect, dst)
        return cv2.warpPerspective(image, M, (maxWidth, maxHeight))

    # ─── Detection ───────────────────────────────────────────────

    def detect_document(self, image: np.ndarray) -> Optional[DocumentCorners]:
        """Обнаруживает границы документа (многослойный алгоритм)"""
        try:
            h, w = image.shape[:2]
            max_dim = 1024
            scale = 1.0
            if max(h, w) > max_dim:
                scale = max_dim / max(h, w)
                small = cv2.resize(image, None, fx=scale, fy=scale,
                                   interpolation=cv2.INTER_AREA)
            else:
                small = image

            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            sh, sw = gray.shape[:2]
            min_area = sh * sw * 0.05

            # Strategy 1: multiple Canny thresholds
            for lo, hi in [(30, 120), (50, 200), (75, 250)]:
                blurred = cv2.GaussianBlur(gray, (5, 5), 0)
                edged = cv2.Canny(blurred, lo, hi)
                edged = cv2.dilate(edged, np.ones((3, 3), np.uint8), iterations=2)
                edged = cv2.erode(edged, np.ones((3, 3), np.uint8), iterations=1)
                result = self._find_best_quad(edged, min_area)
                if result is not None:
                    return self._scale_corners(result, scale)

            # Strategy 2: morphological closing + Canny
            blurred = cv2.GaussianBlur(gray, (7, 7), 0)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
            closed = cv2.morphologyEx(blurred, cv2.MORPH_CLOSE, kernel)
            edged = cv2.Canny(closed, 30, 150)
            edged = cv2.dilate(edged, np.ones((5, 5), np.uint8), iterations=2)
            result = self._find_best_quad(edged, min_area)
            if result is not None:
                return self._scale_corners(result, scale)

            # Strategy 3: adaptive threshold
            for block_size in [15, 25, 41]:
                thresh = cv2.adaptiveThreshold(blurred, 255,
                                               cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                               cv2.THRESH_BINARY_INV, block_size, 5)
                thresh = cv2.dilate(thresh, np.ones((5, 5), np.uint8), iterations=3)
                thresh = cv2.erode(thresh, np.ones((3, 3), np.uint8), iterations=2)
                result = self._find_best_quad(thresh, min_area, use_external=True)
                if result is not None:
                    return self._scale_corners(result, scale)

            # Strategy 4: Hough lines → intersect to quad
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edged = cv2.Canny(blurred, 50, 200)
            result = self._find_quad_from_hough(edged, sw, sh, min_area)
            if result is not None:
                return self._scale_corners(result, scale)

            return None
        except Exception as e:
            logger.error(f"Detection error: {e}")
            return None

    def _find_best_quad(self, binary: np.ndarray, min_area: float,
                        use_external: bool = False) -> Optional[DocumentCorners]:
        """Ищет лучший четырёхугольник в бинарном изображении"""
        mode = cv2.RETR_EXTERNAL if use_external else cv2.RETR_LIST
        contours, _ = cv2.findContours(binary, mode, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:15]

        best = None
        best_area = 0

        for c in contours:
            area = cv2.contourArea(c)
            if area < min_area:
                continue

            peri = cv2.arcLength(c, True)
            # Try multiple epsilon values for approxPolyDP
            for eps_mult in [0.015, 0.02, 0.03, 0.04, 0.05]:
                approx = cv2.approxPolyDP(c, eps_mult * peri, True)
                if len(approx) == 4 and cv2.isContourConvex(approx):
                    if area > best_area:
                        best = approx.reshape(4, 2)
                        best_area = area
                    break

            # If 4-5 points but not exactly 4, try convex hull
            if best is None or area > best_area:
                hull = cv2.convexHull(c)
                if len(hull) >= 4:
                    for eps_mult in [0.02, 0.03, 0.05, 0.08]:
                        approx = cv2.approxPolyDP(hull, eps_mult * peri, True)
                        if len(approx) == 4 and cv2.isContourConvex(approx):
                            if area > best_area:
                                best = approx.reshape(4, 2)
                                best_area = area
                            break

        if best is not None:
            ordered = self.order_points(best.astype("float32"))
            return DocumentCorners(
                top_left=tuple(ordered[0].astype(int)),
                top_right=tuple(ordered[1].astype(int)),
                bottom_right=tuple(ordered[2].astype(int)),
                bottom_left=tuple(ordered[3].astype(int))
            )
        return None

    def _find_quad_from_hough(self, edges: np.ndarray, w: int, h: int,
                              min_area: float) -> Optional[DocumentCorners]:
        """Fallback: Hough lines → пересечения → лучший четырёхугольник"""
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80,
                                minLineLength=min(w, h) // 4, maxLineGap=20)
        if lines is None or len(lines) < 4:
            return None

        # Cluster lines by angle into ~horizontal and ~vertical
        horizontals = []
        verticals = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1)) % 180
            if angle < 30 or angle > 150:
                horizontals.append(line[0])
            elif 60 < angle < 120:
                verticals.append(line[0])

        if len(horizontals) < 2 or len(verticals) < 2:
            return None

        # Get extreme lines (top/bottom horizontal, left/right vertical)
        horizontals.sort(key=lambda l: (l[1] + l[3]) / 2)
        verticals.sort(key=lambda l: (l[0] + l[2]) / 2)

        top_line = horizontals[0]
        bottom_line = horizontals[-1]
        left_line = verticals[0]
        right_line = verticals[-1]

        # Find intersections
        corners = []
        for hline in [top_line, bottom_line]:
            for vline in [left_line, right_line]:
                pt = self._line_intersection(hline, vline)
                if pt is not None and 0 <= pt[0] < w and 0 <= pt[1] < h:
                    corners.append(pt)

        if len(corners) == 4:
            pts = np.array(corners, dtype="float32")
            ordered = self.order_points(pts)
            # Validate area
            area = cv2.contourArea(ordered.astype(np.int32))
            if area >= min_area:
                return DocumentCorners(
                    top_left=tuple(ordered[0].astype(int)),
                    top_right=tuple(ordered[1].astype(int)),
                    bottom_right=tuple(ordered[2].astype(int)),
                    bottom_left=tuple(ordered[3].astype(int))
                )
        return None

    @staticmethod
    def _line_intersection(line1, line2) -> Optional[Tuple[int, int]]:
        """Пересечение двух отрезков (расширенных до прямых)"""
        x1, y1, x2, y2 = line1
        x3, y3, x4, y4 = line2
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-6:
            return None
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
        px = x1 + t * (x2 - x1)
        py = y1 + t * (y2 - y1)
        return (int(px), int(py))

    def _scale_corners(self, corners: DocumentCorners, scale: float) -> DocumentCorners:
        if scale == 1.0:
            return corners
        return DocumentCorners(
            top_left=(int(corners.top_left[0] / scale), int(corners.top_left[1] / scale)),
            top_right=(int(corners.top_right[0] / scale), int(corners.top_right[1] / scale)),
            bottom_right=(int(corners.bottom_right[0] / scale), int(corners.bottom_right[1] / scale)),
            bottom_left=(int(corners.bottom_left[0] / scale), int(corners.bottom_left[1] / scale)),
        )

    # ─── Enhancement ─────────────────────────────────────────────

    def enhance_document(self, image: np.ndarray, mode: str = "auto") -> np.ndarray:
        if mode == "bw":
            return self._enhance_bw(image)
        elif mode == "clean":
            return self._enhance_clean(image)
        elif mode == "color":
            return self._enhance_color(image)
        else:
            if len(image.shape) == 3:
                hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
                if np.mean(hsv[:, :, 1]) > 40:
                    return self._enhance_color(image)
            return self._enhance_clean(image)

    def _enhance_bw(self, image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        # Denoise first
        gray = cv2.fastNlMeansDenoising(gray, h=10)
        result = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 10
        )
        return cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)

    def _enhance_clean(self, image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        # Remove shadows
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
        bg = cv2.morphologyEx(gray, cv2.MORPH_DILATE, kernel)
        normalized = cv2.divide(gray, bg, scale=255)
        # Sharpen
        sharpened = cv2.GaussianBlur(normalized, (0, 0), 3)
        sharpened = cv2.addWeighted(normalized, 1.5, sharpened, -0.5, 0)
        # CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(sharpened)
        return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

    def _enhance_color(self, image: np.ndarray) -> np.ndarray:
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        result = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)
        # Sharpen
        blur = cv2.GaussianBlur(result, (0, 0), 3)
        result = cv2.addWeighted(result, 1.5, blur, -0.5, 0)
        return result

    # ─── High-level API ──────────────────────────────────────────

    def scan_with_corners(self, image: np.ndarray, corners: DocumentCorners,
                          enhance_mode: str = "auto") -> np.ndarray:
        """Сканирует с заданными углами (для ручной коррекции)"""
        pts = corners.as_array()
        warped = self.four_point_transform(image, pts)
        if enhance_mode != "none":
            warped = self.enhance_document(warped, enhance_mode)
        return warped

    def scan_auto(self, image: np.ndarray, enhance_mode: str = "auto") -> np.ndarray:
        """Автоматический скан: детект + трансформация + улучшение"""
        corners = self.detect_document(image)
        if corners:
            return self.scan_with_corners(image, corners, enhance_mode)
        warped = image.copy()
        if enhance_mode != "none":
            warped = self.enhance_document(warped, enhance_mode)
        return warped
