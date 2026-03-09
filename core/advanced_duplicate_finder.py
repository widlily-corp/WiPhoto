# core/advanced_duplicate_finder.py

import logging
import imagehash
from PIL import Image
from collections import defaultdict
from typing import List, Dict, Tuple
from models.image_model import ImageInfo
from core.settings_manager import settings

logger = logging.getLogger(__name__)


class AdvancedDuplicateFinder:
    """
    Продвинутый поиск дубликатов с несколькими алгоритмами
    и комбинированным подходом для повышения точности
    """

    METHODS = {
        "average": {
            "name": "Average Hash (быстрый)",
            "func": imagehash.average_hash,
            "description": "Быстрый, но менее точный. Хорош для точных копий."
        },
        "phash": {
            "name": "Perceptual Hash (рекомендуемый)",
            "func": imagehash.phash,
            "description": "Баланс между скоростью и точностью. Находит похожие фото."
        },
        "dhash": {
            "name": "Difference Hash",
            "func": imagehash.dhash,
            "description": "Устойчив к изменению яркости и контраста."
        },
        "whash": {
            "name": "Wavelet Hash (точный)",
            "func": imagehash.whash,
            "description": "Очень точный, но медленнее. Находит даже слабо похожие."
        },
        "colorhash": {
            "name": "Color Hash",
            "func": imagehash.colorhash,
            "description": "Сравнивает по цветовой палитре."
        }
    }

    def __init__(self):
        self.hash_cache = {}  # Кэш вычисленных хешей

    def calculate_hash(self, image_path: str, method: str = "phash", existing_hash: str = None) -> str:
        """
        Вычисляет хеш изображения выбранным методом

        ОПТИМИЗАЦИЯ: Использует уже вычисленный хеш если он передан
        """
        cache_key = f"{image_path}_{method}"

        # Проверяем кэш
        if cache_key in self.hash_cache:
            return self.hash_cache[cache_key]

        # ОПТИМИЗАЦИЯ: Используем уже вычисленный хеш если доступен
        # Для метода "average" (который используется в analyzer.py как phash)
        if existing_hash and method in ["phash", "average"]:
            self.hash_cache[cache_key] = existing_hash
            return existing_hash

        # Вычисляем новый хеш только если нужен другой метод
        try:
            with Image.open(image_path) as img:
                hash_func = self.METHODS[method]["func"]
                img_hash = str(hash_func(img))
                self.hash_cache[cache_key] = img_hash
                return img_hash
        except Exception as e:
            return None

    def find_duplicates_single_method(self,
                                      images: List[ImageInfo],
                                      method: str = "phash",
                                      threshold: int = 5) -> Dict[str, List[ImageInfo]]:
        """
        Находит дубликаты используя один метод

        Args:
            images: Список изображений
            method: Метод хеширования (average, phash, dhash, whash, colorhash)
            threshold: Порог различия (чем меньше - тем более похожими должны быть)

        Returns:
            Словарь {group_id: [ImageInfo, ...]}
        """
        groups = defaultdict(list)
        unassigned = list(images)
        group_counter = 0

        logger.info(f"Поиск дубликатов методом {method}, порог={threshold}")

        while unassigned:
            base_image = unassigned.pop(0)
            # ОПТИМИЗАЦИЯ: Передаем уже вычисленный хеш если доступен
            existing_hash = base_image.phash if hasattr(base_image, 'phash') else None
            base_hash = self.calculate_hash(base_image.path, method, existing_hash)

            if not base_hash:
                continue

            try:
                base_hash_int = int(base_hash, 16)
            except (ValueError, TypeError):
                continue

            current_group = [base_image]
            remaining = []

            for other_image in unassigned:
                # ОПТИМИЗАЦИЯ: Передаем уже вычисленный хеш если доступен
                other_existing_hash = other_image.phash if hasattr(other_image, 'phash') else None
                other_hash = self.calculate_hash(other_image.path, method, other_existing_hash)

                if not other_hash:
                    remaining.append(other_image)
                    continue

                try:
                    other_hash_int = int(other_hash, 16)
                    distance = bin(base_hash_int ^ other_hash_int).count('1')

                    if distance <= threshold:
                        current_group.append(other_image)
                    else:
                        remaining.append(other_image)
                except (ValueError, TypeError):
                    remaining.append(other_image)

            unassigned = remaining

            # Сохраняем только группы с дубликатами
            if len(current_group) > 1:
                group_id = f"group_{method}_{group_counter}"
                groups[group_id] = current_group
                group_counter += 1

        logger.info(f"Найдено групп: {len(groups)}")
        return dict(groups)

    def find_duplicates_combined(self,
                                 images: List[ImageInfo],
                                 methods: List[str] = ["phash", "dhash"],
                                 threshold: int = 5) -> Dict[str, List[ImageInfo]]:
        """
        Комбинированный поиск дубликатов с использованием нескольких методов
        Изображения считаются дубликатами, если похожи по ВСЕМ методам

        Args:
            images: Список изображений
            methods: Список методов для комбинирования
            threshold: Порог различия

        Returns:
            Словарь {group_id: [ImageInfo, ...]}
        """
        logger.info(f"Комбинированный поиск: {methods}, порог={threshold}")

        # Получаем результаты по каждому методу
        all_results = {}
        for method in methods:
            all_results[method] = self.find_duplicates_single_method(images, method, threshold)

        # Находим пересечения
        combined_groups = defaultdict(list)
        processed = set()
        group_counter = 0

        # Для каждой группы из первого метода
        first_method = methods[0]
        for group_id, group_images in all_results[first_method].items():
            group_paths = {img.path for img in group_images}

            # Проверяем, что эта группа подтверждается всеми другими методами
            is_valid = True
            for method in methods[1:]:
                # Ищем соответствующую группу в других методах
                found = False
                for other_group_images in all_results[method].values():
                    other_paths = {img.path for img in other_group_images}
                    # Если есть существенное пересечение (>80%)
                    overlap = len(group_paths & other_paths)
                    if overlap >= len(group_paths) * 0.8:
                        found = True
                        break

                if not found:
                    is_valid = False
                    break

            # Если группа подтверждена всеми методами
            if is_valid:
                for img in group_images:
                    if img.path not in processed:
                        combined_groups[f"combined_{group_counter}"].append(img)
                        processed.add(img.path)
                group_counter += 1

        logger.info(f"Комбинированный результат: {len(combined_groups)} групп")
        return combined_groups

    def rank_by_quality(self, group: List[ImageInfo]) -> List[ImageInfo]:
        """
        Ранжирует изображения в группе по качеству

        Критерии (в порядке важности):
        1. Резкость (если доступна)
        2. Размер файла
        3. Разрешение
        """

        def get_quality_score(img: ImageInfo) -> Tuple:
            sharpness = img.sharpness if hasattr(img, 'sharpness') and img.sharpness else 0
            file_size = img.file_size if hasattr(img, 'file_size') and img.file_size else 0
            resolution = (img.width * img.height) if hasattr(img, 'width') and img.width > 0 else 0

            # Fallback to disk if ImageInfo has no data
            if file_size == 0:
                try:
                    file_size = os.path.getsize(img.path)
                except OSError:
                    pass

            return (sharpness, file_size, resolution)

        return sorted(group, key=get_quality_score, reverse=True)

    def apply_groups_to_images(self,
                               groups: Dict[str, List[ImageInfo]],
                               mark_best: bool = True) -> List[ImageInfo]:
        """
        Применяет информацию о группах к объектам ImageInfo

        Args:
            groups: Словарь групп дубликатов
            mark_best: Помечать ли лучшее изображение в каждой группе

        Returns:
            Обновленный список всех изображений
        """
        all_images = []

        for group_id, group_images in groups.items():
            # Ранжируем по качеству
            if mark_best:
                ranked = self.rank_by_quality(group_images)
            else:
                ranked = group_images

            # Применяем метки
            for idx, img in enumerate(ranked):
                img.group_id = group_id
                img.is_best_in_group = (idx == 0) if mark_best else False
                all_images.append(img)

        return all_images

    def get_statistics(self, groups: Dict[str, List[ImageInfo]]) -> Dict:
        """Возвращает статистику по найденным дубликатам"""
        total_duplicates = sum(len(group) for group in groups.values())
        total_groups = len(groups)

        # Потенциальная экономия места
        potential_savings = 0
        for group_images in groups.values():
            if len(group_images) > 1:
                # Оставляем лучший, удаляем остальные
                import os
                sizes = []
                for img in group_images:
                    try:
                        sizes.append(os.path.getsize(img.path))
                    except OSError:
                        pass

                if sizes:
                    # Экономия = сумма всех минус самый большой файл
                    potential_savings += sum(sizes) - max(sizes)

        return {
            "total_groups": total_groups,
            "total_duplicates": total_duplicates,
            "potential_savings_mb": potential_savings / (1024 * 1024),
            "average_group_size": total_duplicates / total_groups if total_groups > 0 else 0
        }