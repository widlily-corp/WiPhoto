use crate::models::image_info::DuplicateGroup;
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
    if let Ok(thumb_path) =
        tauri::async_runtime::block_on(super::thumbnails::get_thumbnail(path.to_string()))
    {
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
}
