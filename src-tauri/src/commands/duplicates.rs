use crate::models::image_info::DuplicateGroup;
use rayon::prelude::*;

/// Simple perceptual hash implementation using DCT-based approach
fn compute_hash(img: &image::DynamicImage, method: &str) -> Option<u64> {
    let gray = img.resize_exact(8, 8, image::imageops::FilterType::Lanczos3)
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
            let gray9 = img.resize_exact(9, 8, image::imageops::FilterType::Lanczos3)
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
        "phash" | _ => {
            // Simplified pHash using mean of larger block
            let gray32 = img.resize_exact(32, 32, image::imageops::FilterType::Lanczos3)
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

/// Find duplicates using specified hash method
#[tauri::command]
pub fn find_duplicates(
    paths: Vec<String>,
    method: String,
    threshold: u32,
) -> Result<Vec<DuplicateGroup>, String> {
    // Compute hashes in parallel
    let hashes: Vec<(String, Option<u64>)> = paths
        .par_iter()
        .map(|path| {
            let hash = image::open(path).ok().and_then(|img| compute_hash(&img, &method));
            (path.clone(), hash)
        })
        .collect();

    // Filter out files that couldn't be hashed
    let valid_hashes: Vec<(String, u64)> = hashes
        .into_iter()
        .filter_map(|(path, hash)| hash.map(|h| (path, h)))
        .collect();

    // Group by similarity
    let mut groups: Vec<DuplicateGroup> = Vec::new();
    let mut assigned: Vec<bool> = vec![false; valid_hashes.len()];

    for i in 0..valid_hashes.len() {
        if assigned[i] {
            continue;
        }
        let mut group_paths = vec![valid_hashes[i].0.clone()];

        for j in (i + 1)..valid_hashes.len() {
            if assigned[j] {
                continue;
            }
            let dist = hamming_distance(valid_hashes[i].1, valid_hashes[j].1);
            if dist <= threshold {
                group_paths.push(valid_hashes[j].0.clone());
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
            assigned[i] = true;
        }
    }

    Ok(groups)
}

/// Get duplicate search statistics
#[tauri::command]
pub fn get_duplicate_stats(groups: Vec<DuplicateGroup>) -> Result<DuplicateStats, String> {
    let total_groups = groups.len() as u32;
    let total_duplicates: u32 = groups.iter().map(|g| (g.images.len() as u32).saturating_sub(1)).sum();
    let potential_savings: u64 = groups
        .iter()
        .flat_map(|g| {
            g.images.iter().filter(|p| **p != g.best_path).map(|p| {
                std::fs::metadata(p).map(|m| m.len()).unwrap_or(0)
            })
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
    let img = image::open(&path).map_err(|e| format!("Failed to open image: {}", e))?;
    let hash = compute_hash(&img, "phash").unwrap_or(0);
    Ok(format!("{:016x}", hash))
}
