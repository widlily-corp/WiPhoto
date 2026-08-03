use std::path::Path;
use wiphoto_lib::commands::duplicates;
use wiphoto_lib::onnx;

#[test]
fn test_edge_case_zero_inputs() {
    // 1. Zero vectors cosine similarity
    let zero1 = vec![0.0f32; 512];
    let zero2 = vec![0.0f32; 512];
    let normal_vec = vec![1.0f32; 512];

    let sim_zeros = onnx::cosine_similarity(&zero1, &zero2);
    assert_eq!(sim_zeros, 0.0, "Cosine similarity of two zero vectors must be 0.0 (no NaN)");
    assert!(!sim_zeros.is_nan(), "Cosine similarity must not return NaN for zero vectors");

    let sim_zero_normal = onnx::cosine_similarity(&zero1, &normal_vec);
    assert_eq!(sim_zero_normal, 0.0, "Cosine similarity of zero vector and non-zero vector must be 0.0");
    assert!(!sim_zero_normal.is_nan());

    // 2. Empty slices
    let empty1: Vec<f32> = vec![];
    let empty2: Vec<f32> = vec![];
    assert_eq!(onnx::cosine_similarity(&empty1, &empty2), 0.0);
    assert_eq!(onnx::cosine_similarity(&empty1, &normal_vec), 0.0);

    // 3. Mismatched length slices
    let short_vec = vec![1.0f32, 2.0f32];
    assert_eq!(onnx::cosine_similarity(&short_vec, &normal_vec), 0.0);

    // 4. normalize_vector on zero vector
    let mut zero_to_norm = vec![0.0f32; 512];
    onnx::normalize_vector(&mut zero_to_norm);
    assert_eq!(zero_to_norm, vec![0.0f32; 512], "Normalizing zero vector should leave it as zeros without NaN");
    assert!(zero_to_norm.iter().all(|x| !x.is_nan()));

    // 5. extract_text_embedding on empty / whitespace strings
    let text_empty = onnx::extract_text_embedding("");
    let text_spaces = onnx::extract_text_embedding("   \t\n  ");
    assert_eq!(text_empty.len(), 512);
    assert_eq!(text_spaces.len(), 512);
    assert_eq!(text_empty, vec![0.0f32; 512]);
    assert_eq!(text_spaces, vec![0.0f32; 512]);
}

#[test]
fn test_edge_case_identical_vectors() {
    // 1. Identical non-zero vector similarity
    let mut v = vec![0.5f32; 512];
    onnx::normalize_vector(&mut v);
    let sim_self = onnx::cosine_similarity(&v, &v);
    assert!((sim_self - 1.0).abs() < 1e-5, "Cosine similarity of identical non-zero vector with itself must be 1.0, got {}", sim_self);

    // 2. Identical text query embeddings
    let text1 = onnx::extract_text_embedding("cute dog sitting on a sandy beach");
    let text2 = onnx::extract_text_embedding("cute dog sitting on a sandy beach");
    assert_eq!(text1, text2);
    let sim_text_self = onnx::cosine_similarity(&text1, &text2);
    assert!((sim_text_self - 1.0).abs() < 1e-5);

    // 3. Identical image paths embeddings
    let path = Path::new("C:/non_existent/sample.jpg");
    let img_emb1 = onnx::extract_image_embedding(path);
    let img_emb2 = onnx::extract_image_embedding(path);
    assert_eq!(img_emb1, img_emb2);
    let sim_img_self = onnx::cosine_similarity(&img_emb1, &img_emb2);
    assert!((sim_img_self - 1.0).abs() < 1e-5);
}

#[test]
fn test_edge_case_orthogonal_and_opposite_vectors() {
    // 1. Perfectly orthogonal vectors
    let mut v1 = vec![0.0f32; 512];
    let mut v2 = vec![0.0f32; 512];
    v1[0] = 1.0;
    v2[1] = 1.0;
    let sim_ortho = onnx::cosine_similarity(&v1, &v2);
    assert_eq!(sim_ortho, 0.0, "Cosine similarity of orthogonal vectors must be 0.0");

    // 2. Multi-component orthogonal vectors
    let mut v3 = vec![0.0f32; 512];
    let mut v4 = vec![0.0f32; 512];
    v3[0] = 1.0;
    v3[1] = 1.0;
    v4[0] = 1.0;
    v4[1] = -1.0;
    let sim_ortho2 = onnx::cosine_similarity(&v3, &v4);
    assert!((sim_ortho2 - 0.0).abs() < 1e-5, "Orthogonal dot product should give similarity 0.0");

    // 3. Anti-parallel / Opposite vectors
    let mut v_orig = vec![1.0f32; 512];
    onnx::normalize_vector(&mut v_orig);
    let v_opp: Vec<f32> = v_orig.iter().map(|x| -x).collect();
    let sim_opp = onnx::cosine_similarity(&v_orig, &v_opp);
    assert!((sim_opp - (-1.0)).abs() < 1e-5, "Anti-parallel vectors must have similarity -1.0, got {}", sim_opp);
}

#[test]
fn test_edge_case_empty_paths() {
    // 1. extract_image_embedding with empty path
    let empty_path = Path::new("");
    let emb = onnx::extract_image_embedding(empty_path);
    assert_eq!(emb.len(), 512, "Embedding for empty path must be 512-dimensional");
    let norm: f32 = emb.iter().map(|x| x * x).sum::<f32>().sqrt();
    assert!((norm - 1.0).abs() < 1e-3, "Empty path fallback vector must be normalized");
    assert!(emb.iter().all(|x| !x.is_nan()), "Empty path embedding must not contain NaN");

    // 2. index_faces with empty path string
    let faces_res = duplicates::index_faces("".to_string());
    assert!(faces_res.is_ok(), "index_faces with empty path must return Ok without panic");
    let faces = faces_res.unwrap();
    assert!(faces.is_empty(), "index_faces with empty path should return empty vector");

    // 3. compute_phash with empty path string
    let phash_res = duplicates::compute_phash("".to_string());
    assert!(phash_res.is_err(), "compute_phash with empty path should return Err");
    assert_eq!(phash_res.unwrap_err(), "Failed to open image");
}

#[test]
fn test_edge_case_non_existent_files() {
    // 1. extract_image_embedding with non-existent file
    let missing_path = Path::new("C:/invalid_non_existent_dir_98765/missing_photo_12345.jpg");
    let emb = onnx::extract_image_embedding(missing_path);
    assert_eq!(emb.len(), 512, "Missing file embedding must be 512-dimensional");
    let norm: f32 = emb.iter().map(|x| x * x).sum::<f32>().sqrt();
    assert!((norm - 1.0).abs() < 1e-3, "Missing file fallback vector must be normalized");
    assert!(emb.iter().all(|x| !x.is_nan()), "Missing file embedding must not contain NaN");

    // 2. index_faces with non-existent file path
    let faces_res = duplicates::index_faces("C:/invalid_non_existent_dir_98765/missing_photo_12345.jpg".to_string());
    assert!(faces_res.is_ok(), "index_faces with non-existent file must return Ok without panic");
    let faces = faces_res.unwrap();
    assert!(faces.is_empty(), "index_faces with non-existent file should return empty vector");

    // 3. compute_phash with non-existent file path
    let phash_res = duplicates::compute_phash("C:/invalid_non_existent_dir_98765/missing_photo_12345.jpg".to_string());
    assert!(phash_res.is_err(), "compute_phash with non-existent file should return Err");
    assert_eq!(phash_res.unwrap_err(), "Failed to open image");
}
