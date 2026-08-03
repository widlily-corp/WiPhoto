use std::fs;
use wiphoto_lib::commands::duplicates;
use wiphoto_lib::onnx;

#[test]
fn test_r1_dummy_onnx_model_execution_and_embedding() {
    // Arrange: Create a temporary test directory with sample test images
    let temp_dir = std::env::temp_dir().join(format!("r1_onnx_test_{}", uuid::Uuid::new_v4()));
    fs::create_dir_all(&temp_dir).expect("Failed to create temp dir");

    let img1_path = temp_dir.join("sample_dog.jpg");
    let img2_path = temp_dir.join("sample_beach.jpg");

    // Generate dummy 64x64 RGB images using image crate
    let img1 = image::RgbImage::from_fn(64, 64, |x, y| {
        if (x + y) % 2 == 0 {
            image::Rgb([200, 100, 50])
        } else {
            image::Rgb([100, 50, 20])
        }
    });
    img1.save(&img1_path).expect("Failed to save img1");

    let img2 = image::RgbImage::from_fn(64, 64, |x, _y| {
        if x > 32 {
            image::Rgb([10, 50, 220])
        } else {
            image::Rgb([240, 180, 20])
        }
    });
    img2.save(&img2_path).expect("Failed to save img2");

    // Act 1: Initialize offline dummy ONNX model
    onnx::init_dummy_model().expect("init_dummy_model failed");

    // Assert 1: Model is present
    assert!(
        onnx::get_model().is_some(),
        "ONNX model should be initialized"
    );

    // Act 2: Analyze image using the dummy ONNX graph
    let analysis_res = onnx::analyze_image(&img1_path);
    assert!(
        analysis_res.is_some(),
        "analyze_image should succeed with dummy model"
    );

    // Act 3: Extract 512-dim image embeddings
    let emb1 = onnx::extract_image_embedding(&img1_path);
    let emb2 = onnx::extract_image_embedding(&img2_path);

    // Assert 3: Embedding properties
    assert_eq!(emb1.len(), 512, "Embedding dimension must be 512");
    assert_eq!(emb2.len(), 512, "Embedding dimension must be 512");

    let norm1: f32 = emb1.iter().map(|x| x * x).sum::<f32>().sqrt();
    let norm2: f32 = emb2.iter().map(|x| x * x).sum::<f32>().sqrt();
    assert!((norm1 - 1.0).abs() < 1e-3, "Vector 1 should be L2 normalized");
    assert!((norm2 - 1.0).abs() < 1e-3, "Vector 2 should be L2 normalized");

    // Act 4: Text embedding & Cosine similarity
    let text_emb = onnx::extract_text_embedding("dog and puppy");
    assert_eq!(text_emb.len(), 512);

    let sim_text_img1 = onnx::cosine_similarity(&text_emb, &emb1);
    assert!(
        sim_text_img1 >= -1.0 && sim_text_img1 <= 1.0,
        "Cosine similarity must be bounded in [-1.0, 1.0]"
    );

    // Act 5: Call index_faces command
    let faces_res = duplicates::index_faces(img1_path.to_string_lossy().to_string());
    assert!(faces_res.is_ok(), "index_faces should return Ok");
    let faces = faces_res.unwrap();
    assert!(
        !faces.is_empty(),
        "index_faces should return at least 1 face embedding"
    );
    assert_eq!(faces[0].embedding.len(), 512);

    // Act 6: Call compute_phash command
    let phash_res = duplicates::compute_phash(img1_path.to_string_lossy().to_string());
    assert!(phash_res.is_ok(), "compute_phash should return Ok");
    let phash = phash_res.unwrap();
    assert_eq!(phash.len(), 16, "pHash string length should be 16 hex chars");

    // Clean up
    let _ = fs::remove_dir_all(&temp_dir);
}
