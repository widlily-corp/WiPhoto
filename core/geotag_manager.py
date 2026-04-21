# core/geotag_manager.py

import re
from dataclasses import dataclass
from typing import Optional
from core.metadata_reader import read_metadata


@dataclass
class GeoLocation:
    """Геолокация фотографии"""
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    location_name: Optional[str] = None


def parse_gps_coordinate(coord_str: str, ref: str) -> Optional[float]:
    """Парсит GPS координату из EXIF формата в десятичные градусы"""
    if not coord_str:
        return None

    try:
        # Формат: "55 deg 45' 21.12"" или "55.755333"
        if 'deg' in coord_str:
            parts = re.findall(r'(\d+\.?\d*)', coord_str)
            if len(parts) >= 2:
                degrees = float(parts[0])
                minutes = float(parts[1]) if len(parts) > 1 else 0
                seconds = float(parts[2]) if len(parts) > 2 else 0
                decimal = degrees + (minutes / 60) + (seconds / 3600)
            else:
                return None
        else:
            decimal = float(coord_str)

        # Применяем направление
        if ref in ['S', 'W']:
            decimal = -decimal

        return decimal
    except (ValueError, IndexError):
        return None


def get_geolocation(image_path: str) -> Optional[GeoLocation]:
    """Извлекает геолокацию из EXIF данных изображения"""
    metadata = read_metadata(image_path)
    if not metadata:
        return None

    # Ищем GPS данные
    gps_lat = metadata.get('GPS Latitude')
    gps_lat_ref = metadata.get('GPS Latitude Ref', 'N')
    gps_lon = metadata.get('GPS Longitude')
    gps_lon_ref = metadata.get('GPS Longitude Ref', 'E')
    gps_alt = metadata.get('GPS Altitude')

    if not gps_lat or not gps_lon:
        return None

    latitude = parse_gps_coordinate(gps_lat, gps_lat_ref)
    longitude = parse_gps_coordinate(gps_lon, gps_lon_ref)

    if latitude is None or longitude is None:
        return None

    altitude = None
    if gps_alt:
        try:
            altitude = float(re.findall(r'(\d+\.?\d*)', str(gps_alt))[0])
        except (ValueError, IndexError):
            pass

    return GeoLocation(
        latitude=latitude,
        longitude=longitude,
        altitude=altitude
    )
