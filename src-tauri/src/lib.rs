pub mod commands;
pub mod db;
pub mod models;
pub mod onnx;

use commands::{
    duplicates, editor, export, file_ops, metadata, scanner, search, settings, thumbnails, xmp,
};

struct FileAndConsoleLogger {
    file: Option<Mutex<File>>,
}

impl log::Log for FileAndConsoleLogger {
    fn enabled(&self, metadata: &log::Metadata) -> bool {
        metadata.level() <= log::Level::Info
    }

    fn log(&self, record: &log::Record) {
        if self.enabled(record.metadata()) {
            let timestamp = chrono::Local::now().format("%Y-%m-%dT%H:%M:%S%.3f%z");
            let msg = format!(
                "[{}] [{}] [{}] {}",
                timestamp,
                record.level(),
                record.target(),
                record.args()
            );

            // Write to console (stderr)
            eprintln!("{}", msg);

            // Write to file if open
            if let Some(ref file_mutex) = self.file {
                if let Ok(mut file) = file_mutex.lock() {
                    let _ = writeln!(file, "{}", msg);
                }
            }
        }
    }

    fn flush(&self) {
        if let Some(ref file_mutex) = self.file {
            if let Ok(mut file) = file_mutex.lock() {
                let _ = file.flush();
            }
        }
    }
}

fn init_logger() {
    let mut exe_path = std::env::current_exe().unwrap_or_default();
    exe_path.set_file_name("debug.log");
    let file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&exe_path)
        .ok()
        .map(Mutex::new);

    let logger = FileAndConsoleLogger { file };
    let _ =
        log::set_boxed_logger(Box::new(logger)).map(|_| log::set_max_level(log::LevelFilter::Info));
}

use std::fs::File;
use std::io::Write;
use std::sync::Mutex;

