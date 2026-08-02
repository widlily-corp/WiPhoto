use std::fs;
use std::path::PathBuf;
use std::thread;
use wiphoto_lib::db;
use wiphoto_lib::models::image_info::ImageInfo;

#[test]
fn test_database_multi_threaded_concurrency_stress() {
    let _ = db::init_db();

    // Spawn 10 concurrent threads inserting and querying 100 records each
    let num_threads = 10;
    let items_per_thread = 100;
    let mut handles = vec![];

    for t_id in 0..num_threads {
        let handle = thread::spawn(move || {
            let _ = db::init_db();
            for i in 0..items_per_thread {
                let img_path = format!("C:/photos/thread_{}/image_{}.jpg", t_id, i);
                let info = ImageInfo {
                    path: img_path.clone(),
                    filename: format!("image_{}.jpg", i),
                    thumbnail: "thumb_data".to_string(),
                    phash: Some("1234567890abcdef".to_string()),
                    sharpness: 0.95,
                    is_best_in_group: i == 0,
                    group_id: Some(format!("group_{}", t_id)),
                    faces_count: (i % 3) as u32,
                    animals_count: 0,
                    gps_location: Some((48.8566 + (i as f64 * 0.001), 2.3522)),
                    aspect_ratio: 1.5,
                    camera_model: "Sony A7IV".to_string(),
                    date_taken: "2026:07:30 12:00:00".to_string(),
                    rating: ((i % 5) + 1) as u8,
                    file_size: 1024 * 500,
                    width: 6000,
                    height: 4000,
                    animal_species: vec![],
                    color_label: "green".to_string(),
                    flag_status: "picked".to_string(),
                    tags: vec!["Benchmark".to_string(), format!("T_{}", t_id)],
                    is_video: false,
                    is_raw: false,
                };

                let save_res = db::save_images_batch(&[(&info, 1700000000)]);
                assert!(save_res.is_ok(), "DB Save batch failed in thread {}", t_id);

                let dummy_emb = vec![(i as f32) / 100.0; 512];
                let emb_res = db::save_image_embedding(&img_path, &dummy_emb);
                assert!(emb_res.is_ok(), "Embedding save failed in thread {}", t_id);

                let query_res = db::get_images_by_paths(std::slice::from_ref(&img_path));
                assert!(query_res.is_ok(), "Query by path failed in thread {}", t_id);
                let queried = query_res.unwrap();
                assert_eq!(queried.len(), 1);
                assert_eq!(queried[0].filename, format!("image_{}.jpg", i));
            }
        });
        handles.push(handle);
    }

    for h in handles {
        h.join().expect("DB Concurrency Thread panicked");
    }

    println!("  ✓ DB Multi-threaded Concurrency Stress passed (10 threads, 1,000 operations)");
}

#[test]
fn test_multi_threaded_folder_scan_simulation() {
    let temp_dir = std::env::temp_dir().join(format!("wiphoto_scan_stress_{}", std::process::id()));
    let _ = fs::remove_dir_all(&temp_dir);
    fs::create_dir_all(&temp_dir).expect("Failed to create temp dir");

    // Create 100 fake image files in temp_dir
    for i in 0..100 {
        let file_path = temp_dir.join(format!("photo_{:03}.jpg", i));
        fs::write(&file_path, b"FAKE_JPEG_HEADER_STRESS_TEST_DATA").unwrap();
    }

    // Measure Rayon multi-threaded traversal
    use rayon::prelude::*;
    let entries: Vec<PathBuf> = fs::read_dir(&temp_dir)
        .unwrap()
        .filter_map(|e| e.ok().map(|de| de.path()))
        .collect();

    assert_eq!(entries.len(), 100);

    let start = std::time::Instant::now();
    let processed_count: usize = entries
        .par_iter()
        .map(|path| {
            let meta = fs::metadata(path).ok();
            if meta.is_some() {
                1
            } else {
                0
            }
        })
        .sum();

    let duration = start.elapsed();
    assert_eq!(processed_count, 100);
    assert!(
        duration.as_millis() < 50,
        "Rayon 100 files processing took {:?}",
        duration
    );

    println!(
        "  ✓ Multi-threaded Folder Scan Simulation passed (100 files in {:?})",
        duration
    );

    let _ = fs::remove_dir_all(&temp_dir);
}

