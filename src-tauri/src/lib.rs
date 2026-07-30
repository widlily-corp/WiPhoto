pub mod commands;
pub mod db;
pub mod models;
pub mod onnx;

use commands::{
    duplicates, editor, export, file_ops, metadata, scanner, settings, thumbnails, xmp,
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
    if file_path.exists() && file_path.is_file() {
        if let Ok(bytes) = std::fs::read(file_path) {
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
                _ => "application/octet-stream",
            };
            return tauri::http::Response::builder()
                .status(200)
                .header("Content-Type", mime)
                .header("Access-Control-Allow-Origin", "*")
                .body(std::borrow::Cow::Owned(bytes))
                .unwrap_or_else(|_| {
                    tauri::http::Response::builder()
                        .status(500)
                        .body(std::borrow::Cow::Borrowed(b"Internal Error" as &[u8]))
                        .unwrap()
                });
        }
    }

    tauri::http::Response::builder()
        .status(404)
        .body(std::borrow::Cow::Borrowed(b"Not Found" as &[u8]))
        .unwrap()
}

pub fn decode_percent(s: &str) -> String {
    let mut result = String::with_capacity(s.len());
    let mut bytes = s.bytes();
    while let Some(b) = bytes.next() {
        if b == b'%' {
            let h1 = bytes.next();
            let h2 = bytes.next();
            if let (Some(h1), Some(h2)) = (h1, h2) {
                let hex = [h1, h2];
                if let Ok(hex_str) = std::str::from_utf8(&hex) {
                    if let Ok(val) = u8::from_str_radix(hex_str, 16) {
                        result.push(val as char);
                        continue;
                    }
                }
            }
            result.push('%');
        } else {
            result.push(b as char);
        }
    }
    result
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    init_logger();
    log::info!("Starting WiPhoto v5.0.0 application...");

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
        .register_uri_scheme_protocol("tauri", |_ctx, req| handle_asset_custom_protocol(req))
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            // Scanner
            scanner::scan_folder,
            scanner::count_files,
            // Thumbnails
            thumbnails::get_thumbnail,
            thumbnails::load_full_image,
            thumbnails::clear_thumbnail_cache,
            // Metadata
            metadata::read_exif,
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
            // Editor
            editor::apply_edit,
            editor::save_edited,
            editor::crop_image,
            editor::save_cropped_edited_image,
            editor::get_histogram,
            editor::get_color_palette,
            // Export
            export::export_files,
            // Settings
            settings::load_settings,
            settings::save_settings,
            settings::get_app_version,
            settings::get_app_info,
            // XMP
            xmp::read_xmp_sidecar,
            xmp::write_xmp_sidecar,
            // Logger
            scanner::log_js,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