pub fn handle_asset_custom_protocol(
    request: tauri::http::Request<Vec<u8>>,
) -> tauri::http::Response<std::borrow::Cow<'static, [u8]>> {
    let path_str = request.uri().path();
    let decoded_path = decode_percent(path_str);
    let clean_path = if decoded_path.starts_with('/') && decoded_path.chars().nth(2) == Some(':') {
        &decoded_path[1..]
    } else {
        &decoded_path
    };

    let file_path = std::path::Path::new(clean_path);
    if !file_path.exists() || !file_path.is_file() {
        return tauri::http::Response::builder()
            .status(404)
            .header("Access-Control-Allow-Origin", "*")
            .body(std::borrow::Cow::Borrowed(b"Not Found" as &[u8]))
            .unwrap_or_else(|_| {
                tauri::http::Response::new(std::borrow::Cow::Borrowed(b"Not Found" as &[u8]))
            });
    }

    let (file_len, mtime_secs) = match file_path.metadata() {
        Ok(m) => {
            let len = m.len();
            let mtime = m
                .modified()
                .ok()
                .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
                .map(|d| d.as_secs())
                .unwrap_or(0);
            (len, mtime)
        }
        Err(_) => (0, 0),
    };

    let etag = format!("\"{:x}-{:x}\"", file_len, mtime_secs);

    if let Some(if_none_match) = request.headers().get("if-none-match") {
        if let Ok(val) = if_none_match.to_str() {
            if val == etag || val == "*" {
                return tauri::http::Response::builder()
                    .status(304)
                    .header("ETag", &etag)
                    .header("Cache-Control", "max-age=31536000, immutable")
                    .header("Access-Control-Allow-Origin", "*")
                    .body(std::borrow::Cow::Borrowed(&[] as &[u8]))
                    .unwrap_or_else(|_| {
                        tauri::http::Response::new(std::borrow::Cow::Borrowed(&[] as &[u8]))
                    });
            }
        }
    }

    let ext = file_path
        .extension()
        .and_then(|s| s.to_str())
        .unwrap_or("")
        .to_lowercase();
    let mime = match ext.as_str() {
        "jpg" | "jpeg" => "image/jpeg",
        "png" => "image/png",
        "gif" => "image/gif",
        "webp" => "image/webp",
        "svg" => "image/svg+xml",
        "bmp" => "image/bmp",
        "tiff" | "tif" => "image/tiff",
        "ico" => "image/x-icon",
        "mp4" => "video/mp4",
        "webm" => "video/webm",
        "arw" => "image/x-sony-arw",
        "cr2" => "image/x-canon-cr2",
        "cr3" => "image/x-canon-cr3",
        "nef" => "image/x-nikon-nef",
        "dng" => "image/x-adobe-dng",
        "orf" => "image/x-olympus-orf",
        "rw2" => "image/x-panasonic-rw2",
        "pef" | "ptx" => "image/x-pentax-pef",
        "raf" => "image/x-fuji-raf",
        "heic" | "heif" => "image/heic",
        "avif" => "image/avif",
        "jxl" => "image/jxl",
        _ => "application/octet-stream",
    };

    let range_header = request.headers().get("range").and_then(|h| h.to_str().ok());
    if let Some(range_str) = range_header {
        if let Some(range_spec) = range_str.strip_prefix("bytes=") {
            let parts: Vec<&str> = range_spec.split('-').collect();
            if parts.len() == 2 {
                let start_opt = parts[0].parse::<u64>().ok();
                let end_opt = parts[1].parse::<u64>().ok();

                let (start, end) = match (start_opt, end_opt) {
                    (Some(s), Some(e)) => (s, e.min(file_len.saturating_sub(1))),
                    (Some(s), None) => (s, file_len.saturating_sub(1)),
                    (None, Some(e)) => (file_len.saturating_sub(e), file_len.saturating_sub(1)),
                    (None, None) => (0, file_len.saturating_sub(1)),
                };

                if start <= end && start < file_len {
                    let range_len = (end - start + 1) as usize;
                    if let Ok(mut file) = std::fs::File::open(file_path) {
                        use std::io::{Read, Seek, SeekFrom};
                        if file.seek(SeekFrom::Start(start)).is_ok() {
                            let mut buffer = vec![0u8; range_len];
                            if file.read_exact(&mut buffer).is_ok() {
                                let content_range = format!("bytes {}-{}/{}", start, end, file_len);
                                if let Ok(resp) = tauri::http::Response::builder()
                                    .status(206)
                                    .header("Content-Type", mime)
                                    .header("Content-Length", range_len.to_string())
                                    .header("Content-Range", content_range)
                                    .header("Accept-Ranges", "bytes")
                                    .header("Cache-Control", "max-age=31536000, immutable")
                                    .header("ETag", &etag)
                                    .header("Access-Control-Allow-Origin", "*")
                                    .body(std::borrow::Cow::Owned(buffer))
                                {
                                    return resp;
                                }
                            }
                        }
                    }
                } else {
                    return tauri::http::Response::builder()
                        .status(416)
                        .header("Content-Range", format!("bytes */{}", file_len))
                        .header("Access-Control-Allow-Origin", "*")
                        .body(std::borrow::Cow::Borrowed(&[] as &[u8]))
                        .unwrap_or_else(|_| {
                            tauri::http::Response::new(std::borrow::Cow::Borrowed(&[] as &[u8]))
                        });
                }
            }
        }
    }

    if let Ok(bytes) = std::fs::read(file_path) {
        if let Ok(resp) = tauri::http::Response::builder()
            .status(200)
            .header("Content-Type", mime)
            .header("Content-Length", bytes.len().to_string())
            .header("Accept-Ranges", "bytes")
            .header("Cache-Control", "max-age=31536000, immutable")
            .header("ETag", &etag)
            .header("Access-Control-Allow-Origin", "*")
            .body(std::borrow::Cow::Owned(bytes))
        {
            return resp;
        }
    }

    tauri::http::Response::builder()
        .status(404)
        .header("Access-Control-Allow-Origin", "*")
        .body(std::borrow::Cow::Borrowed(b"Not Found" as &[u8]))
        .unwrap_or_else(|_| {
            tauri::http::Response::new(std::borrow::Cow::Borrowed(b"Not Found" as &[u8]))
        })
}

