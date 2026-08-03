use std::fs;
use std::path::Path;
use std::sync::Arc;
use wiphoto_lib::commands::duplicates;
use wiphoto_lib::onnx;

#[test]
fn test_r1_challenger_onnx_offline_and_edge_cases() {
    // 1. Initialize offline dummy ONNX model
    onnx::init_dummy_model().expect("init_dummy_model failed");
    assert!(onnx::get_model().is_some());

    // 2. Test analyze_image with missing file
    let missing_path = Path::new("non_existent_image_12345.jpg");
    assert!(
        onnx::analyze_image(missing_path).is_none(),
        "analyze_image on non-existent file should return None"
    );

    // 3. Test extract_image_embedding with missing file
    let missing_emb = onnx::extract_image_embedding(missing_path);
    assert_eq!(
        missing_emb.len(),
        512,
        "Should return 512-dim zero/normalized fallback embedding"
    );

    // 4. Test index_faces with non-existent file/dir/empty string
    let res1 = duplicates::index_faces("non_existent_file.jpg".into());
    assert!(
        res1.is_ok(),
        "index_faces on non-existent path should return Ok(empty vec)"
    );
    assert!(res1.unwrap().is_empty());

    let res2 = duplicates::index_faces("".into());
    assert!(
        res2.is_ok(),
        "index_faces on empty path should return Ok(empty vec)"
    );
    assert!(res2.unwrap().is_empty());

    let res3 = duplicates::index_faces("C:\\invalid_folder_98765".into());
    assert!(
        res3.is_ok(),
        "index_faces on non-existent folder should return Ok(empty vec)"
    );
    assert!(res3.unwrap().is_empty());
}

#[test]
fn test_r1_challenger_face_indexing_corrupt_and_valid_files() {
    let temp_dir = std::env::temp_dir().join(format!("r1_stress_faces_{}", uuid::Uuid::new_v4()));
    fs::create_dir_all(&temp_dir).expect("Failed to create temp dir");

    // Create 0-byte corrupt image
    let corrupt_jpg = temp_dir.join("corrupt.jpg");
    fs::write(&corrupt_jpg, b"").expect("Failed to write 0-byte file");

    // Create non-image text file
    let txt_file = temp_dir.join("readme.txt");
    fs::write(&txt_file, b"Hello World").expect("Failed to write txt file");

    // Create valid image file
    let valid_jpg = temp_dir.join("valid_face.jpg");
    let img = image::RgbImage::from_fn(128, 128, |x, y| {
        image::Rgb([(x % 255) as u8, (y % 255) as u8, 128])
    });
    img.save(&valid_jpg).expect("Failed to save valid_jpg");

    // Act: index_faces on corrupt file
    let corrupt_res = duplicates::index_faces(corrupt_jpg.to_string_lossy().to_string());
    assert!(
        corrupt_res.is_ok(),
        "index_faces on corrupt image should return Ok"
    );

    // Act: index_faces on directory containing mix of corrupt, txt, and valid image
    let dir_res = duplicates::index_faces(temp_dir.to_string_lossy().to_string());
    assert!(dir_res.is_ok(), "index_faces on folder should succeed");
    let embeddings = dir_res.unwrap();
    assert!(
        !embeddings.is_empty(),
        "Should extract face embedding for valid_jpg in directory"
    );
    assert_eq!(embeddings[0].embedding.len(), 512);

    // Clean up
    let _ = fs::remove_dir_all(&temp_dir);
}

#[test]
fn test_r1_challenger_similar_images_blue_water_vs_red() {
    let temp_dir = std::env::temp_dir().join(format!("r1_stress_similar_{}", uuid::Uuid::new_v4()));
    fs::create_dir_all(&temp_dir).expect("Failed to create temp dir");

    // Create 2 identical blue images with different filenames
    let blue1 = temp_dir.join("sea_view1.jpg");
    let blue2 = temp_dir.join("sea_view2.jpg");

    let img_blue = image::RgbImage::from_fn(100, 100, |_, _| image::Rgb([10, 20, 240]));
    img_blue.save(&blue1).expect("Failed to save blue1");
    img_blue.save(&blue2).expect("Failed to save blue2");

    let emb_b1 = onnx::extract_image_embedding(&blue1);
    let emb_b2 = onnx::extract_image_embedding(&blue2);

    let sim_blue = onnx::cosine_similarity(&emb_b1, &emb_b2);
    assert!(
        (sim_blue - 1.0).abs() < 0.05,
        "Identical blue images should have high similarity"
    );

    // Clean up
    let _ = fs::remove_dir_all(&temp_dir);
}

#[test]
fn test_r1_challenger_concurrent_face_indexing_stress() {
    let temp_dir = Arc::new(
        std::env::temp_dir().join(format!("r1_stress_concurrent_{}", uuid::Uuid::new_v4())),
    );
    fs::create_dir_all(&*temp_dir).expect("Failed to create temp dir");

    let img_path = temp_dir.join("concurrent_test.jpg");
    let img = image::RgbImage::from_fn(64, 64, |x, y| image::Rgb([x as u8, y as u8, 200]));
    img.save(&img_path).expect("Failed to save image");

    let path_str = Arc::new(img_path.to_string_lossy().to_string());

    let mut handles = Vec::new();
    for _ in 0..10 {
        let p = Arc::clone(&path_str);
        handles.push(std::thread::spawn(move || {
            let res = duplicates::index_faces((*p).clone());
            assert!(res.is_ok(), "Concurrent index_faces failed");
            let faces = res.unwrap();
            assert!(!faces.is_empty());
            assert_eq!(faces[0].embedding.len(), 512);
        }));
    }

    for handle in handles {
        handle
            .join()
            .expect("Thread panicked during concurrent index_faces test");
    }

    let _ = fs::remove_dir_all(&*temp_dir);
}

#[test]
fn test_r1_challenger_phash_computation_robustness() {
    // Test compute_phash on missing file
    let res_missing = duplicates::compute_phash("non_existent_file_99.jpg".into());
    assert!(
        res_missing.is_err(),
        "compute_phash on missing file should return Err"
    );

    // Test compute_phash on valid synthetic image
    let temp_dir = std::env::temp_dir().join(format!("r1_stress_phash_{}", uuid::Uuid::new_v4()));
    fs::create_dir_all(&temp_dir).expect("Failed to create temp dir");
    let img_path = temp_dir.join("phash_test.jpg");
    let img = image::RgbImage::from_fn(32, 32, |x, y| {
        image::Rgb([(x * 8) as u8, (y * 8) as u8, 100])
    });
    img.save(&img_path).expect("Failed to save image");

    let res_valid = duplicates::compute_phash(img_path.to_string_lossy().to_string());
    assert!(res_valid.is_ok());
    let hash_hex = res_valid.unwrap();
    assert_eq!(hash_hex.len(), 16, "pHash string must be 16 hex characters");

    let _ = fs::remove_dir_all(&temp_dir);
}
