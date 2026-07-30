use crate::models::image_info::ImageInfo;
use rusqlite::{params, Connection, Result};
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

fn get_db_path() -> PathBuf {
    if cfg!(test) {
        let thread_id = format!("{:?}", std::thread::current().id())
            .chars()
            .filter(|c| c.is_alphanumeric())
            .collect::<String>();
        let temp_file = std::env::temp_dir().join(format!(
            "wiphoto_test_{}_{}.db",
            std::process::id(),
            thread_id
        ));
        return temp_file;
    }
    let dir = dirs::home_dir().unwrap_or_default().join(".wiphoto");
    let _ = fs::create_dir_all(&dir);
    dir.join("library.db")
}

use once_cell::sync::Lazy;

#[cfg(not(test))]
use r2d2::Pool;
#[cfg(not(test))]
use r2d2_sqlite::SqliteConnectionManager;

#[cfg(test)]
fn open_conn_raw() -> Result<Connection> {
    let path = get_db_path();
    let conn = Connection::open(path)?;
    if let Err(e) = conn.busy_timeout(std::time::Duration::from_millis(5000)) {
        log::warn!("Failed to set SQLite busy timeout: {}", e);
    }
    if let Err(e) = conn.pragma_update(None, "journal_mode", "WAL") {
        log::warn!("Failed to set SQLite journal mode to WAL: {}", e);
    }
    if let Err(e) = conn.pragma_update(None, "synchronous", "NORMAL") {
        log::warn!("Failed to set SQLite synchronous mode: {}", e);
    }
    Ok(conn)
}

#[cfg(not(test))]
static DB_POOL: Lazy<Pool<SqliteConnectionManager>> = Lazy::new(|| {
    let path = get_db_path();
    let manager = SqliteConnectionManager::file(path).with_init(|c| {
        c.busy_timeout(std::time::Duration::from_millis(5000))?;
        c.pragma_update(None, "journal_mode", "WAL")?;
        c.pragma_update(None, "synchronous", "NORMAL")?;
        Ok(())
    });
    Pool::builder()
        .max_size(10)
        .build(manager)
        .expect("Failed to create SQLite connection pool")
});

#[cfg(test)]
static TEST_CONNS: Lazy<Mutex<HashMap<std::thread::ThreadId, Connection>>> =
    Lazy::new(|| Mutex::new(HashMap::new()));

pub fn with_db<F, R>(f: F) -> Result<R>
where
    F: FnOnce(&mut Connection) -> Result<R>,
{
    #[cfg(test)]
    {
        let tid = std::thread::current().id();
        let mut map = TEST_CONNS.lock();
        if !map.contains_key(&tid) {
            let conn = open_conn_raw()?;
            map.insert(tid, conn);
        }
        let conn = map
            .get_mut(&tid)
            .ok_or_else(|| rusqlite::Error::QueryReturnedNoRows)?;
        f(conn)
    }
    #[cfg(not(test))]
    {
        let mut conn = DB_POOL.get().map_err(|e| {
            rusqlite::Error::SqliteFailure(
                rusqlite::ffi::Error::new(rusqlite::ffi::SQLITE_ERROR),
                Some(e.to_string()),
            )
        })?;
        f(&mut conn)
    }
}

/// Initialize the SQLite database and create the images table if not exists
pub fn init_db() -> Result<()> {
    with_db(|conn| {
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
                modified_time INTEGER NOT NULL,
                embedding TEXT
            )",
            [],
        )?;
        let _ = conn.execute(
            "ALTER TABLE images ADD COLUMN modified_time INTEGER DEFAULT 0",
            [],
        );
        let _ = conn.execute("ALTER TABLE images ADD COLUMN embedding TEXT", []);
        Ok(())
    })
}

/// Store a 512-dim embedding for an image path in SQLite
pub fn save_image_embedding(path: &str, embedding: &[f32]) -> Result<()> {
    with_db(|conn| {
        let serialized = serde_json::to_string(embedding).unwrap_or_else(|_| "[]".to_string());
        conn.execute(
            "UPDATE images SET embedding = ? WHERE path = ?",
            params![serialized, path],
        )?;
        Ok(())
    })
}

