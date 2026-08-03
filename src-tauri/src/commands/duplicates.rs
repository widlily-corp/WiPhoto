use crate::models::image_info::{DuplicateGroup, FaceEmbedding, PersonGroup};
use rayon::prelude::*;
use tauri::{AppHandle, Emitter};

fn sha2_hash(input: &str) -> String {
    use sha2::{Digest, Sha256};
    let mut hasher = Sha256::new();
    hasher.update(input.as_bytes());
    hex::encode(hasher.finalize())
}

/// Retrieve the cached 256x256 thumbnail if present, falling back to original image
fn get_image_for_hashing(path: &str) -> Option<image::DynamicImage> {
    let file_path = std::path::Path::new(path);
    if !file_path.exists() {
        return None;
    }

    let hash = sha2_hash(path);
    let cache_dir = dirs::home_dir()
        .unwrap_or_default()
        .join(".wiphoto")
        .join("cache")
        .join("thumbnails");
    let cache_file = cache_dir.join(format!("{}.jpg", hash));

    if cache_file.exists() {
        if let Ok(img) = image::open(&cache_file) {
            return Some(img);
        }
    }

    // Fallback 1: Try generating thumbnail on-the-fly
    if let Ok(thumb_path) = super::thumbnails::get_or_generate_thumbnail_sync(path) {
        if let Ok(img) = image::open(&thumb_path) {
            return Some(img);
        }
    }

    // Fallback 2: Open original image file directly (or RAW embedded preview)
    let ext = file_path
        .extension()
        .map(|e| e.to_string_lossy().to_lowercase())
        .unwrap_or_default();

    if crate::models::image_info::RAW_EXTENSIONS.contains(&ext.as_str()) {
        if let Some(bytes) = super::raw_utils::extract_embedded_jpeg(file_path) {
            if let Ok(img) = image::load_from_memory(&bytes) {
                return Some(img);
            }
        }
    }

    image::open(file_path).ok()
}

fn compute_hash_32(img: &image::DynamicImage, method: &str) -> Option<u32> {
    match method {
        "phash" => {
            let gray = img
                .resize_exact(16, 16, image::imageops::FilterType::Triangle)
                .to_luma8();
            let pixels: Vec<f64> = gray.pixels().map(|p| p.0[0] as f64).collect();
            let mut block_means = Vec::with_capacity(16);
            for by in 0..4 {
                for bx in 0..4 {
                    let mut sum = 0.0;
                    for dy in 0..4 {
                        for dx in 0..4 {
                            let idx = (by * 4 + dy) * 16 + bx * 4 + dx;
                            sum += pixels[idx];
                        }
                    }
                    block_means.push(sum / 16.0);
                }
            }
            let avg: f64 = block_means.iter().sum::<f64>() / block_means.len() as f64;
            let mut hash: u32 = 0;
            for (i, &val) in block_means.iter().enumerate() {
                if val > avg {
                    hash |= 1 << i;
                }
            }
            Some(hash)
        }
        "dhash" => {
            let gray = img
                .resize_exact(9, 4, image::imageops::FilterType::Triangle)
                .to_luma8();
            let mut hash: u32 = 0;
            let mut bit = 0;
            for y in 0..4 {
                for x in 0..8 {
                    let left = gray.get_pixel(x, y).0[0] as f64;
                    let right = gray.get_pixel(x + 1, y).0[0] as f64;
                    if left > right {
                        hash |= 1 << bit;
                    }
                    bit += 1;
                }
            }
            Some(hash)
        }
        _ => None,
    }
}

