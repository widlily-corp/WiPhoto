use crate::models::image_info::{self, ImageInfo, RAW_EXTENSIONS, VIDEO_EXTENSIONS};
use image::imageops::FilterType;
use rayon::prelude::*;
use std::fs;
use std::path::{Path, PathBuf};
use tauri::{AppHandle, Emitter};

const THUMBNAIL_SIZE: u32 = 256;

/// Collect all supported files from a directory
fn collect_files(root: &str, recursive: bool) -> Vec<PathBuf> {
    let root_path = Path::new(root);
    let mut files = Vec::new();

    if recursive {
        for entry in walkdir::WalkDir::new(root_path)
            .follow_links(false)
            .into_iter()
            .filter_map(|e| e.ok())
        {
            if entry.file_type().is_file() {
                if let Some(ext) = entry.path().extension() {
                    let ext_str = ext.to_string_lossy().to_lowercase();
                    if image_info::is_supported_extension(&ext_str) {
                        files.push(entry.path().to_path_buf());
                    }
                }
            }
        }
    } else {
        if let Ok(entries) = fs::read_dir(root_path) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.is_file() {
                    if let Some(ext) = path.extension() {
                        let ext_str = ext.to_string_lossy().to_lowercase();
                        if image_info::is_supported_extension(&ext_str) {
                            files.push(path);
                        }
                    }
                }
            }
        }
    }

    files
}

/// Generate a thumbnail file path (Zero-Copy)
fn generate_thumbnail(path: &Path, cache_dir: &Path) -> Option<String> {
    let path_str = path.to_string_lossy().to_string();
    if let Some(cached) = super::thumbnails::get_cached_thumbnail_path(&path_str) {
        return Some(cached);
    }

    // Create cache key from path hash
    let hash = sha2_hash(&path_str);
    let cache_file = cache_dir.join(format!("{}.jpg", hash));

    // Check disk cache first
    if cache_file.exists() {
        let cache_file_str = cache_file.to_string_lossy().to_string();
        super::thumbnails::update_in_memory_thumbnail_cache(path_str, cache_file_str.clone());
        return Some(cache_file_str);
    }

    let ext = path.extension()?.to_string_lossy().to_lowercase();

    // For videos, generate a placeholder thumbnail
    if VIDEO_EXTENSIONS.contains(&ext.as_str()) {
        let res = generate_video_placeholder(path, cache_dir, &hash);
        if let Some(ref thumb_path) = res {
            super::thumbnails::update_in_memory_thumbnail_cache(path_str, thumb_path.clone());
        }
        return res;
    }

    // Try to load the image
    let img = if RAW_EXTENSIONS.contains(&ext.as_str()) {
        // For RAW files, try to extract embedded JPEG preview
        match load_raw_thumbnail(path) {
            Some(i) => i,
            None => {
                log::warn!("Failed to load RAW thumbnail preview for: {:?}", path);
                return None;
            }
        }
    } else {
        match image::open(path) {
            Ok(i) => i,
            Err(e) => {
                log::warn!("Failed to open image {:?}: {}", path, e);
                return None;
            }
        }
    };

    // Create thumbnail using Triangle filter (much faster than Lanczos3, negligible difference for 256px thumbs)
    let thumb = img.resize(THUMBNAIL_SIZE, THUMBNAIL_SIZE, FilterType::Triangle);

    // Save to cache
    let _ = fs::create_dir_all(cache_dir);
    let _ = thumb.save_with_format(&cache_file, image::ImageFormat::Jpeg);

    let cache_file_str = cache_file.to_string_lossy().to_string();
    super::thumbnails::update_in_memory_thumbnail_cache(path_str, cache_file_str.clone());
    Some(cache_file_str)
}