pub fn decode_percent(s: &str) -> String {
    let mut bytes = Vec::with_capacity(s.len());
    let mut input_bytes = s.bytes();
    while let Some(b) = input_bytes.next() {
        if b == b'%' {
            let h1 = input_bytes.next();
            let h2 = input_bytes.next();
            if let (Some(h1), Some(h2)) = (h1, h2) {
                let hex = [h1, h2];
                if let Ok(hex_str) = std::str::from_utf8(&hex) {
                    if let Ok(val) = u8::from_str_radix(hex_str, 16) {
                        bytes.push(val);
                        continue;
                    }
                }
                bytes.push(b'%');
                bytes.push(h1);
                bytes.push(h2);
            } else {
                bytes.push(b'%');
                if let Some(h1) = h1 {
                    bytes.push(h1);
                }
            }
        } else {
            bytes.push(b);
        }
    }
    String::from_utf8_lossy(&bytes).into_owned()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    init_logger();
    log::info!(
        "Starting WiPhoto v{} application...",
        env!("CARGO_PKG_VERSION")
    );

    if let Err(e) = db::init_db() {
        log::error!("Failed to initialize database: {}", e);
    }

    // Spawn background task to prune old thumbnails
    std::thread::spawn(|| {
        log::info!("Starting background thumbnail cache pruning...");
        match commands::thumbnails::auto_prune_thumbnail_cache() {
            Ok(count) => log::info!("Pruned {} old thumbnails from cache.", count),
            Err(e) => log::error!("Failed to prune thumbnail cache: {}", e),
        }
    });

    tauri::Builder::default()
        .register_uri_scheme_protocol("asset", |_ctx, req| handle_asset_custom_protocol(req))
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            // Scanner
            scanner::scan_folder,
            scanner::count_files,
            // Thumbnails
            thumbnails::get_thumbnail,
            thumbnails::load_full_image,
            thumbnails::clear_thumbnail_cache,
            thumbnails::get_image_url,
            // Metadata
            metadata::read_exif,
            metadata::update_photo_metadata,
            metadata::get_geotagged_photos,
            // File operations
            file_ops::delete_files,
            file_ops::copy_files,
            file_ops::move_files,
            file_ops::delete_permanently,
            file_ops::batch_rename,
            file_ops::get_folder_tree,
            file_ops::list_trash,
            file_ops::restore_from_trash,
            file_ops::empty_trash,
            file_ops::open_in_system_player,
            // Duplicates
            duplicates::find_duplicates,
            duplicates::get_duplicate_stats,
            duplicates::compute_phash,
            duplicates::index_faces,
            duplicates::find_similar_images,
            duplicates::get_indexed_faces,
            duplicates::group_faces_by_person,
            duplicates::find_smart_duplicates,
            // Editor
            editor::apply_edit,
            editor::save_edited,
            editor::crop_image,
            editor::save_cropped_edited_image,
            editor::get_histogram,
            editor::get_color_palette,
            // Export
            export::export_files,
            export::batch_export_advanced,
            // Settings
            settings::load_settings,
            settings::save_settings,
            settings::get_app_version,
            settings::get_app_info,
            // XMP
            xmp::read_xmp_sidecar,
            xmp::write_xmp_sidecar,
            xmp::sync_xmp_sidecar,
            // Search
            search::search_clip_semantic,
            search::search_clip,
            // Logger
            scanner::log_js,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_decode_percent_utf8_cyrillic() {
        let encoded = "%D1%85";
        let decoded = decode_percent(encoded);
        assert_eq!(decoded, "х");
    }

    #[test]
    fn test_decode_percent_ascii_and_spaces() {
        let encoded = "C:/photos/my%20test%20image.jpg";
        let decoded = decode_percent(encoded);
        assert_eq!(decoded, "C:/photos/my test image.jpg");
    }

    #[test]
    fn test_handle_asset_custom_protocol_range_and_headers() {
        let temp_dir = std::env::temp_dir().join(uuid::Uuid::new_v4().to_string());
        std::fs::create_dir_all(&temp_dir).unwrap();
        let file_path = temp_dir.join("test.arw");
        std::fs::write(&file_path, b"0123456789ABCDEF").unwrap();

        let path_str = file_path.to_string_lossy();
        let uri = format!("asset://localhost/{}", path_str);
        let req = tauri::http::Request::builder()
            .uri(&uri)
            .header("Range", "bytes=4-11")
            .body(vec![])
            .unwrap();

        let resp = handle_asset_custom_protocol(req);
        assert_eq!(resp.status(), 206);
        assert_eq!(
            resp.headers().get("Content-Type").unwrap(),
            "image/x-sony-arw"
        );
        assert_eq!(resp.headers().get("Content-Length").unwrap(), "8");
        assert_eq!(
            resp.headers().get("Content-Range").unwrap(),
            "bytes 4-11/16"
        );
        assert_eq!(resp.body().as_ref(), b"456789AB");

        let _ = std::fs::remove_dir_all(&temp_dir);
    }
}