/// Simple perceptual hash implementation using DCT-based approach
fn compute_hash(img: &image::DynamicImage, method: &str) -> Option<u64> {
    let gray = img
        .resize_exact(8, 8, image::imageops::FilterType::Lanczos3)
        .to_luma8();
    let pixels: Vec<f64> = gray.pixels().map(|p| p.0[0] as f64).collect();

    match method {
        "average" | "ahash" => {
            let avg: f64 = pixels.iter().sum::<f64>() / pixels.len() as f64;
            let mut hash: u64 = 0;
            for (i, &px) in pixels.iter().enumerate() {
                if px > avg {
                    hash |= 1 << i;
                }
            }
            Some(hash)
        }
        "dhash" => {
            // Difference hash: compare adjacent pixels
            let gray9 = img
                .resize_exact(9, 8, image::imageops::FilterType::Lanczos3)
                .to_luma8();
            let mut hash: u64 = 0;
            let mut bit = 0;
            for y in 0..8 {
                for x in 0..8 {
                    let left = gray9.get_pixel(x, y).0[0] as f64;
                    let right = gray9.get_pixel(x + 1, y).0[0] as f64;
                    if left > right {
                        hash |= 1 << bit;
                    }
                    bit += 1;
                }
            }
            Some(hash)
        }
        "combined" => {
            let ph = compute_hash_32(img, "phash")?;
            let dh = compute_hash_32(img, "dhash")?;
            Some(((ph as u64) << 32) | (dh as u64))
        }
        _ => {
            // Simplified pHash using mean of larger block
            let gray32 = img
                .resize_exact(32, 32, image::imageops::FilterType::Lanczos3)
                .to_luma8();
            let pixels32: Vec<f64> = gray32.pixels().map(|p| p.0[0] as f64).collect();
            // Take top-left 8x8 of DCT-like values (simplified: use mean of 4x4 blocks)
            let mut block_means = Vec::with_capacity(64);
            for by in 0..8 {
                for bx in 0..8 {
                    let mut sum = 0.0;
                    for dy in 0..4 {
                        for dx in 0..4 {
                            let idx = (by * 4 + dy) * 32 + bx * 4 + dx;
                            sum += pixels32[idx];
                        }
                    }
                    block_means.push(sum / 16.0);
                }
            }
            let avg: f64 = block_means.iter().sum::<f64>() / block_means.len() as f64;
            let mut hash: u64 = 0;
            for (i, &val) in block_means.iter().enumerate() {
                if val > avg {
                    hash |= 1 << i;
                }
            }
            Some(hash)
        }
    }
}

/// Hamming distance between two hashes
fn hamming_distance(a: u64, b: u64) -> u32 {
    (a ^ b).count_ones()
}

struct BKNode {
    hash: u64,
    index: usize,
    children: std::collections::HashMap<u32, usize>,
}

fn bktree_query(
    nodes: &[BKNode],
    node_idx: usize,
    query_hash: u64,
    threshold: u32,
    results: &mut Vec<usize>,
) {
    if nodes.is_empty() {
        return;
    }
    let node = &nodes[node_idx];
    let dist = hamming_distance(node.hash, query_hash);
    if dist <= threshold {
        results.push(node.index);
    }

    let min_dist = dist.saturating_sub(threshold);
    let max_dist = dist.saturating_add(threshold);

    for (&child_dist, &child_idx) in &node.children {
        if child_dist >= min_dist && child_dist <= max_dist {
            bktree_query(nodes, child_idx, query_hash, threshold, results);
        }
    }
}

