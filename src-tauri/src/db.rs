use crate::models::image_info::ImageInfo;
use rusqlite::{params, Connection, Result};
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

fn get_db_path() -> PathBuf {
    let dir = dirs::home_dir().unwrap_or_default().join(".wiphoto");
    let _ = fs::create_dir_all(&dir);
    dir.join("library.db")
}

/// Initialize the SQLite database and create the images table if not exists
pub fn init_db() -> Result<()> {
    let path = get_db_path();
    let conn = Connection::open(path)?;
    conn.execute(
        "CREATE TABLE IF NOT EXISTS images (
            path TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            thumbnail TEXT NOT NULL,
            phash TEXT,
            sharpness REAL NOT NULL,
            is_best_in_group INTEGER NOT NULL,
            group_id TEXT,
            faces_count INTEGER NOT NULL,
            animals_count INTEGER NOT NULL,
            gps_latitude REAL,
            gps_longitude REAL,
            aspect_ratio REAL NOT NULL,
            camera_model TEXT NOT NULL,
            date_taken TEXT NOT NULL,
            rating INTEGER NOT NULL,
            file_size INTEGER NOT NULL,
            width INTEGER NOT NULL,
            height INTEGER NOT NULL,
            animal_species TEXT NOT NULL,
            color_label TEXT NOT NULL,
            flag_status TEXT NOT NULL,
            tags TEXT NOT NULL,
            is_video INTEGER NOT NULL,
            is_raw INTEGER NOT NULL,
            modified_time INTEGER NOT NULL
        )",
        [],
    )?;
    Ok(())
}

/// Retrieve all cached images for a given folder path
pub fn get_folder_mtimes(folder: &str) -> Result<HashMap<String, u64>> {
    let path = get_db_path();
    let conn = Connection::open(path)?;

    // We fetch everything matching the folder path prefix to support recursive and flat lookups
    let folder_prefix = if folder.ends_with('/') || folder.ends_with('\\') {
        folder.to_string()
    } else if folder.contains('\\') {
        format!("{}\\", folder)
    } else {
        format!("{}/", folder)
    };

    let mut stmt = conn.prepare("SELECT path, modified_time FROM images WHERE path LIKE ?")?;
    let query_param = format!("{}%", folder_prefix);
    
    let rows = stmt.query_map(params![query_param], |row| {
        let path_str: String = row.get(0)?;
        let modified_time: u64 = row.get(1)?;
        Ok((path_str, modified_time))
    })?;

    let mut cache = HashMap::new();
    for row in rows {
        if let Ok((path_str, val)) = row {
            cache.insert(path_str, val);
        }
    }
    Ok(cache)
}

