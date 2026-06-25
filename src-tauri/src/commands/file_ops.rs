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

    for path in &paths {
        let src = Path::new(path);
        if !src.exists() {
            continue;
        }

        let filename = src.file_name().unwrap_or_default().to_string_lossy().to_string();
        let mut dest = trash_dir.join(&filename);

        // Handle name conflicts
        if dest.exists() {
            let stem = src.file_stem().unwrap_or_default().to_string_lossy().to_string();
            let ext = src.extension().map(|e| e.to_string_lossy().to_string()).unwrap_or_default();
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

        if fs::rename(src, &dest).is_ok() || fs::copy(src, &dest).map(|_| fs::remove_file(src)).is_ok() {
            deleted.push(path.clone());

            // Also move XMP sidecar if exists
            let xmp_src = Path::new(path).with_extension("xmp");
            if xmp_src.exists() {
                let xmp_dest = dest.with_extension("xmp");
                let _ = fs::rename(&xmp_src, &xmp_dest);
            }
        }
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
                let name = path.file_name().unwrap_or_default().to_string_lossy().to_string();
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
    nodes.sort_by(|a, b| a.name.to_lowercase().cmp(&b.name.to_lowercase()));
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
