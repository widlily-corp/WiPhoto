use std::fs;
use std::path::Path;

const TRASH_DIR_NAME: &str = ".wiphoto/trash";

fn get_trash_dir() -> std::path::PathBuf {
    let dir = dirs::home_dir().unwrap_or_default().join(TRASH_DIR_NAME);
    let _ = fs::create_dir_all(&dir);
    dir
}

/// Move files to WiPhoto trash
#[tauri::command]
pub fn delete_files(paths: Vec<String>) -> Result<Vec<String>, String> {
    let trash_dir = get_trash_dir();
    let mut deleted = Vec::new();

    // Load existing metadata
    let metadata_path = trash_dir.join(".trash_metadata.json");
    let mut metadata_map: std::collections::HashMap<String, String> = if metadata_path.exists() {
        let content = fs::read_to_string(&metadata_path).unwrap_or_default();
        serde_json::from_str(&content).unwrap_or_default()
    } else {
        std::collections::HashMap::new()
    };

    for path in &paths {
        let src = Path::new(path);
        if !src.exists() {
            continue;
        }

        let filename = src
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .to_string();
        let mut dest = trash_dir.join(&filename);

        // Handle name conflicts
        if dest.exists() {
            let stem = src
                .file_stem()
                .unwrap_or_default()
                .to_string_lossy()
                .to_string();
            let ext = src
                .extension()
                .map(|e| e.to_string_lossy().to_string())
                .unwrap_or_default();
            let mut counter = 1;
            loop {
                let new_name = if ext.is_empty() {
                    format!("{}_{}", stem, counter)
                } else {
                    format!("{}_{}.{}", stem, counter, ext)
                };
                dest = trash_dir.join(&new_name);
                if !dest.exists() {
                    break;
                }
                counter += 1;
            }
        }

        if fs::rename(src, &dest).is_ok()
            || fs::copy(src, &dest).map(|_| fs::remove_file(src)).is_ok()
        {
            deleted.push(path.clone());

            let trash_filename = dest
                .file_name()
                .unwrap_or_default()
                .to_string_lossy()
                .to_string();
            metadata_map.insert(trash_filename, path.clone());

            // Also move XMP sidecar if exists
            let xmp_src = Path::new(path).with_extension("xmp");
            if xmp_src.exists() {
                let xmp_dest = dest.with_extension("xmp");
                let _ = fs::rename(&xmp_src, &xmp_dest);
            }
        }
    }

    if !deleted.is_empty() {
        let content = serde_json::to_string_pretty(&metadata_map).unwrap_or_default();
        let _ = fs::write(&metadata_path, content);
    }

    Ok(deleted)
}

/// Copy files to destination
#[tauri::command]
pub fn copy_files(paths: Vec<String>, dest_dir: String) -> Result<u32, String> {
    let dest = Path::new(&dest_dir);
    if !dest.exists() {
        return Err("Destination directory does not exist".into());
    }

    let mut count = 0u32;
    for path in &paths {
        let src = Path::new(path);
        if !src.exists() {
            continue;
        }
        let filename = src.file_name().unwrap_or_default();
        let dest_file = dest.join(filename);

        if dest_file == *src {
            continue;
        }

        if fs::copy(src, &dest_file).is_ok() {
            count += 1;
            // Copy XMP sidecar
            let xmp_src = src.with_extension("xmp");
            if xmp_src.exists() {
                let xmp_dest = dest_file.with_extension("xmp");
                let _ = fs::copy(&xmp_src, &xmp_dest);
            }
        }
    }

    Ok(count)
}

/// Move files to destination
#[tauri::command]
pub fn move_files(paths: Vec<String>, dest_dir: String) -> Result<Vec<String>, String> {
    let dest = Path::new(&dest_dir);
    if !dest.exists() {
        return Err("Destination directory does not exist".into());
    }

    let mut moved = Vec::new();
    for path in &paths {
        let src = Path::new(path);
        if !src.exists() {
            continue;
        }
        let filename = src.file_name().unwrap_or_default();
        let dest_file = dest.join(filename);

        if dest_file == *src {
            continue;
        }

        let success = fs::rename(src, &dest_file).is_ok()
            || (fs::copy(src, &dest_file).is_ok() && fs::remove_file(src).is_ok());

        if success {
            moved.push(path.clone());
            // Move XMP sidecar
            let xmp_src = src.with_extension("xmp");
            if xmp_src.exists() {
                let xmp_dest = dest_file.with_extension("xmp");
                let _ = fs::rename(&xmp_src, &xmp_dest);
            }
        }
    }

    Ok(moved)
}

/// Permanently delete files (from trash)
#[tauri::command]
pub fn delete_permanently(paths: Vec<String>) -> Result<u32, String> {
    let mut count = 0u32;
    for path in &paths {
        if fs::remove_file(path).is_ok() {
            count += 1;
            // Also remove XMP sidecar
            let xmp_path = Path::new(path).with_extension("xmp");
            let _ = fs::remove_file(&xmp_path);
        }
    }
    Ok(count)
}

