use crate::models::image_info::ExifEntry;
use std::fs;
use std::path::Path;

/// Read EXIF metadata from an image file
#[tauri::command]
pub fn read_exif(path: String) -> Result<Vec<ExifEntry>, String> {
    let file_path = Path::new(&path);
    if !file_path.exists() {
        return Err("File not found".into());
    }

    let mut entries = Vec::new();

    // File info
    if let Ok(meta) = fs::metadata(file_path) {
        entries.push(ExifEntry {
            key: "Размер файла".into(),
            value: format_file_size(meta.len()),
        });
    }

    entries.push(ExifEntry {
        key: "Имя файла".into(),
        value: file_path
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .to_string(),
    });

    entries.push(ExifEntry {
        key: "Формат".into(),
        value: file_path
            .extension()
            .unwrap_or_default()
            .to_string_lossy()
            .to_uppercase(),
    });

    // Try to read EXIF
    if let Ok(file) = fs::File::open(file_path) {
        let mut bufreader = std::io::BufReader::new(file);
        let exif_reader = exif::Reader::new();
        if let Ok(exif_data) = exif_reader.read_from_container(&mut bufreader) {
            // Common EXIF fields
            let fields = [
                (exif::Tag::Make, "Производитель"),
                (exif::Tag::Model, "Камера"),
                (exif::Tag::LensModel, "Объектив"),
                (exif::Tag::DateTimeOriginal, "Дата съёмки"),
                (exif::Tag::ExposureTime, "Выдержка"),
                (exif::Tag::FNumber, "Диафрагма"),
                (exif::Tag::PhotographicSensitivity, "ISO"),
                (exif::Tag::FocalLength, "Фокусное расстояние"),
                (exif::Tag::FocalLengthIn35mmFilm, "Фокус. расст. (35мм)"),
                (exif::Tag::ExposureBiasValue, "Экспокоррекция"),
                (exif::Tag::MeteringMode, "Режим замера"),
                (exif::Tag::Flash, "Вспышка"),
                (exif::Tag::WhiteBalance, "Баланс белого"),
                (exif::Tag::ExposureProgram, "Программа экспозиции"),
                (exif::Tag::PixelXDimension, "Ширина"),
                (exif::Tag::PixelYDimension, "Высота"),
                (exif::Tag::ColorSpace, "Цветовое пространство"),
                (exif::Tag::Software, "ПО"),
                (exif::Tag::Artist, "Автор"),
                (exif::Tag::Copyright, "Авторские права"),
                (exif::Tag::ImageDescription, "Описание"),
            ];

            for (tag, label) in &fields {
                if let Some(field) = exif_data.get_field(*tag, exif::In::PRIMARY) {
                    let val = field.display_value().to_string();
                    let val = val.trim_matches('"').to_string();
                    if !val.is_empty() {
                        entries.push(ExifEntry {
                            key: label.to_string(),
                            value: val,
                        });
                    }
                }
            }

            // GPS coordinates
            if let (Some(lat_field), Some(lat_ref), Some(lon_field), Some(lon_ref)) = (
                exif_data.get_field(exif::Tag::GPSLatitude, exif::In::PRIMARY),
                exif_data.get_field(exif::Tag::GPSLatitudeRef, exif::In::PRIMARY),
                exif_data.get_field(exif::Tag::GPSLongitude, exif::In::PRIMARY),
                exif_data.get_field(exif::Tag::GPSLongitudeRef, exif::In::PRIMARY),
            ) {
                entries.push(ExifEntry {
                    key: "GPS".into(),
                    value: format!(
                        "{} {} / {} {}",
                        lat_field.display_value(),
                        lat_ref.display_value(),
                        lon_field.display_value(),
                        lon_ref.display_value()
                    ),
                });
            }

            if let Some(alt) = exif_data.get_field(exif::Tag::GPSAltitude, exif::In::PRIMARY) {
                entries.push(ExifEntry {
                    key: "Высота GPS".into(),
                    value: format!("{} м", alt.display_value()),
                });
            }
        }
    }

    // Try to get image dimensions if EXIF didn't have them (use fast header-only parsing)
    if !entries.iter().any(|e| e.key == "Ширина") {
        let mut dimensions = None;
        let ext = file_path
            .extension()
            .map(|e| e.to_string_lossy().to_lowercase())
            .unwrap_or_default();

        use crate::models::image_info::RAW_EXTENSIONS;
        if RAW_EXTENSIONS.contains(&ext.as_str()) {
            if let Some(bytes) = super::raw_utils::extract_embedded_jpeg(file_path) {
                let cursor = std::io::Cursor::new(bytes);
                if let Ok(reader) = image::ImageReader::new(cursor).with_guessed_format() {
                    if let Ok(dims) = reader.into_dimensions() {
                        dimensions = Some(dims);
                    }
                }
            }
        } else {
            if let Ok(reader) = image::ImageReader::open(file_path) {
                if let Ok(dims) = reader.into_dimensions() {
                    dimensions = Some(dims);
                }
            }
        }

        if let Some((w, h)) = dimensions {
            entries.push(ExifEntry {
                key: "Ширина".into(),
                value: w.to_string(),
            });
            entries.push(ExifEntry {
                key: "Высота".into(),
                value: h.to_string(),
            });
        }
    }

    Ok(entries)
}

