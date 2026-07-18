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