/// Batch rename files
#[tauri::command]
pub fn batch_rename(rename_map: Vec<(String, String)>) -> Result<u32, String> {
    let mut count = 0u32;
    for (old_path, new_path) in &rename_map {
        if old_path == new_path {
            continue;
        }
        if fs::rename(old_path, new_path).is_ok() {
            count += 1;
            // Rename XMP sidecar
            let xmp_old = Path::new(old_path).with_extension("xmp");
            let xmp_new = Path::new(new_path).with_extension("xmp");
            if xmp_old.exists() {
                let _ = fs::rename(&xmp_old, &xmp_new);
            }
        }
    }
    Ok(count)
}

/// Get directory tree structure
#[tauri::command]
pub fn get_folder_tree(root_path: String) -> Result<Vec<FolderNode>, String> {
    let root = Path::new(&root_path);
    if !root.exists() {
        return Err("Path does not exist".into());
    }
    Ok(build_folder_tree(root, 3))
}

#[derive(serde::Serialize, serde::Deserialize)]
pub struct FolderNode {
    pub name: String,
    pub path: String,
    pub children: Vec<FolderNode>,
    pub file_count: u32,
}

fn build_folder_tree(dir: &Path, depth: u32) -> Vec<FolderNode> {
    if depth == 0 {
        return vec![];
    }

    let mut nodes = Vec::new();
    if let Ok(entries) = fs::read_dir(dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                let name = path
                    .file_name()
                    .unwrap_or_default()
                    .to_string_lossy()
                    .to_string();
                // Skip hidden dirs
                if name.starts_with('.') {
                    continue;
                }
                let file_count = count_images_in_dir(&path);
                let children = build_folder_tree(&path, depth - 1);
                nodes.push(FolderNode {
                    name,
                    path: path.to_string_lossy().to_string(),
                    children,
                    file_count,
                });
            }
        }
    }
    nodes.sort_by_key(|a| a.name.to_lowercase());
    nodes
}

fn count_images_in_dir(dir: &Path) -> u32 {
    let mut count = 0;
    if let Ok(entries) = fs::read_dir(dir) {
        for entry in entries.flatten() {
            if entry.path().is_file() {
                if let Some(ext) = entry.path().extension() {
                    let ext = ext.to_string_lossy().to_lowercase();
                    if crate::models::image_info::is_supported_extension(&ext) {
                        count += 1;
                    }
                }
            }
        }
    }
    count
}

#[derive(serde::Serialize, serde::Deserialize)]
pub struct TrashItem {
    pub filename: String,
    pub path: String,
    pub original_path: String,
    pub file_size: u64,
    pub thumbnail: String,
    pub is_video: bool,
    pub is_raw: bool,
}

/// List all files in the trash with metadata and thumbnails
#[tauri::command]
pub fn list_trash() -> Result<Vec<TrashItem>, String> {
    let trash_dir = get_trash_dir();
    let metadata_path = trash_dir.join(".trash_metadata.json");

    let metadata_map: std::collections::HashMap<String, String> = if metadata_path.exists() {
        let content = fs::read_to_string(&metadata_path).unwrap_or_default();
        serde_json::from_str(&content).unwrap_or_default()
    } else {
        std::collections::HashMap::new()
    };

    let mut items = Vec::new();
    if let Ok(entries) = fs::read_dir(&trash_dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_file() {
                let filename = path
                    .file_name()
                    .unwrap_or_default()
                    .to_string_lossy()
                    .to_string();
                if filename == ".trash_metadata.json" || filename.ends_with(".xmp") {
                    continue;
                }

                let file_size = path.metadata().map(|m| m.len()).unwrap_or(0);
                let original_path = metadata_map
                    .get(&filename)
                    .cloned()
                    .unwrap_or_else(|| filename.clone());

                let ext = path
                    .extension()
                    .map(|e| e.to_string_lossy().to_lowercase())
                    .unwrap_or_default();
                let is_video = crate::models::image_info::VIDEO_EXTENSIONS.contains(&ext.as_str());
                let is_raw = crate::models::image_info::RAW_EXTENSIONS.contains(&ext.as_str());

                // Generate/load cached thumbnail
                let thumbnail = tauri::async_runtime::block_on(super::thumbnails::get_thumbnail(
                    path.to_string_lossy().to_string(),
                ))
                .unwrap_or_default();

                items.push(TrashItem {
                    filename,
                    path: path.to_string_lossy().to_string(),
                    original_path,
                    file_size,
                    thumbnail,
                    is_video,
                    is_raw,
                });
            }
        }
    }

    Ok(items)
}