/// Retrieve stored embedding for an image path
pub fn get_image_embedding(path: &str) -> Result<Option<Vec<f32>>> {
    with_db(|conn| {
        let mut stmt = conn.prepare("SELECT embedding FROM images WHERE path = ?")?;
        let mut rows = stmt.query(params![path])?;
        if let Some(row) = rows.next()? {
            let val: Option<String> = row.get(0)?;
            if let Some(json_str) = val {
                if let Ok(vec) = serde_json::from_str::<Vec<f32>>(&json_str) {
                    if !vec.is_empty() {
                        return Ok(Some(vec));
                    }
                }
            }
        }
        Ok(None)
    })
}

/// Perform vector similarity search across all stored images using CLIP query embedding
pub fn search_clip_semantic_db(query_vec: &[f32], limit: usize) -> Result<Vec<(ImageInfo, f32)>> {
    let images_with_emb = with_db(|conn| {
        let mut stmt = conn.prepare(
            "SELECT 
                path, filename, thumbnail, phash, sharpness, is_best_in_group, group_id,
                faces_count, animals_count, gps_latitude, gps_longitude, aspect_ratio,
                camera_model, date_taken, rating, file_size, width, height,
                animal_species, color_label, flag_status, tags, is_video, is_raw, embedding
            FROM images",
        )?;

        let rows = stmt.query_map([], |row| {
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
            let embedding_str: Option<String> = row.get(24)?;

            let gps_location = match (gps_latitude, gps_longitude) {
                (Some(lat), Some(lon)) => Some((lat, lon)),
                _ => None,
            };

            let animal_species: Vec<String> =
                serde_json::from_str(&animal_species_str).unwrap_or_default();
            let tags: Vec<String> = serde_json::from_str(&tags_str).unwrap_or_default();
            let embedding: Option<Vec<f32>> = embedding_str
                .as_deref()
                .and_then(|s| serde_json::from_str::<Vec<f32>>(s).ok())
                .filter(|v| !v.is_empty());

            Ok((
                ImageInfo {
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
                },
                embedding,
            ))
        })?;

        let mut list = Vec::new();
        for item in rows.flatten() {
            list.push(item);
        }
        Ok(list)
    })?;

    let mut ranked = Vec::new();
    for (info, emb_opt) in images_with_emb {
        let img_vec = match emb_opt {
            Some(v) => v,
            None => crate::onnx::extract_image_embedding(std::path::Path::new(&info.path)),
        };
        let score = crate::onnx::cosine_similarity(query_vec, &img_vec);
        if score.is_finite() {
            ranked.push((info, score));
        }
    }

    ranked.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
    if limit > 0 && ranked.len() > limit {
        ranked.truncate(limit);
    }

    Ok(ranked)
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
        if let Err(ref e) = save_res {
            println!("DB Save Error: {:?}", e);
        }
        assert!(save_res.is_ok());

        let cache = get_folder_mtimes(folder).expect("Failed to get cache");

        // Assert
        assert!(cache.contains_key("C:/test_folder/img1.jpg"));
        let cached_mtime = cache.get("C:/test_folder/img1.jpg").unwrap();
        assert_eq!(*cached_mtime, 123456u64);

        // Test embedding save and search
        let test_emb = vec![0.1f32; crate::onnx::EMBEDDING_DIM];
        let save_emb_res = save_image_embedding("C:/test_folder/img1.jpg", &test_emb);
        assert!(save_emb_res.is_ok());

        let fetched_emb = get_image_embedding("C:/test_folder/img1.jpg").unwrap();
        assert!(fetched_emb.is_some());
        assert_eq!(fetched_emb.unwrap().len(), crate::onnx::EMBEDDING_DIM);

        let search_res = search_clip_semantic_db(&test_emb, 10).unwrap();
        assert!(!search_res.is_empty());
        assert_eq!(search_res[0].0.path, "C:/test_folder/img1.jpg");

        // Delete
        let del_res = delete_images_batch(&["C:/test_folder/img1.jpg".to_string()]);
        assert!(del_res.is_ok());

        let cache_after = get_folder_mtimes(folder).unwrap();
        assert!(!cache_after.contains_key("C:/test_folder/img1.jpg"));
    }
}

