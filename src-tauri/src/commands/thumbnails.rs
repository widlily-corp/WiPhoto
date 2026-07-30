use crate::models::image_info::RAW_EXTENSIONS;
use image::imageops::FilterType;
use std::fs;
use std::path::Path;

const THUMBNAIL_SIZE: u32 = 256;

/// Retrieve cached thumbnail file path (Zero-Copy)
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
        return Ok(cache_file.to_string_lossy().to_string());
    }

    // Support RAW formats
    let ext = file_path
        .extension()
        .map(|e| e.to_string_lossy().to_lowercase())
        .unwrap_or_default();
    let img = if RAW_EXTENSIONS.contains(&ext.as_str()) {
        if let Some(bytes) = super::raw_utils::extract_embedded_jpeg(file_path) {
            image::load_from_memory(&bytes)
                .map_err(|e| format!("Failed to decode embedded RAW JPEG: {}", e))?
        } else {
            return Err("Failed to extract preview from RAW file".into());
        }
    } else {
        image::open(file_path).map_err(|e| format!("Failed to open image: {}", e))?
    };

    // Resize using fast Triangle filter
    let thumb = img.resize(THUMBNAIL_SIZE, THUMBNAIL_SIZE, FilterType::Triangle);

    thumb
        .save_with_format(&cache_file, image::ImageFormat::Jpeg)
        .map_err(|e| format!("Failed to save thumbnail: {}", e))?;

    Ok(cache_file.to_string_lossy().to_string())
}

/// Load full-resolution image file path (Zero-Copy, with preview cache for RAW/resized)
#[tauri::command]
pub fn load_full_image(path: String, max_size: Option<u32>) -> Result<String, String> {
    let file_path = Path::new(&path);
    if !file_path.exists() {
        return Err("File not found".into());
    }

    let ext = file_path
        .extension()
        .map(|e| e.to_string_lossy().to_lowercase())
        .unwrap_or_default();

    let is_raw = RAW_EXTENSIONS.contains(&ext.as_str());

    // If standard image and no max_size resize requested, return original file path directly
    if !is_raw && max_size.is_none() {
        return Ok(path);
    }

    let cache_dir = dirs::home_dir()
        .unwrap_or_default()
        .join(".wiphoto")
        .join("cache")
        .join("previews");
    let _ = fs::create_dir_all(&cache_dir);

    let hash = {
        use sha2::{Digest, Sha256};
        let mut hasher = Sha256::new();
        hasher.update(path.as_bytes());
        if let Some(max) = max_size {
            hasher.update(max.to_string().as_bytes());
        }
        hex::encode(hasher.finalize())
    };
    let preview_file = cache_dir.join(format!("{}.jpg", hash));

    if preview_file.exists() {
        return Ok(preview_file.to_string_lossy().to_string());
    }

    // Support RAW formats and resizing
    let img = if is_raw {
        if let Some(bytes) = super::raw_utils::extract_embedded_jpeg(file_path) {
            image::load_from_memory(&bytes)
                .map_err(|e| format!("Failed to decode embedded RAW JPEG: {}", e))?
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

    img.save_with_format(&preview_file, image::ImageFormat::Jpeg)
        .map_err(|e| format!("Failed to save preview: {}", e))?;

    Ok(preview_file.to_string_lossy().to_string())
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