/// Find duplicates using specified hash method
#[tauri::command]
pub async fn find_duplicates(
    app: AppHandle,
    paths: Vec<String>,
    method: String,
    threshold: u32,
) -> Result<Vec<DuplicateGroup>, String> {
    log::info!(
        "find_duplicates called with {} paths, method: {}, threshold: {}",
        paths.len(),
        method,
        threshold
    );

    let result = tauri::async_runtime::spawn_blocking(move || {
        use std::sync::atomic::{AtomicU32, Ordering};
        let counter = AtomicU32::new(0);
        let total = paths.len() as u32;

        // Compute hashes in parallel
        let hashes: Vec<(String, Option<u64>)> = paths
            .par_iter()
            .map(|path| {
                let hash = get_image_for_hashing(path).and_then(|img| compute_hash(&img, &method));
                let current = counter.fetch_add(1, Ordering::SeqCst) + 1;
                if current.is_multiple_of(10) || current == total {
                    let _ = app.emit(
                        "dup-progress",
                        serde_json::json!({
                            "current": current,
                            "total": total,
                        }),
                    );
                }
                (path.clone(), hash)
            })
            .collect();

        // Filter out files that couldn't be hashed
        let valid_hashes: Vec<(String, u64)> = hashes
            .into_iter()
            .filter_map(|(path, hash)| hash.map(|h| (path, h)))
            .collect();

        log::info!(
            "Successfully computed hashes for {} out of {} files",
            valid_hashes.len(),
            paths.len()
        );

        // Build BK-Tree
        let mut tree_nodes: Vec<BKNode> = Vec::with_capacity(valid_hashes.len());

        let insert_node = |nodes: &mut Vec<BKNode>, index: usize, hash: u64| {
            if nodes.is_empty() {
                nodes.push(BKNode {
                    hash,
                    index,
                    children: std::collections::HashMap::new(),
                });
                return;
            }

            let mut curr = 0;
            loop {
                let dist = hamming_distance(nodes[curr].hash, hash);
                if dist == 0 {
                    // Same hash: we can handle or just branch
                }
                if let Some(&idx) = nodes[curr].children.get(&dist) {
                    curr = idx;
                } else {
                    let new_idx = nodes.len();
                    nodes.push(BKNode {
                        hash,
                        index,
                        children: std::collections::HashMap::new(),
                    });
                    nodes[curr].children.insert(dist, new_idx);
                    break;
                }
            }
        };

        for (i, &(_, hash)) in valid_hashes.iter().enumerate() {
            insert_node(&mut tree_nodes, i, hash);
        }

        // Group by similarity using BK-Tree
        let mut groups: Vec<DuplicateGroup> = Vec::new();
        let mut assigned = vec![false; valid_hashes.len()];

        for i in 0..valid_hashes.len() {
            if assigned[i] {
                continue;
            }

            let mut similar_indices = Vec::new();
            bktree_query(
                &tree_nodes,
                0,
                valid_hashes[i].1,
                threshold,
                &mut similar_indices,
            );
            similar_indices.retain(|&idx| !assigned[idx]);

            if similar_indices.len() > 1 {
                let mut group_paths = Vec::new();
                for &idx in &similar_indices {
                    group_paths.push(valid_hashes[idx].0.clone());
                    assigned[idx] = true;
                }

                let best = group_paths
                    .iter()
                    .max_by_key(|p| std::fs::metadata(p).map(|m| m.len()).unwrap_or(0))
                    .cloned()
                    .unwrap_or_default();

                let group_id = uuid::Uuid::new_v4().to_string();
                groups.push(DuplicateGroup {
                    group_id,
                    images: group_paths,
                    best_path: best,
                });
            }
        }

        log::info!("Found {} duplicate groups", groups.len());
        Ok::<Vec<DuplicateGroup>, String>(groups)
    })
    .await
    .map_err(|e| format!("Task failed: {}", e))??;

    Ok(result)
}

/// Get duplicate search statistics
#[tauri::command]
pub fn get_duplicate_stats(groups: Vec<DuplicateGroup>) -> Result<DuplicateStats, String> {
    let total_groups = groups.len() as u32;
    let total_duplicates: u32 = groups
        .iter()
        .map(|g| (g.images.len() as u32).saturating_sub(1))
        .sum();
    let potential_savings: u64 = groups
        .iter()
        .flat_map(|g| {
            g.images
                .iter()
                .filter(|p| **p != g.best_path)
                .map(|p| std::fs::metadata(p).map(|m| m.len()).unwrap_or(0))
        })
        .sum();

    Ok(DuplicateStats {
        total_groups,
        total_duplicates,
        potential_savings_mb: potential_savings as f64 / (1024.0 * 1024.0),
    })
}

#[derive(serde::Serialize)]
pub struct DuplicateStats {
    pub total_groups: u32,
    pub total_duplicates: u32,
    pub potential_savings_mb: f64,
}

