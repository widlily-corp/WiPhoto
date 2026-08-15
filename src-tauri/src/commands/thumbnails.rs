use crate::models::image_info::{RAW_EXTENSIONS, VIDEO_EXTENSIONS};
use image::imageops::FilterType;
use once_cell::sync::Lazy;
use parking_lot::RwLock;
use std::collections::HashMap;
use std::fs;
use std::path::Path;

const THUMBNAIL_SIZE: u32 = 256;

static THUMBNAIL_PATH_CACHE: Lazy<RwLock<HashMap<String, String>>> =
    Lazy::new(|| RwLock::new(HashMap::new()));

/// Helper: Store thumbnail mapping in memory cache
pub fn update_in_memory_thumbnail_cache(path: String, thumb_path: String) {
    THUMBNAIL_PATH_CACHE.write().insert(path, thumb_path);
}

/// Helper: Lookup thumbnail path from memory cache
pub fn get_cached_thumbnail_path(path: &str) -> Option<String> {
    let cache_read = THUMBNAIL_PATH_CACHE.read();
    if let Some(cached_file) = cache_read.get(path) {
        if Path::new(cached_file).exists() {
            return Some(cached_file.clone());
        }
    }
    None
}

/// Helper: Get cached thumbnail path or generate thumbnail synchronously on disk
pub fn get_or_generate_thumbnail_sync(path: &str) -> Result<String, String> {
    let file_path = Path::new(path);
    if !file_path.exists() {
        return Err("File not found".into());
    }

    if let Some(cached_file) = get_cached_thumbnail_path(path) {
        return Ok(cached_file);
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
    let cache_file_str = cache_file.to_string_lossy().to_string();

    if cache_file.exists() {
        THUMBNAIL_PATH_CACHE
            .write()
            .insert(path.to_string(), cache_file_str.clone());
        return Ok(cache_file_str);
    }

    let ext = file_path
        .extension()
        .map(|e| e.to_string_lossy().to_lowercase())
        .unwrap_or_default();

    if VIDEO_EXTENSIONS.contains(&ext.as_str()) {
        let mut img = image::RgbaImage::new(THUMBNAIL_SIZE, THUMBNAIL_SIZE);
        for pixel in img.pixels_mut() {
            *pixel = image::Rgba([40, 44, 58, 255]);
        }
        let cx = THUMBNAIL_SIZE as f32 / 2.0;
        let cy = THUMBNAIL_SIZE as f32 / 2.0;
        let size = 40.0f32;
        for y in 0..THUMBNAIL_SIZE {
            for x in 0..THUMBNAIL_SIZE {
                let fx = x as f32 - cx + size * 0.3;
                let fy = y as f32 - cy;
                if fx >= -size * 0.5 && fx <= size * 0.5 {
                    let max_y = size * 0.5 * (1.0 - fx / (size * 0.5));
                    if fy.abs() <= max_y {
                        img.put_pixel(x, y, image::Rgba([200, 200, 200, 220]));
                    }
                }
            }
        }
        let _ = image::DynamicImage::ImageRgba8(img)
            .save_with_format(&cache_file, image::ImageFormat::Jpeg);
        THUMBNAIL_PATH_CACHE
            .write()
            .insert(path.to_string(), cache_file_str.clone());
        return Ok(cache_file_str);
    }

    let img = if ext == "jxl" {
        crate::commands::export::load_jxl(file_path)
            .ok_or_else(|| "Failed to decode JXL image".to_string())?
    } else if RAW_EXTENSIONS.contains(&ext.as_str()) {
        if let Some(bytes) = super::raw_utils::extract_embedded_jpeg(file_path) {
            image::load_from_memory(&bytes)
                .map_err(|e| format!("Failed to decode embedded RAW JPEG: {}", e))?
        } else {
            return Err("Failed to extract preview from RAW file".into());
        }
    } else {
        image::open(file_path).map_err(|e| format!("Failed to open image: {}", e))?
    };

    let thumb = img.resize(THUMBNAIL_SIZE, THUMBNAIL_SIZE, FilterType::Triangle);

    thumb
        .save_with_format(&cache_file, image::ImageFormat::Jpeg)
        .map_err(|e| format!("Failed to save thumbnail: {}", e))?;

    THUMBNAIL_PATH_CACHE
        .write()
        .insert(path.to_string(), cache_file_str.clone());
    Ok(cache_file_str)
}

/// Retrieve cached thumbnail file path (Zero-Copy)
#[tauri::command]
pub async fn get_thumbnail(path: String) -> Result<String, String> {
    if let Some(cached_file) = get_cached_thumbnail_path(&path) {
        return Ok(cached_file);
    }
    let path_clone = path.clone();
    tauri::async_runtime::spawn_blocking(move || get_or_generate_thumbnail_sync(&path_clone))
        .await
        .map_err(|e| format!("Task join error: {}", e))?
}

/// Load full-resolution image file path (Zero-Copy, with preview cache for RAW/resized)
#[tauri::command]
pub async fn load_full_image(path: String, max_size: Option<u32>) -> Result<String, String> {
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
    if !is_raw && max_size.is_none() && ext != "jxl" {
        return Ok(path);
    }

    let path_clone = path.clone();
    tauri::async_runtime::spawn_blocking(move || {
        let cache_dir = dirs::home_dir()
            .unwrap_or_default()
            .join(".wiphoto")
            .join("cache")
            .join("previews");
        let _ = fs::create_dir_all(&cache_dir);

        let hash = {
            use sha2::{Digest, Sha256};
            let mut hasher = Sha256::new();
            hasher.update(path_clone.as_bytes());
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
        let img = if ext == "jxl" {
            crate::commands::export::load_jxl(Path::new(&path_clone))
                .ok_or_else(|| "Failed to decode JXL image".to_string())?
        } else if is_raw {
            if let Some(bytes) = super::raw_utils::extract_embedded_jpeg(Path::new(&path_clone)) {
                image::load_from_memory(&bytes)
                    .map_err(|e| format!("Failed to decode embedded RAW JPEG: {}", e))?
            } else {
                return Err("Failed to extract preview from RAW file".into());
            }
        } else {
            image::open(Path::new(&path_clone)).map_err(|e| format!("Failed to open: {}", e))?
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
    })
    .await
    .map_err(|e| format!("Task join error: {}", e))?
}

/// Clear thumbnail cache
#[tauri::command]
pub fn clear_thumbnail_cache() -> Result<u32, String> {
    THUMBNAIL_PATH_CACHE.write().clear();

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

/// Get asset protocol URL for zero-copy rendering (PROJECT.md contract)
#[tauri::command]
pub fn get_image_url(path: String) -> String {
    format!("asset://localhost/{}", path)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_get_image_url() {
        let url = get_image_url("C:/photos/test.jpg".into());
        assert_eq!(url, "asset://localhost/C:/photos/test.jpg");
    }
}
