mod commands;
mod models;

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
        .write(true)
        .append(true)
        .open(&exe_path)
        .ok()
        .map(|f| Mutex::new(f));

    let logger = FileAndConsoleLogger { file };
    let _ = log::set_boxed_logger(Box::new(logger))
        .map(|_| log::set_max_level(log::LevelFilter::Info));
}

use std::fs::File;
use std::io::Write;
use std::sync::Mutex;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    init_logger();
    log::info!("Starting WiPhoto v4.0.0 application...");

    tauri::Builder::default()
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