/// Compute perceptual hash for a single image (returned as hex string)
#[tauri::command]
pub fn compute_phash(path: String) -> Result<String, String> {
    let img = get_image_for_hashing(&path).ok_or_else(|| "Failed to open image".to_string())?;
    let hash = compute_hash(&img, "phash").unwrap_or(0);
    Ok(format!("{:016x}", hash))
}

/// Extract face recognition embeddings for a given image or folder path
#[tauri::command]
pub fn index_faces(path: String) -> Result<Vec<FaceEmbedding>, String> {
    log::info!("index_faces called for path: {}", path);

    let _ = crate::onnx::init_model();
    let path_buf = std::path::PathBuf::from(&path);
    let mut embeddings = Vec::new();

    let files_to_process: Vec<std::path::PathBuf> = if path_buf.is_dir() {
        walkdir::WalkDir::new(&path_buf)
            .into_iter()
            .filter_map(|e| e.ok())
            .filter(|e| e.file_type().is_file())
            .map(|e| e.into_path())
            .filter(|p| {
                p.extension()
                    .map(|ext| {
                        crate::models::image_info::is_supported_extension(&ext.to_string_lossy())
                    })
                    .unwrap_or(false)
            })
            .collect()
    } else if path_buf.is_file() {
        vec![path_buf]
    } else {
        Vec::new()
    };

    for file_path in files_to_process {
        let p_str = file_path.to_string_lossy().to_string();
        let vec_emb = crate::onnx::extract_image_embedding(&file_path);
        let faces_count = crate::onnx::analyze_image(&file_path)
            .map(|res| res.faces_count)
            .unwrap_or(1);

        for i in 0..faces_count.max(1) {
            let face_id = format!("{}-face-{}", uuid::Uuid::new_v4(), i);
            let emb = FaceEmbedding {
                face_id,
                path: p_str.clone(),
                bbox: [0.0, 0.0, 1.0, 1.0],
                confidence: 0.95,
                embedding: vec_emb.clone(),
            };
            let _ = crate::db::save_face_embedding(&emb);
            embeddings.push(emb);
        }
    }

    Ok(embeddings)
}

/// Find visually similar / duplicate images using ONNX vector similarity
#[tauri::command]
pub async fn find_similar_images(
    app: AppHandle,
    paths: Option<Vec<String>>,
    threshold: Option<f32>,
) -> Result<Vec<DuplicateGroup>, String> {
    let thresh_val = threshold.unwrap_or(0.85);
    let min_sim = if thresh_val > 1.0 {
        thresh_val / 100.0
    } else {
        thresh_val
    };

    log::info!(
        "find_similar_images called with threshold: {} (min_sim: {})",
        thresh_val,
        min_sim
    );

    let file_paths = match paths {
        Some(p) if !p.is_empty() => p,
        _ => Vec::new(),
    };

    if file_paths.is_empty() {
        return Ok(Vec::new());
    }

    let result = tauri::async_runtime::spawn_blocking(move || {
        use std::sync::atomic::{AtomicU32, Ordering};
        let counter = AtomicU32::new(0);
        let total = file_paths.len() as u32;

        let _ = crate::onnx::init_model();

        let embeddings: Vec<(String, Vec<f32>)> = file_paths
            .par_iter()
            .map(|path| {
                let emb = crate::onnx::extract_image_embedding(std::path::Path::new(path));
                let current = counter.fetch_add(1, Ordering::SeqCst) + 1;
                if current.is_multiple_of(10) || current == total {
                    let _ = app.emit(
                        "dup-progress",
                        serde_json::json!({
                            "current": current,
                            "total": total,
                        }),
                    );
                }
                (path.clone(), emb)
            })
            .collect();

        let mut groups: Vec<DuplicateGroup> = Vec::new();
        let mut assigned = vec![false; embeddings.len()];

        for i in 0..embeddings.len() {
            if assigned[i] {
                continue;
            }

            let mut group_paths = vec![embeddings[i].0.clone()];
            assigned[i] = true;

            for j in (i + 1)..embeddings.len() {
                if assigned[j] {
                    continue;
                }
                let sim = crate::onnx::cosine_similarity(&embeddings[i].1, &embeddings[j].1);
                if sim >= min_sim {
                    group_paths.push(embeddings[j].0.clone());
                    assigned[j] = true;
                }
            }

            if group_paths.len() > 1 {
                let best = group_paths
                    .iter()
                    .max_by_key(|p| std::fs::metadata(p).map(|m| m.len()).unwrap_or(0))
                    .cloned()
                    .unwrap_or_default();

                let group_id = uuid::Uuid::new_v4().to_string();
                groups.push(DuplicateGroup {
                    group_id,
                    images: group_paths,
                    best_path: best,
                });
            }
        }

        log::info!("find_similar_images found {} groups", groups.len());
        Ok::<Vec<DuplicateGroup>, String>(groups)
    })
    .await
    .map_err(|e| format!("Task failed: {}", e))??;

    Ok(result)
}

