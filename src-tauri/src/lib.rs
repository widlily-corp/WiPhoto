mod commands;
mod models;

use commands::{
    duplicates, editor, export, file_ops, metadata, scanner, settings, thumbnails, xmp,
};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();
    log::info!("Starting WiPhoto v3.0.0 application...");

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