pub fn get_images_by_paths(paths: &[String]) -> Result<Vec<ImageInfo>> {
    if paths.is_empty() {
        return Ok(Vec::new());
    }
    let db_path = get_db_path();
    let conn = Connection::open(db_path)?;
    
    let mut results = Vec::new();
    for chunk in paths.chunks(500) {
        let placeholders: Vec<String> = (0..chunk.len()).map(|_| "?".to_string()).collect();
        let query = format!("SELECT 
            path, filename, thumbnail, phash, sharpness, is_best_in_group, group_id,
            faces_count, animals_count, gps_latitude, gps_longitude, aspect_ratio,
            camera_model, date_taken, rating, file_size, width, height,
            animal_species, color_label, flag_status, tags, is_video, is_raw
        FROM images WHERE path IN ({})", placeholders.join(", "));
        
        let mut stmt = conn.prepare(&query)?;
        
        let params: Vec<&dyn rusqlite::ToSql> = chunk.iter().map(|s| s as &dyn rusqlite::ToSql).collect();
        
        let rows = stmt.query_map(&params[..], |row| {
            let path_str: String = row.get(0)?;
            let filename: String = row.get(1)?;
            let thumbnail: String = row.get(2)?;
            let phash: Option<String> = row.get(3)?;
            let sharpness: f64 = row.get(4)?;
            let is_best_in_group_int: i32 = row.get(5)?;
            let group_id: Option<String> = row.get(6)?;
            let faces_count: u32 = row.get(7)?;
            let animals_count: u32 = row.get(8)?;
            let gps_latitude: Option<f64> = row.get(9)?;
            let gps_longitude: Option<f64> = row.get(10)?;
            let aspect_ratio: f64 = row.get(11)?;
            let camera_model: String = row.get(12)?;
            let date_taken: String = row.get(13)?;
            let rating: u8 = row.get(14)?;
            let file_size: u64 = row.get(15)?;
            let width: u32 = row.get(16)?;
            let height: u32 = row.get(17)?;
            let animal_species_str: String = row.get(18)?;
            let color_label: String = row.get(19)?;
            let flag_status: String = row.get(20)?;
            let tags_str: String = row.get(21)?;
            let is_video_int: i32 = row.get(22)?;
            let is_raw_int: i32 = row.get(23)?;

            let gps_location = match (gps_latitude, gps_longitude) {
                (Some(lat), Some(lon)) => Some((lat, lon)),
                _ => None,
            };

            let animal_species: Vec<String> = serde_json::from_str(&animal_species_str).unwrap_or_default();
            let tags: Vec<String> = serde_json::from_str(&tags_str).unwrap_or_default();

            Ok(ImageInfo {
                path: path_str,
                filename,
                thumbnail,
                phash,
                sharpness,
                is_best_in_group: is_best_in_group_int != 0,
                group_id,
                faces_count,
                animals_count,
                gps_location,
                aspect_ratio,
                camera_model,
                date_taken,
                rating,
                file_size,
                width,
                height,
                animal_species,
                color_label,
                flag_status,
                tags,
                is_video: is_video_int != 0,
                is_raw: is_raw_int != 0,
            })
        })?;
        
        for row in rows {
            if let Ok(info) = row {
                results.push(info);
            }
        }
    }
    
    Ok(results)
}

/// Batch insert/replace images inside a transaction
pub fn save_images_batch(images: &[(&ImageInfo, u64)]) -> Result<()> {
    if images.is_empty() {
        return Ok(());
    }
    let path = get_db_path();
    let mut conn = Connection::open(path)?;
    let tx = conn.transaction()?;

    {
        let mut stmt = tx.prepare(
            "INSERT OR REPLACE INTO images (
                path, filename, thumbnail, phash, sharpness, is_best_in_group, group_id,
                faces_count, animals_count, gps_latitude, gps_longitude, aspect_ratio,
                camera_model, date_taken, rating, file_size, width, height,
                animal_species, color_label, flag_status, tags, is_video, is_raw, modified_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )?;

        for (info, mtime) in images {
            let gps_lat = info.gps_location.map(|g| g.0);
            let gps_lon = info.gps_location.map(|g| g.1);
            let animal_species_str = serde_json::to_string(&info.animal_species).unwrap_or_else(|_| "[]".to_string());
            let tags_str = serde_json::to_string(&info.tags).unwrap_or_else(|_| "[]".to_string());

            stmt.execute(params![
                info.path,
                info.filename,
                info.thumbnail,
                info.phash,
                info.sharpness,
                if info.is_best_in_group { 1 } else { 0 },
                info.group_id,
                info.faces_count,
                info.animals_count,
                gps_lat,
                gps_lon,
                info.aspect_ratio,
                info.camera_model,
                info.date_taken,
                info.rating,
                info.file_size,
                info.width,
                info.height,
                animal_species_str,
                info.color_label,
                info.flag_status,
                tags_str,
                if info.is_video { 1 } else { 0 },
                if info.is_raw { 1 } else { 0 },
                mtime
            ])?;
        }
    }

    tx.commit()?;
    Ok(())
}

/// Batch delete images inside a transaction
pub fn delete_images_batch(paths: &[String]) -> Result<()> {
    if paths.is_empty() {
        return Ok(());
    }
    let path = get_db_path();
    let mut conn = Connection::open(path)?;
    let tx = conn.transaction()?;

    {
        let mut stmt = tx.prepare("DELETE FROM images WHERE path = ?")?;
        for p in paths {
            stmt.execute(params![p])?;
        }
    }

    tx.commit()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_init_and_cache_db() {
        // Arrange
        let _ = init_db();
        let folder = "C:/test_folder";
        let info1 = ImageInfo {
            path: "C:/test_folder/img1.jpg".into(),
            filename: "img1.jpg".into(),
            thumbnail: "dummy_thumb".into(),
            phash: Some("abcdef".into()),
            sharpness: 0.8,
            is_best_in_group: true,
            group_id: Some("g1".into()),
            faces_count: 1,
            animals_count: 0,
            gps_location: Some((50.0, 10.0)),
            aspect_ratio: 1.5,
            camera_model: "Nikon".into(),
            date_taken: "2024:01:01".into(),
            rating: 4,
            file_size: 1024,
            width: 600,
            height: 400,
            animal_species: vec![],
            color_label: "red".into(),
            flag_status: "picked".into(),
            tags: vec!["land".into()],
            is_video: false,
            is_raw: false,
        };

        // Act
        let save_res = save_images_batch(&[(&info1, 123456u64)]);
        assert!(save_res.is_ok());

        let cache = get_folder_cache(folder).expect("Failed to get cache");

        // Assert
        assert!(cache.contains_key("C:/test_folder/img1.jpg"));
        let (cached_info, cached_mtime) = cache.get("C:/test_folder/img1.jpg").unwrap();
        assert_eq!(cached_info.filename, "img1.jpg");
        assert_eq!(cached_info.rating, 4);
        assert_eq!(cached_info.tags, vec!["land".to_string()]);
        assert_eq!(*cached_mtime, 123456u64);

        // Delete
        let del_res = delete_images_batch(&["C:/test_folder/img1.jpg".to_string()]);
        assert!(del_res.is_ok());

        let cache_after = get_folder_cache(folder).unwrap();
        assert!(!cache_after.contains_key("C:/test_folder/img1.jpg"));
    }
}