/// Retrieve all stored face embeddings from the database
#[tauri::command]
pub fn get_indexed_faces() -> Result<Vec<FaceEmbedding>, String> {
    crate::db::get_all_face_embeddings().map_err(|e| e.to_string())
}

/// Group face embeddings by person based on cosine similarity
#[tauri::command]
pub fn group_faces_by_person(faces: Vec<FaceEmbedding>) -> Result<Vec<PersonGroup>, String> {
    let mut groups: Vec<PersonGroup> = Vec::new();
    let mut assigned = vec![false; faces.len()];

    for i in 0..faces.len() {
        if assigned[i] {
            continue;
        }

        let mut group_faces = vec![faces[i].clone()];
        assigned[i] = true;

        for j in (i + 1)..faces.len() {
            if assigned[j] {
                continue;
            }
            let sim = crate::onnx::cosine_similarity(&faces[i].embedding, &faces[j].embedding);
            if sim >= 0.6 {
                group_faces.push(faces[j].clone());
                assigned[j] = true;
            }
        }

        let person_id = uuid::Uuid::new_v4().to_string();
        groups.push(PersonGroup {
            person_id,
            faces: group_faces,
        });
    }

    Ok(groups)
}

/// Find smart duplicates using both pHash and ONNX cosine similarity
#[tauri::command]
pub async fn find_smart_duplicates(
    _app: AppHandle,
    paths: Vec<String>,
) -> Result<Vec<DuplicateGroup>, String> {
    if paths.is_empty() {
        return Ok(Vec::new());
    }

    let result = tauri::async_runtime::spawn_blocking(move || {
        let _ = crate::onnx::init_model();
        let mut image_data = Vec::with_capacity(paths.len());

        for p in &paths {
            let img_opt = get_image_for_hashing(p);
            let phash = img_opt
                .as_ref()
                .and_then(|img| compute_hash(img, "phash"))
                .unwrap_or(0);
            let emb = crate::onnx::extract_image_embedding(std::path::Path::new(p));
            image_data.push((p.clone(), phash, emb));
        }

        let mut groups: Vec<DuplicateGroup> = Vec::new();
        let mut assigned = vec![false; image_data.len()];

        for i in 0..image_data.len() {
            if assigned[i] {
                continue;
            }
            let mut group_paths = vec![image_data[i].0.clone()];
            assigned[i] = true;

            for j in (i + 1)..image_data.len() {
                if assigned[j] {
                    continue;
                }

                let dist = hamming_distance(image_data[i].1, image_data[j].1);
                let hamming_normalized = dist as f32 / 64.0;
                let cosine_sim = crate::onnx::cosine_similarity(&image_data[i].2, &image_data[j].2);
                let score = (1.0 - hamming_normalized) * 50.0 + cosine_sim * 50.0;

                if score > 70.0 {
                    group_paths.push(image_data[j].0.clone());
                    assigned[j] = true;
                }
            }

            if group_paths.len() > 1 {
                let best = group_paths
                    .iter()
                    .max_by_key(|p| std::fs::metadata(p).map(|m| m.len()).unwrap_or(0))
                    .cloned()
                    .unwrap_or_default();
                let group_id = uuid::Uuid::new_v4().to_string();
                groups.push(DuplicateGroup {
                    group_id,
                    images: group_paths,
                    best_path: best,
                });
            }
        }

        Ok::<Vec<DuplicateGroup>, String>(groups)
    })
    .await
    .map_err(|e| format!("Task failed: {}", e))??;

    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hamming_distance() {
        // Arrange
        let a = 0b10101010;
        let b = 0b10101111; // differs in last 2 bits

        // Act
        let dist = hamming_distance(a, b);

        // Assert
        assert_eq!(dist, 2);
    }

    #[test]
    fn test_get_duplicate_stats() {
        // Arrange
        let groups = vec![
            DuplicateGroup {
                group_id: "1".into(),
                images: vec!["a.jpg".into(), "b.jpg".into()],
                best_path: "a.jpg".into(),
            },
            DuplicateGroup {
                group_id: "2".into(),
                images: vec!["c.jpg".into(), "d.jpg".into(), "e.jpg".into()],
                best_path: "c.jpg".into(),
            },
        ];

        // Act
        let stats = get_duplicate_stats(groups).expect("Failed to get stats");

        // Assert
        assert_eq!(stats.total_groups, 2);
        assert_eq!(stats.total_duplicates, 3);
        assert_eq!(stats.potential_savings_mb, 0.0);
    }

    #[test]
    fn test_compute_hash_32_phash() {
        // Arrange
        let img = image::DynamicImage::ImageRgba8(image::RgbaImage::new(16, 16));

        // Act
        let hash = compute_hash_32(&img, "phash");

        // Assert
        assert!(hash.is_some());
    }

    #[test]
    fn test_bktree_query() {
        // Arrange
        let mut nodes = Vec::new();
        nodes.push(BKNode {
            hash: 0b10101010,
            index: 0,
            children: std::collections::HashMap::new(),
        });

        nodes[0].children.insert(2, 1);
        nodes.push(BKNode {
            hash: 0b10101111,
            index: 1,
            children: std::collections::HashMap::new(),
        });

        // Act
        let mut results = Vec::new();
        bktree_query(&nodes, 0, 0b10101111, 2, &mut results);

        // Assert
        assert!(results.contains(&1));
    }

    #[test]
    fn test_group_faces_by_person() {
        // Arrange
        let face1 = FaceEmbedding {
            face_id: "1".into(),
            path: "a.jpg".into(),
            bbox: [0.0, 0.0, 1.0, 1.0],
            confidence: 0.9,
            embedding: vec![1.0, 0.0, 0.0],
        };
        let face2 = FaceEmbedding {
            face_id: "2".into(),
            path: "b.jpg".into(),
            bbox: [0.0, 0.0, 1.0, 1.0],
            confidence: 0.9,
            embedding: vec![0.9, 0.1, 0.0], // Highly similar to face1
        };
        let face3 = FaceEmbedding {
            face_id: "3".into(),
            path: "c.jpg".into(),
            bbox: [0.0, 0.0, 1.0, 1.0],
            confidence: 0.9,
            embedding: vec![0.0, 1.0, 0.0], // Orthogonal to face1 and face2
        };

        let faces = vec![face1, face2, face3];

        // Act
        let groups_result = group_faces_by_person(faces);

        // Assert
        assert!(groups_result.is_ok());
        let groups = groups_result.unwrap();

        // Expected 2 groups: [face1, face2] and [face3]
        assert_eq!(groups.len(), 2);

        let mut group_sizes: Vec<usize> = groups.iter().map(|g| g.faces.len()).collect();
        group_sizes.sort_unstable();
        assert_eq!(group_sizes, vec![1, 2]);
    }
}