fn format_file_size(size: u64) -> String {
    const UNITS: &[&str] = &["B", "KB", "MB", "GB", "TB"];
    let mut s = size as f64;
    for unit in UNITS {
        if s < 1024.0 {
            return format!("{:.1} {}", s, unit);
        }
        s /= 1024.0;
    }
    format!("{:.1} PB", s)
}

/// Update photo metadata (rating, color label, flag status, tags) and sync to XMP sidecar
#[tauri::command]
pub fn update_photo_metadata(
    path: String,
    rating: Option<u8>,
    color_label: Option<String>,
    flag_status: Option<String>,
    tags: Option<Vec<String>>,
) -> Result<(), String> {
    let mut current_rating = 0;
    let mut current_label = String::new();
    let mut current_flag = String::new();
    let mut current_tags = Vec::new();

    if let Ok(Some(existing)) = crate::commands::xmp::read_xmp_sidecar(path.clone()) {
        current_rating = existing.rating;
        current_label = existing.color_label;
        current_flag = existing.flag_status;
        current_tags = existing.tags;
    }

    if let Some(r) = rating {
        current_rating = r;
    }
    if let Some(l) = color_label {
        current_label = l;
    }
    if let Some(f) = flag_status {
        current_flag = f;
    }
    if let Some(t) = tags {
        current_tags = t;
    }

    crate::commands::xmp::write_xmp_sidecar(
        path,
        current_rating,
        current_label,
        current_flag,
        current_tags,
        None,
    )
}

use serde::{Deserialize, Serialize};

/// Geotagged photo structure for map spatial clustering
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GeoPhoto {
    pub id: String,
    pub path: String,
    pub filename: String,
    pub latitude: f64,
    pub longitude: f64,
    pub thumbnail: String,
    pub rating: u8,
}

/// Retrieve all geotagged photos from database
#[tauri::command]
pub fn get_geotagged_photos() -> Result<Vec<GeoPhoto>, String> {
    let images = crate::db::get_images_by_paths(&[]).map_err(|e| e.to_string())?;
    let geo_photos = images
        .into_iter()
        .filter_map(|img| {
            if let Some((lat, lon)) = img.gps_location {
                Some(GeoPhoto {
                    id: img.path.clone(),
                    path: img.path,
                    filename: img.filename,
                    latitude: lat,
                    longitude: lon,
                    thumbnail: img.thumbnail,
                    rating: img.rating,
                })
            } else {
                None
            }
        })
        .collect();
    Ok(geo_photos)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::image_info::ImageInfo;

    #[test]
    fn test_format_file_size() {
        // Arrange & Act & Assert
        assert_eq!(format_file_size(500), "500.0 B");
        assert_eq!(format_file_size(2048), "2.0 KB");
        assert_eq!(format_file_size(1048576), "1.0 MB");
    }

    #[test]
    fn test_get_geotagged_photos_conversion() {
        // Arrange
        let mut info = ImageInfo::new("C:/photos/eiffel.jpg");
        info.gps_location = Some((48.8584, 2.2945));
        info.rating = 5;

        // Act
        let geo = if let Some((lat, lon)) = info.gps_location {
            Some(GeoPhoto {
                id: info.path.clone(),
                path: info.path,
                filename: info.filename,
                latitude: lat,
                longitude: lon,
                thumbnail: info.thumbnail,
                rating: info.rating,
            })
        } else {
            None
        };

        // Assert
        assert!(geo.is_some());
        let g = geo.unwrap();
        assert_eq!(g.latitude, 48.8584);
        assert_eq!(g.longitude, 2.2945);
        assert_eq!(g.filename, "eiffel.jpg");
        assert_eq!(g.rating, 5);
    }
}