/// Restore a file from trash back to its original path
#[tauri::command]
pub fn restore_from_trash(filename: String) -> Result<(), String> {
    let trash_dir = get_trash_dir();
    let src_file = trash_dir.join(&filename);
    if !src_file.exists() {
        return Err("File does not exist in trash".into());
    }

    let metadata_path = trash_dir.join(".trash_metadata.json");
    let mut metadata_map: std::collections::HashMap<String, String> = if metadata_path.exists() {
        let content = fs::read_to_string(&metadata_path).unwrap_or_default();
        serde_json::from_str(&content).unwrap_or_default()
    } else {
        std::collections::HashMap::new()
    };

    let original_path = metadata_map
        .get(&filename)
        .ok_or_else(|| "Original path not found in metadata".to_string())?;

    let dest_file = Path::new(original_path);

    if let Some(parent) = dest_file.parent() {
        let _ = fs::create_dir_all(parent);
    }

    if fs::rename(&src_file, dest_file).is_ok()
        || (fs::copy(&src_file, dest_file).is_ok() && fs::remove_file(&src_file).is_ok())
    {
        // Also restore XMP sidecar if it exists
        let xmp_src = src_file.with_extension("xmp");
        if xmp_src.exists() {
            let xmp_dest = dest_file.with_extension("xmp");
            let _ = fs::rename(&xmp_src, &xmp_dest);
        }

        // Remove from metadata map
        metadata_map.remove(&filename);
        let _ = fs::write(
            &metadata_path,
            serde_json::to_string_pretty(&metadata_map).unwrap_or_default(),
        );

        Ok(())
    } else {
        Err("Failed to restore file".into())
    }
}

/// Clear trash completely
#[tauri::command]
pub fn empty_trash() -> Result<(), String> {
    let trash_dir = get_trash_dir();
    if let Ok(entries) = fs::read_dir(&trash_dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_file() {
                let filename = path
                    .file_name()
                    .unwrap_or_default()
                    .to_string_lossy()
                    .to_string();
                if filename == ".trash_metadata.json" {
                    continue;
                }
                let _ = fs::remove_file(path);
            }
        }
    }
    // Clear metadata file
    let metadata_path = trash_dir.join(".trash_metadata.json");
    if metadata_path.exists() {
        let _ = fs::remove_file(metadata_path);
    }
    Ok(())
}

/// Open a file in the system default media player
#[tauri::command]
pub fn open_in_system_player(app: tauri::AppHandle, path: String) -> Result<(), String> {
    log::info!("Opening file in system player: {}", path);
    use tauri_plugin_opener::OpenerExt;
    app.opener()
        .open_path(path, None::<String>)
        .map_err(|e| format!("Failed to open path: {}", e))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_get_trash_dir() {
        // Act
        let trash_dir = get_trash_dir();

        // Assert
        assert!(trash_dir.exists());
        assert!(trash_dir.to_string_lossy().contains(".wiphoto/trash"));
    }

    #[test]
    fn test_delete_non_existent_file() {
        // Arrange
        let paths = vec!["non_existent_file.jpg".to_string()];

        // Act
        let result = delete_files(paths).expect("Failed to call delete_files");

        // Assert
        assert!(result.is_empty());
    }

    #[test]
    fn test_copy_files() {
        // Arrange
        let dir = std::env::temp_dir().join(uuid::Uuid::new_v4().to_string());
        std::fs::create_dir_all(&dir).unwrap();
        let src_dir = dir.join("src");
        let dest_dir = dir.join("dest");
        std::fs::create_dir_all(&src_dir).unwrap();
        std::fs::create_dir_all(&dest_dir).unwrap();
        let src_file = src_dir.join("test.txt");
        std::fs::write(&src_file, "content").unwrap();

        // Act
        let result = copy_files(
            vec![src_file.to_string_lossy().to_string()],
            dest_dir.to_string_lossy().to_string(),
        )
        .expect("Failed copy");

        // Assert
        assert_eq!(result, 1);
        assert!(dest_dir.join("test.txt").exists());

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_move_files() {
        // Arrange
        let dir = std::env::temp_dir().join(uuid::Uuid::new_v4().to_string());
        std::fs::create_dir_all(&dir).unwrap();
        let src_dir = dir.join("src");
        let dest_dir = dir.join("dest");
        std::fs::create_dir_all(&src_dir).unwrap();
        std::fs::create_dir_all(&dest_dir).unwrap();
        let src_file = src_dir.join("test.txt");
        std::fs::write(&src_file, "content").unwrap();

        // Act
        let result = move_files(
            vec![src_file.to_string_lossy().to_string()],
            dest_dir.to_string_lossy().to_string(),
        )
        .expect("Failed move");

        // Assert
        assert_eq!(result.len(), 1);
        assert!(!src_file.exists());
        assert!(dest_dir.join("test.txt").exists());

        let _ = std::fs::remove_dir_all(&dir);
    }
}