/// Retrieve all cached images for a given folder path
pub fn get_folder_mtimes(folder: &str) -> Result<HashMap<String, u64>> {
    with_db(|conn| {
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
        for (path_str, val) in rows.flatten() {
            cache.insert(path_str, val);
        }
        Ok(cache)
    })
}

pub fn get_images_by_paths(paths: &[String]) -> Result<Vec<ImageInfo>> {
    let _ = init_db();
    with_db(|conn| {
        let mut results = Vec::new();
        if paths.is_empty() {
            let query = "SELECT 
                path, filename, thumbnail, phash, sharpness, is_best_in_group, group_id,
                faces_count, animals_count, gps_latitude, gps_longitude, aspect_ratio,
                camera_model, date_taken, rating, file_size, width, height,
                animal_species, color_label, flag_status, tags, is_video, is_raw
            FROM images";

            let mut stmt = conn.prepare(query)?;
            let rows = stmt.query_map([], |row| {
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

                let animal_species: Vec<String> =
                    serde_json::from_str(&animal_species_str).unwrap_or_default();
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

            for info in rows.flatten() {
                results.push(info);
            }
            return Ok(results);
        }
        for chunk in paths.chunks(500) {
            let placeholders: Vec<String> = (0..chunk.len()).map(|_| "?".to_string()).collect();
            let query = format!(
                "SELECT 
                path, filename, thumbnail, phash, sharpness, is_best_in_group, group_id,
                faces_count, animals_count, gps_latitude, gps_longitude, aspect_ratio,
                camera_model, date_taken, rating, file_size, width, height,
                animal_species, color_label, flag_status, tags, is_video, is_raw
            FROM images WHERE path IN ({})",
                placeholders.join(", ")
            );

            let mut stmt = conn.prepare(&query)?;

            let params: Vec<&dyn rusqlite::ToSql> =
                chunk.iter().map(|s| s as &dyn rusqlite::ToSql).collect();

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

                let animal_species: Vec<String> =
                    serde_json::from_str(&animal_species_str).unwrap_or_default();
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

            for info in rows.flatten() {
                results.push(info);
            }
        }

        Ok(results)
    })
}

/// Batch insert/replace images inside a transaction
pub fn save_images_batch(images: &[(&ImageInfo, u64)]) -> Result<()> {
    if images.is_empty() {
        return Ok(());
    }
    let _ = init_db();
    with_db(|conn| {
        let tx = conn.transaction()?;

        {
            let mut stmt = tx.prepare(
                "INSERT OR REPLACE INTO images (
                    path, filename, thumbnail, phash, sharpness, is_best_in_group, group_id,
                    faces_count, animals_count, gps_latitude, gps_longitude, aspect_ratio,
                    camera_model, date_taken, rating, file_size, width, height,
                    animal_species, color_label, flag_status, tags, is_video, is_raw, modified_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            )?;

            for (info, mtime) in images {
                let gps_lat = info.gps_location.map(|g| g.0);
                let gps_lon = info.gps_location.map(|g| g.1);
                let animal_species_str = serde_json::to_string(&info.animal_species)
                    .unwrap_or_else(|_| "[]".to_string());
                let tags_str =
                    serde_json::to_string(&info.tags).unwrap_or_else(|_| "[]".to_string());

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
    })
}

/// Batch delete images inside a transaction
pub fn delete_images_batch(paths: &[String]) -> Result<()> {
    if paths.is_empty() {
        return Ok(());
    }
    with_db(|conn| {
        let tx = conn.transaction()?;

        {
            let mut stmt = tx.prepare("DELETE FROM images WHERE path = ?")?;
            for p in paths {
                stmt.execute(params![p])?;
            }
        }

        tx.commit()?;
        Ok(())
    })
}