/// Try to load RAW thumbnail from embedded JPEG
fn load_raw_thumbnail(path: &Path) -> Option<image::DynamicImage> {
    // 1. Try kamadak-exif to find embedded thumbnail (fast)
    if let Ok(file) = std::fs::File::open(path) {
        let mut bufreader = std::io::BufReader::new(&file);
        let exif_reader = exif::Reader::new();
        if let Ok(exif) = exif_reader.read_from_container(&mut bufreader) {
            if let Some(thumb_offset) =
                exif.get_field(exif::Tag::JPEGInterchangeFormat, exif::In::THUMBNAIL)
            {
                if let Some(thumb_length) =
                    exif.get_field(exif::Tag::JPEGInterchangeFormatLength, exif::In::THUMBNAIL)
                {
                    if let (Some(offset), Some(length)) = (
                        thumb_offset.value.get_uint(0),
                        thumb_length.value.get_uint(0),
                    ) {
                        use std::io::{Read, Seek, SeekFrom};
                        if let Ok(mut file2) = std::fs::File::open(path) {
                            if file2.seek(SeekFrom::Start(offset as u64)).is_ok() {
                                let mut buf = vec![0u8; length as usize];
                                if file2.read_exact(&mut buf).is_ok() {
                                    if let Ok(img) = image::load_from_memory(&buf) {
                                        return Some(img);
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // 2. Try raw_utils binary search (extremely robust for all CR3, NEF, ARW, DNG, etc.)
    if let Some(bytes) = super::raw_utils::extract_embedded_jpeg(path) {
        if let Ok(img) = image::load_from_memory(&bytes) {
            return Some(img);
        }
    }

    // Fallback: try to open with image crate directly (unlikely to work for RAW, but good for normal files)
    image::open(path).ok()
}

fn generate_video_placeholder(_path: &Path, cache_dir: &Path, hash: &str) -> Option<String> {
    let cache_file = cache_dir.join(format!("vid_{}.jpg", hash));
    if cache_file.exists() {
        return Some(cache_file.to_string_lossy().to_string());
    }

    // Create a simple dark thumbnail with play icon for videos
    let mut img = image::RgbaImage::new(THUMBNAIL_SIZE, THUMBNAIL_SIZE);
    // Fill with dark grey
    for pixel in img.pixels_mut() {
        *pixel = image::Rgba([40, 44, 58, 255]);
    }
    // Draw a simple play triangle
    let cx = THUMBNAIL_SIZE as f32 / 2.0;
    let cy = THUMBNAIL_SIZE as f32 / 2.0;
    let size = 40.0f32;
    for y in 0..THUMBNAIL_SIZE {
        for x in 0..THUMBNAIL_SIZE {
            let fx = x as f32 - cx + size * 0.3;
            let fy = y as f32 - cy;
            // Triangle: left edge at -size/2, right edge at size/2
            if fx >= -size * 0.5 && fx <= size * 0.5 {
                let max_y = size * 0.5 * (1.0 - fx / (size * 0.5));
                if fy.abs() <= max_y {
                    img.put_pixel(x, y, image::Rgba([200, 200, 200, 220]));
                }
            }
        }
    }
    let _ = fs::create_dir_all(cache_dir);
    let _ = image::DynamicImage::ImageRgba8(img)
        .save_with_format(&cache_file, image::ImageFormat::Jpeg);
    Some(cache_file.to_string_lossy().to_string())
}

fn sha2_hash(input: &str) -> String {
    use sha2::{Digest, Sha256};
    let mut hasher = Sha256::new();
    hasher.update(input.as_bytes());
    hex::encode(hasher.finalize())
}

/// Process a single image file into ImageInfo
fn process_single_file(path: &Path, cache_dir: &Path) -> Option<ImageInfo> {
    let mut info = ImageInfo::new(&path.to_string_lossy());

    // Get file metadata
    if let Ok(meta) = fs::metadata(path) {
        info.file_size = meta.len();
    }

    // Try to read EXIF metadata first (fast)
    let mut exif_width = None;
    let mut exif_height = None;

    if let Ok(file) = fs::File::open(path) {
        let mut bufreader = std::io::BufReader::new(file);
        let exif_reader = exif::Reader::new();
        if let Ok(exif_data) = exif_reader.read_from_container(&mut bufreader) {
            // Camera model
            if let Some(field) = exif_data.get_field(exif::Tag::Model, exif::In::PRIMARY) {
                info.camera_model = field
                    .display_value()
                    .to_string()
                    .trim_matches('"')
                    .to_string();
            }
            // Date taken
            if let Some(field) = exif_data.get_field(exif::Tag::DateTimeOriginal, exif::In::PRIMARY)
            {
                info.date_taken = field
                    .display_value()
                    .to_string()
                    .trim_matches('"')
                    .to_string();
            }
            // GPS
            if let (Some(lat_field), Some(lat_ref), Some(lon_field), Some(lon_ref)) = (
                exif_data.get_field(exif::Tag::GPSLatitude, exif::In::PRIMARY),
                exif_data.get_field(exif::Tag::GPSLatitudeRef, exif::In::PRIMARY),
                exif_data.get_field(exif::Tag::GPSLongitude, exif::In::PRIMARY),
                exif_data.get_field(exif::Tag::GPSLongitudeRef, exif::In::PRIMARY),
            ) {
                if let (Some(lat), Some(lon)) = (
                    parse_gps_coordinate(&lat_field.value, &lat_ref.display_value().to_string()),
                    parse_gps_coordinate(&lon_field.value, &lon_ref.display_value().to_string()),
                ) {
                    info.gps_location = Some((lat, lon));
                }
            }
            // Try to extract dimensions from EXIF (critical for RAW images that standard readers can't parse)
            if let Some(w_field) = exif_data
                .get_field(exif::Tag::ImageWidth, exif::In::PRIMARY)
                .or_else(|| exif_data.get_field(exif::Tag::PixelXDimension, exif::In::PRIMARY))
            {
                exif_width = w_field.value.get_uint(0);
            }
            if let Some(h_field) = exif_data
                .get_field(exif::Tag::ImageLength, exif::In::PRIMARY)
                .or_else(|| exif_data.get_field(exif::Tag::PixelYDimension, exif::In::PRIMARY))
            {
                exif_height = h_field.value.get_uint(0);
            }
        }
    }

    // Set dimensions
    if !info.is_video {
        if let (Some(w), Some(h)) = (exif_width, exif_height) {
            info.width = w;
            info.height = h;
            if h > 0 {
                info.aspect_ratio = w as f64 / h as f64;
            }
        } else {
            // Fast dimension reading from image headers (without decoding raw pixels)
            if let Ok(reader) = image::ImageReader::open(path) {
                if let Ok((w, h)) = reader.into_dimensions() {
                    info.width = w;
                    info.height = h;
                    if h > 0 {
                        info.aspect_ratio = w as f64 / h as f64;
                    }
                }
            }
        }
    }

    // Generate thumbnail (fallback to empty string instead of failing the scan)
    info.thumbnail = generate_thumbnail(path, cache_dir).unwrap_or_default();

    // Read XMP sidecar if exists
    let xmp_path = path.with_extension("xmp");
    if xmp_path.exists() {
        if let Ok(content) = fs::read_to_string(&xmp_path) {
            if let Some(xmp) = super::xmp::parse_xmp_content(&content) {
                info.rating = xmp.rating;
                info.color_label = xmp.color_label;
                info.flag_status = xmp.flag_status;
                info.tags = xmp.tags;
            }
        }
    }

    Some(info)
}

fn parse_gps_coordinate(value: &exif::Value, reference: &str) -> Option<f64> {
    match value {
        exif::Value::Rational(rats) if rats.len() >= 3 => {
            let deg = rats[0].to_f64();
            let min = rats[1].to_f64();
            let sec = rats[2].to_f64();
            if !deg.is_finite() || !min.is_finite() || !sec.is_finite() {
                return None;
            }
            let mut coord = deg + min / 60.0 + sec / 3600.0;
            if !coord.is_finite() {
                return None;
            }
            let ref_str = reference.trim_matches('"').trim();
            if ref_str == "S" || ref_str == "W" {
                coord = -coord;
            }
            Some(coord)
        }
        _ => None,
    }
}

fn is_direct_child(folder: &Path, file_path: &Path) -> bool {
    let parent = match file_path.parent() {
        Some(p) => p,
        None => return false,
    };
    let parent_str = parent
        .to_string_lossy()
        .replace('\\', "/")
        .trim_end_matches('/')
        .to_string();
    let folder_str = folder
        .to_string_lossy()
        .replace('\\', "/")
        .trim_end_matches('/')
        .to_string();
    parent_str.eq_ignore_ascii_case(&folder_str)
}

fn enqueue_background_onnx_tasks(files: Vec<PathBuf>) {
    if files.is_empty() {
        return;
    }
    tauri::async_runtime::spawn(async move {
        let _ = tauri::async_runtime::spawn_blocking(move || {
            let model_init = crate::onnx::init_model().is_ok();
            for file_path in files {
                let ext = file_path
                    .extension()
                    .map(|e| e.to_string_lossy().to_lowercase())
                    .unwrap_or_default();
                if VIDEO_EXTENSIONS.contains(&ext.as_str()) {
                    continue;
                }
                let path_str = file_path.to_string_lossy().to_string();
                if model_init {
                    if let Some(analysis) = crate::onnx::analyze_image(&file_path) {
                        if let Ok(mut infos) =
                            crate::db::get_images_by_paths(std::slice::from_ref(&path_str))
                        {
                            if let Some(info) = infos.first_mut() {
                                info.faces_count = analysis.faces_count;
                                info.animals_count = analysis.animals_count;
                                info.animal_species = analysis.animal_species;
                                for tag in analysis.tags {
                                    if !info.tags.contains(&tag) {
                                        info.tags.push(tag);
                                    }
                                }
                                let _ = crate::db::save_images_batch(&[(
                                    info,
                                    get_modified_time(&file_path),
                                )]);
                            }
                        }
                    }
                }
                // Extract 512-dim vector embedding and save to SQLite
                let embedding = crate::onnx::extract_image_embedding(&file_path);
                let _ = crate::db::save_image_embedding(&path_str, &embedding);
            }
        })
        .await;
    });
}

fn get_modified_time(path: &Path) -> u64 {
    fs::metadata(path)
        .and_then(|m| m.modified())
        .and_then(|t| {
            t.duration_since(std::time::SystemTime::UNIX_EPOCH)
                .map_err(std::io::Error::other)
        })
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

/// Scan a folder and return all image infos
#[tauri::command]
pub async fn scan_folder(
    app: AppHandle,
    path: String,
    recursive: bool,
) -> Result<Vec<ImageInfo>, String> {
    log::info!("Starting folder scan: {} (recursive={})", path, recursive);

    let result = tauri::async_runtime::spawn_blocking(move || {
        let cache_dir = dirs::home_dir()
            .unwrap_or_default()
            .join(".wiphoto")
            .join("cache")
            .join("thumbnails");
        let _ = fs::create_dir_all(&cache_dir);

        let files = collect_files(&path, recursive);
        let total = files.len() as u32;
        log::info!("Found {} files to scan", total);

        if total == 0 {
            log::info!("Scan completed. No files found.");
            return Ok(vec![]);
        }

        let db_mtimes = crate::db::get_folder_mtimes(&path).unwrap_or_default();

        let _ = app.emit(
            "scan-progress",
            serde_json::json!({
                "current": 0,
                "total": total,
                "current_file": ""
            }),
        );

        let mut cached_paths = Vec::new();
        let mut uncached_files = Vec::new();
        let mut file_paths_set = std::collections::HashSet::new();

        for file_path in &files {
            let path_str = file_path.to_string_lossy().to_string();
            let img_mtime = get_modified_time(file_path);
            let xmp_path = file_path.with_extension("xmp");
            let xmp_mtime = if xmp_path.exists() {
                get_modified_time(&xmp_path)
            } else {
                0
            };
            let mtime = img_mtime.max(xmp_mtime);
            file_paths_set.insert(path_str.clone());

            if let Some(&cached_mtime) = db_mtimes.get(&path_str) {
                if cached_mtime == mtime {
                    cached_paths.push(path_str);
                    continue;
                }
            }
            uncached_files.push((file_path.clone(), mtime));
        }

        let mut final_results = Vec::new();
        let mut current_count = 0;

        let mut cached_infos = crate::db::get_images_by_paths(&cached_paths).unwrap_or_default();
        for chunk in cached_infos.chunks(50) {
            let _ = app.emit("image-scanned-batch", chunk.to_vec());
            current_count += chunk.len() as u32;
            let _ = app.emit(
                "scan-progress",
                serde_json::json!({
                    "current": current_count,
                    "total": total,
                    "current_file": chunk.last().map(|i| i.path.clone()).unwrap_or_default()
                }),
            );
        }
        final_results.append(&mut cached_infos);

        use std::sync::atomic::{AtomicU32, Ordering};
        let counter = AtomicU32::new(current_count);
        let (tx, rx) = std::sync::mpsc::channel();

        let app_clone = app.clone();
        let batch_thread = std::thread::spawn(move || {
            let mut batch = Vec::new();
            for info in rx {
                batch.push(info);
                if batch.len() >= 50 {
                    let _ = app_clone.emit("image-scanned-batch", batch.clone());
                    batch.clear();
                }
            }
            if !batch.is_empty() {
                let _ = app_clone.emit("image-scanned-batch", batch);
            }
        });

        let new_infos: Vec<(ImageInfo, u64)> = uncached_files
            .par_iter()
            .filter_map(|(file_path, mtime)| {
                let path_str = file_path.to_string_lossy().to_string();
                if let Some(info) = process_single_file(file_path, &cache_dir) {
                    let _ = tx.send(info.clone());
                    let current = counter.fetch_add(1, Ordering::SeqCst) + 1;
                    if current % 10 == 0 || current == total {
                        let _ = app.emit(
                            "scan-progress",
                            serde_json::json!({
                                "current": current,
                                "total": total,
                                "current_file": path_str
                            }),
                        );
                    }
                    Some((info, *mtime))
                } else {
                    let current = counter.fetch_add(1, Ordering::SeqCst) + 1;
                    if current % 10 == 0 || current == total {
                        let _ = app.emit(
                            "scan-progress",
                            serde_json::json!({
                                "current": current,
                                "total": total,
                                "current_file": path_str
                            }),
                        );
                    }
                    None
                }
            })
            .collect();

        drop(tx);
        let _ = batch_thread.join();

        let mut to_save_refs = Vec::new();
        for (info, mtime) in &new_infos {
            final_results.push(info.clone());
            to_save_refs.push((info, *mtime));
        }

        final_results.sort_by(|a, b| a.path.cmp(&b.path));

        if !to_save_refs.is_empty() {
            if let Err(e) = crate::db::save_images_batch(&to_save_refs) {
                log::error!("Failed to save scanned images to database: {}", e);
            }
            let newly_scanned_paths: Vec<PathBuf> =
                uncached_files.into_iter().map(|(p, _)| p).collect();
            enqueue_background_onnx_tasks(newly_scanned_paths);
        }

        let mut to_delete = Vec::new();
        let root_path_buf = PathBuf::from(&path);
        for cached_path in db_mtimes.keys() {
            if !recursive && !is_direct_child(&root_path_buf, Path::new(cached_path)) {
                continue;
            }
            if !file_paths_set.contains(cached_path) {
                to_delete.push(cached_path.clone());
            }
        }

        if !to_delete.is_empty() {
            if let Err(e) = crate::db::delete_images_batch(&to_delete) {
                log::error!("Failed to delete orphaned database records: {}", e);
            }
        }

        log::info!(
            "Folder scan completed. Successfully processed {} files.",
            final_results.len()
        );

        let _ = app.emit(
            "scan-finished",
            serde_json::json!({
                "total": final_results.len()
            }),
        );

        Ok::<Vec<ImageInfo>, String>(final_results)
    })
    .await
    .map_err(|e| format!("Task failed: {}", e))??;

    Ok(result)
}

/// Get file count in a directory (for preview)
#[tauri::command]
pub async fn count_files(path: String, recursive: bool) -> Result<u32, String> {
    let count =
        tauri::async_runtime::spawn_blocking(move || collect_files(&path, recursive).len() as u32)
            .await
            .map_err(|e| format!("Task failed: {}", e))?;
    Ok(count)
}

/// JS error logger command
#[tauri::command]
pub fn log_js(message: String) {
    log::info!("[JS] {}", message);
}
