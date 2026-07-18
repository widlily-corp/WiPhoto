use base64::{engine::general_purpose::STANDARD, Engine};
use image::imageops::FilterType;
use std::fs;
use std::path::Path;
use crate::models::image_info::RAW_EXTENSIONS;

const THUMBNAIL_SIZE: u32 = 256;

/// Generate or retrieve cached thumbnail as base64
#[tauri::command]
pub fn get_thumbnail(path: String) -> Result<String, String> {
    let file_path = Path::new(&path);
    if !file_path.exists() {
        return Err("File not found".into());
    }

    let cache_dir = dirs::home_dir()
        .unwrap_or_default()
        .join(".wiphoto")
        .join("cache")
        .join("thumbnails");
    let _ = fs::create_dir_all(&cache_dir);

    let hash = {
        use sha2::{Digest, Sha256};
        let mut hasher = Sha256::new();
        hasher.update(path.as_bytes());
        hex::encode(hasher.finalize())
    };
    let cache_file = cache_dir.join(format!("{}.jpg", hash));

    if cache_file.exists() {
        if let Ok(bytes) = fs::read(&cache_file) {
            return Ok(STANDARD.encode(&bytes));
        }
    }

    // Support RAW formats
    let ext = file_path.extension().map(|e| e.to_string_lossy().to_lowercase()).unwrap_or_default();
    let img = if RAW_EXTENSIONS.contains(&ext.as_str()) {
        if let Some(bytes) = super::raw_utils::extract_embedded_jpeg(file_path) {
            image::load_from_memory(&bytes).map_err(|e| format!("Failed to decode embedded RAW JPEG: {}", e))?
        } else {
            return Err("Failed to extract preview from RAW file".into());
        }
    } else {
        image::open(file_path).map_err(|e| format!("Failed to open image: {}", e))?
    };

    // Resize using fast Triangle filter
    let thumb = img.resize(THUMBNAIL_SIZE, THUMBNAIL_SIZE, FilterType::Triangle);

    let _ = thumb.save_with_format(&cache_file, image::ImageFormat::Jpeg);

    let mut buf = Vec::new();
    let mut cursor = std::io::Cursor::new(&mut buf);
    thumb
        .write_to(&mut cursor, image::ImageFormat::Jpeg)
        .map_err(|e| format!("Failed to encode: {}", e))?;
    Ok(STANDARD.encode(&buf))
}

/// Load full-resolution image as base64 (for preview/editor)
#[tauri::command]
pub fn load_full_image(path: String, max_size: Option<u32>) -> Result<String, String> {
    let file_path = Path::new(&path);
    if !file_path.exists() {
        return Err("File not found".into());
    }

    // Support RAW formats
    let ext = file_path.extension().map(|e| e.to_string_lossy().to_lowercase()).unwrap_or_default();
    let img = if RAW_EXTENSIONS.contains(&ext.as_str()) {
        if let Some(bytes) = super::raw_utils::extract_embedded_jpeg(file_path) {
            image::load_from_memory(&bytes).map_err(|e| format!("Failed to decode embedded RAW JPEG: {}", e))?
        } else {
            return Err("Failed to extract preview from RAW file".into());
        }
    } else {
        image::open(file_path).map_err(|e| format!("Failed to open: {}", e))?
    };

    let img = if let Some(max) = max_size {
        let (w, h) = image::GenericImageView::dimensions(&img);
        if w > max || h > max {
            img.resize(max, max, FilterType::Triangle)
        } else {
            img
        }
    } else {
        img
    };

    let mut buf = Vec::new();
    let mut cursor = std::io::Cursor::new(&mut buf);
    img.write_to(&mut cursor, image::ImageFormat::Jpeg)
        .map_err(|e| format!("Failed to encode: {}", e))?;
    Ok(STANDARD.encode(&buf))
}

/// Clear thumbnail cache
#[tauri::command]
pub fn clear_thumbnail_cache() -> Result<u32, String> {
    let cache_dir = dirs::home_dir()
        .unwrap_or_default()
        .join(".wiphoto")
        .join("cache")
        .join("thumbnails");

    let mut count = 0u32;
    if cache_dir.exists() {
        if let Ok(entries) = fs::read_dir(&cache_dir) {
            for entry in entries.flatten() {
                if entry.path().extension().is_some_and(|e| e == "jpg") {
                    let _ = fs::remove_file(entry.path());
                    count += 1;
                }
            }
        }
    }
    Ok(count)
}

/// Auto-prune thumbnail cache files older than 30 days
pub fn auto_prune_thumbnail_cache() -> Result<u32, String> {
    let cache_dir = dirs::home_dir()
        .unwrap_or_default()
        .join(".wiphoto")
        .join("cache")
        .join("thumbnails");
    if !cache_dir.exists() {
        return Ok(0);
    }

    let mut count = 0u32;
    let now = std::time::SystemTime::now();
    let max_age = std::time::Duration::from_secs(30 * 24 * 60 * 60); // 30 days

    if let Ok(entries) = fs::read_dir(&cache_dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().is_some_and(|e| e == "jpg") {
                let mut should_delete = false;
                if let Ok(metadata) = fs::metadata(&path) {
                    if let Ok(modified) = metadata.modified() {
                        if let Ok(age) = now.duration_since(modified) {
                            if age > max_age {
                                should_delete = true;
                            }
                        }
                    }
                }
                if should_delete {
                    let _ = fs::remove_file(path);
                    count += 1;
                }
            }
        }
    }
    Ok(count)
}
