use crate::models::image_info::{self, ImageInfo, RAW_EXTENSIONS, VIDEO_EXTENSIONS};
use base64::{engine::general_purpose::STANDARD, Engine};
use image::imageops::FilterType;
use rayon::prelude::*;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use tauri::{Emitter, AppHandle};

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

/// Generate a thumbnail as base64 string
fn generate_thumbnail(path: &Path, cache_dir: &Path) -> Option<String> {
    // Create cache key from path hash
    let hash = sha2_hash(path.to_string_lossy().as_ref());
    let cache_file = cache_dir.join(format!("{}.jpg", hash));

    // Check cache first
    if cache_file.exists() {
        if let Ok(bytes) = fs::read(&cache_file) {
            return Some(STANDARD.encode(&bytes));
        }
    }

    let ext = path.extension()?.to_string_lossy().to_lowercase();

    // For videos, generate a placeholder thumbnail
    if VIDEO_EXTENSIONS.contains(&ext.as_str()) {
        return Some(generate_video_placeholder(path));
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

    // Encode to base64
    let mut buf = Vec::new();
    let mut cursor = std::io::Cursor::new(&mut buf);
    thumb
        .write_to(&mut cursor, image::ImageFormat::Jpeg)
        .ok()?;
    Some(STANDARD.encode(&buf))
}

/// Try to load RAW thumbnail from embedded JPEG
fn load_raw_thumbnail(path: &Path) -> Option<image::DynamicImage> {
    // 1. Try kamadak-exif to find embedded thumbnail (fast)
    if let Ok(file) = std::fs::File::open(path) {
        let mut bufreader = std::io::BufReader::new(&file);
        let exif_reader = exif::Reader::new();
        if let Ok(exif) = exif_reader.read_from_container(&mut bufreader) {
            if let Some(thumb_offset) = exif.get_field(exif::Tag::JPEGInterchangeFormat, exif::In::THUMBNAIL) {
                if let Some(thumb_length) = exif.get_field(exif::Tag::JPEGInterchangeFormatLength, exif::In::THUMBNAIL) {
                    if let (Some(offset), Some(length)) = (thumb_offset.value.get_uint(0), thumb_length.value.get_uint(0)) {
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

fn generate_video_placeholder(_path: &Path) -> String {
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
    let mut buf = Vec::new();
    let mut cursor = std::io::Cursor::new(&mut buf);
    let _ = image::DynamicImage::ImageRgba8(img).write_to(&mut cursor, image::ImageFormat::Jpeg);
    STANDARD.encode(&buf)
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
                info.camera_model = field.display_value().to_string().trim_matches('"').to_string();
            }
            // Date taken
            if let Some(field) = exif_data.get_field(exif::Tag::DateTimeOriginal, exif::In::PRIMARY) {
                info.date_taken = field.display_value().to_string().trim_matches('"').to_string();
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
            if let Some(w_field) = exif_data.get_field(exif::Tag::ImageWidth, exif::In::PRIMARY)
                .or_else(|| exif_data.get_field(exif::Tag::PixelXDimension, exif::In::PRIMARY))
            {
                exif_width = w_field.value.get_uint(0);
            }
            if let Some(h_field) = exif_data.get_field(exif::Tag::ImageLength, exif::In::PRIMARY)
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
            let mut coord = deg + min / 60.0 + sec / 3600.0;
            let ref_str = reference.trim_matches('"').trim();
            if ref_str == "S" || ref_str == "W" {
                coord = -coord;
            }
            Some(coord)
        }
        _ => None,
    }
}

/// Scan a folder and return all image infos
#[tauri::command]
pub async fn scan_folder(
    app: AppHandle,
    path: String,
    recursive: bool,
) -> Result<Vec<ImageInfo>, String> {
    log::info!("Starting folder scan: {} (recursive={})", path, recursive);
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

    // Emit initial progress
    let _ = app.emit("scan-progress", serde_json::json!({
        "current": 0,
        "total": total,
        "current_file": ""
    }));

    let results = Mutex::new(Vec::new());
    let counter = Mutex::new(0u32);

    files.par_iter().for_each(|file_path| {
        if let Some(info) = process_single_file(file_path, &cache_dir) {
            let mut r = results.lock().unwrap();
            r.push(info.clone());

            let mut c = counter.lock().unwrap();
            *c += 1;

            let _ = app.emit("image-scanned", info);

            if *c % 5 == 0 || *c == total {
                let _ = app.emit("scan-progress", serde_json::json!({
                    "current": *c,
                    "total": total,
                    "current_file": file_path.to_string_lossy()
                }));
            }
        }
    });

    let mut final_results = results.into_inner().unwrap();
    // Sort by path for consistency
    final_results.sort_by(|a, b| a.path.cmp(&b.path));
    log::info!("Folder scan completed. Successfully processed {} files.", final_results.len());

    let _ = app.emit("scan-finished", serde_json::json!({
        "total": final_results.len()
    }));

    Ok(final_results)
}

/// Get file count in a directory (for preview)
#[tauri::command]
pub fn count_files(path: String, recursive: bool) -> u32 {
    collect_files(&path, recursive).len() as u32
}

/// JS error logger command
#[tauri::command]
pub fn log_js(message: String) {
    log::error!("[JS-Frontend] {}", message);
}