#[test]
fn test_thumbnail_cache_concurrency_and_hit_latency() {
    use wiphoto_lib::commands::thumbnails;

    // Arrange: Pre-populate cache with 5,000 thumbnail entries
    let cache_size = 5000;
    for i in 0..cache_size {
        let original_path = format!("C:/photos/gallery/photo_{:05}.jpg", i);
        let thumb_path = format!("C:/cache/thumbnails/thumb_{:05}.jpg", i);
        thumbnails::update_in_memory_thumbnail_cache(original_path, thumb_path);
    }

    // Act: Spawn 20 threads executing 100,000 total lookup operations
    let num_threads = 20;
    let lookups_per_thread = 5000;
    let mut handles = vec![];

    let start = std::time::Instant::now();

    for t_id in 0..num_threads {
        let handle = thread::spawn(move || {
            for i in 0..lookups_per_thread {
                let idx = (t_id * lookups_per_thread + i) % cache_size;
                let path = format!("C:/photos/gallery/photo_{:05}.jpg", idx);
                let _res = thumbnails::get_cached_thumbnail_path(&path);
            }
        });
        handles.push(handle);
    }

    for h in handles {
        h.join().expect("Thumbnail lookup thread panicked");
    }

    let elapsed = start.elapsed();
    let total_lookups = (num_threads * lookups_per_thread) as f64;
    let avg_latency_micros = (elapsed.as_secs_f64() * 1_000_000.0) / total_lookups;

    // Assert: Cache hit response time under 20 concurrent threads must be < 10 microseconds per lookup
    assert!(
        avg_latency_micros < 10.0,
        "Average thumbnail cache lookup latency was {:.2} µs (> 10 µs limit)",
        avg_latency_micros
    );

    println!(
        "  ✓ Thumbnail Cache Concurrency: 100,000 lookups across 20 threads in {:?} ({:.2} µs/lookup)",
        elapsed, avg_latency_micros
    );
}

#[test]
fn test_bktree_10000_items_duplicate_query_benchmark() {
    use std::collections::HashMap;

    // Arrange: Synthetic BKNode struct matching implementation for 10k items
    struct BKNode {
        hash: u64,
        index: usize,
        children: HashMap<u32, usize>,
    }

    fn hamming(a: u64, b: u64) -> u32 {
        (a ^ b).count_ones()
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
        let dist = hamming(node.hash, query_hash);
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

    let item_count = 10000;
    let mut tree_nodes: Vec<BKNode> = Vec::with_capacity(item_count);

    // Build 10,000 perceptual hashes
    let start_build = std::time::Instant::now();
    for i in 0..item_count {
        let hash = (i as u64).wrapping_mul(0x9E3779B97F4A7C15);
        if tree_nodes.is_empty() {
            tree_nodes.push(BKNode {
                hash,
                index: i,
                children: HashMap::new(),
            });
            continue;
        }
        let mut curr = 0;
        loop {
            let dist = hamming(tree_nodes[curr].hash, hash);
            if let Some(&idx) = tree_nodes[curr].children.get(&dist) {
                curr = idx;
            } else {
                let new_idx = tree_nodes.len();
                tree_nodes.push(BKNode {
                    hash,
                    index: i,
                    children: HashMap::new(),
                });
                tree_nodes[curr].children.insert(dist, new_idx);
                break;
            }
        }
    }
    let build_duration = start_build.elapsed();

    // Act: 1,000 duplicate search queries with Hamming distance threshold = 8
    let start_query = std::time::Instant::now();
    let query_count = 1000;
    let mut total_matches = 0;

    for q in 0..query_count {
        let query_hash = (q as u64)
            .wrapping_mul(7919u64)
            .wrapping_mul(0x9E3779B97F4A7C15u64);
        let mut matches = Vec::new();
        bktree_query(&tree_nodes, 0, query_hash, 8, &mut matches);
        total_matches += matches.len();
    }

    let query_duration = start_query.elapsed();
    let avg_query_ms = (query_duration.as_secs_f64() * 1000.0) / query_count as f64;

    // Assert: BK-Tree 10,000 items query response time must be < 2.0ms per query in debug mode
    assert!(
        avg_query_ms < 2.0,
        "Average BK-Tree query time was {:.3} ms (> 2.0 ms limit)",
        avg_query_ms
    );

    println!(
        "  ✓ BK-Tree 10,000 Items: Build {:?}, 1,000 Queries in {:?} ({:.3} ms/query, {} matches)",
        build_duration, query_duration, avg_query_ms, total_matches
    );
}
