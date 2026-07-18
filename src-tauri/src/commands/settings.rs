use crate::models::image_info::AppSettings;
use std::fs;

fn settings_path() -> std::path::PathBuf {
    let dir = dirs::home_dir().unwrap_or_default().join(".wiphoto");
    let _ = fs::create_dir_all(&dir);
    dir.join("settings.json")
}

/// Load settings from disk
#[tauri::command]
pub fn load_settings() -> AppSettings {
    let path = settings_path();
    if path.exists() {
        if let Ok(content) = fs::read_to_string(&path) {
            if let Ok(settings) = serde_json::from_str::<AppSettings>(&content) {
                return settings;
            }
        }
    }
    AppSettings::default()
}

/// Save settings to disk
#[tauri::command]
pub fn save_settings(settings: AppSettings) -> Result<(), String> {
    let path = settings_path();
    let content =
        serde_json::to_string_pretty(&settings).map_err(|e| format!("Serialize error: {}", e))?;
    fs::write(&path, content).map_err(|e| format!("Write error: {}", e))?;

    // Ensure cache directory exists
    let _ = fs::create_dir_all(&settings.thumbnail_cache_path);

    Ok(())
}

/// Get app version
#[tauri::command]
pub fn get_app_version() -> String {
    "4.0.0".to_string()
}

/// Get app info
#[tauri::command]
pub fn get_app_info() -> AppInfo {
    AppInfo {
        version: "4.0.0".to_string(),
        author: "Widlily Corporation".to_string(),
        email: "widlily.corp@gmail.com".to_string(),
        description: "WiPhoto - Ваш умный менеджер фотографий.".to_string(),
        copyright: "© 2026, Widlily Corporation. Все права защищены.".to_string(),
    }
}

#[derive(serde::Serialize)]
pub struct AppInfo {
    pub version: String,
    pub author: String,
    pub email: String,
    pub description: String,
    pub copyright: String,
}
