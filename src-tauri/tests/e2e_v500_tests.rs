use std::fs;
use wiphoto_lib::commands::settings;
use wiphoto_lib::commands::xmp;
use wiphoto_lib::db;
use wiphoto_lib::models::image_info::ImageInfo;
use wiphoto_lib::onnx;

#[test]
fn test_tier1_feature_coverage_rust() {
    // Arrange: R7 Version Check
    let version = settings::get_app_version();
    let info = settings::get_app_info();
    assert_eq!(version, env!("CARGO_PKG_VERSION"));
    assert_eq!(info.version, env!("CARGO_PKG_VERSION"));

    // Arrange: R1 Cosine Similarity
    let v_query = vec![1.0, 0.0, 0.0, 0.0];
    let v_match = vec![0.9, 0.1, 0.0, 0.0];
    let v_ortho = vec![0.0, 1.0, 0.0, 0.0];

    // Act
    let score_high = onnx::cosine_similarity(&v_query, &v_match);
    let score_low = onnx::cosine_similarity(&v_query, &v_ortho);

    // Assert
    assert!(score_high > 0.90);
    assert!(score_low < 0.01);

    // Arrange & Act: R2 XMP XML Parsing
    let xml = r#"<?xml version="1.0"?>
    <x:xmpmeta xmlns:x="adobe:ns:meta/">
      <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
        <rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/"
          xmp:Rating="5" xmp:Label="green" xmp:FlagStatus="picked">
          <dc:subject><rdf:Bag><rdf:li>Landscape</rdf:li><rdf:li>Sunset</rdf:li></rdf:Bag></dc:subject>
        </rdf:Description>
      </rdf:RDF>
    </x:xmpmeta>"#;

    let parsed = xmp::parse_xmp_content(xml).expect("Failed to parse XMP XML");

    // Assert
    assert_eq!(parsed.rating, 5);
    assert_eq!(parsed.color_label, "green");
    assert_eq!(parsed.flag_status, "picked");
    assert_eq!(parsed.tags, vec!["Landscape", "Sunset"]);
}

#[test]
fn test_tier2_boundary_corner_cases_rust() {
    let _ = db::init_db();

    // Arrange: Empty vectors to cosine similarity
    let empty_v1: Vec<f32> = vec![];
    let empty_v2: Vec<f32> = vec![];
    let sim_empty = onnx::cosine_similarity(&empty_v1, &empty_v2);
    assert_eq!(sim_empty, 0.0);

    // Arrange: Malformed XML to XMP parser
    let malformed_xml = "<invalid>xml context <unclosed>";
    let parsed_none = xmp::parse_xmp_content(malformed_xml);
    assert!(parsed_none.is_none());

    // Arrange: XMP with empty attributes
    let xml_empty_attrs = r#"<?xml version="1.0"?>
    <x:xmpmeta xmlns:x="adobe:ns:meta/">
      <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
        <rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/">
        </rdf:Description>
      </rdf:RDF>
    </x:xmpmeta>"#;

    let parsed_empty = xmp::parse_xmp_content(xml_empty_attrs).expect("Should handle empty attrs");
    assert_eq!(parsed_empty.rating, 0);
    assert!(parsed_empty.tags.is_empty());

    // DB edge case: Query non-existent path vector
    let non_existent_paths: Vec<String> = vec!["C:/non_existent_path_999.jpg".to_string()];
    let db_results = db::get_images_by_paths(&non_existent_paths).expect("DB query failed");
    assert!(db_results.is_empty());
}

#[test]
fn test_tier3_cross_feature_combinations_rust() {
    // Arrange: Initialize SQLite DB
    let init_res = db::init_db();
    assert!(init_res.is_ok());

    // Create test image data with EXIF GPS and XMP tags
    let img_path = format!(
        "{}/temp_test_image.jpg",
        std::env::temp_dir().to_string_lossy()
    );
    let info = ImageInfo {
        path: img_path.clone(),
        filename: "temp_test_image.jpg".into(),
        thumbnail: "data:image/jpeg;base64,dummy".into(),
        phash: Some("12345678".into()),
        sharpness: 0.95,
        is_best_in_group: true,
        group_id: None,
        faces_count: 2,
        animals_count: 1,
        gps_location: Some((48.8566, 2.3522)), // Paris coordinates
        aspect_ratio: 1.5,
        camera_model: "Sony A7IV".into(),
        date_taken: "2026:07:30".into(),
        rating: 5,
        file_size: 204800,
        width: 1920,
        height: 1080,
        animal_species: vec!["Dog".into()],
        color_label: "yellow".into(),
        flag_status: "picked".into(),
        tags: vec!["Eiffel".into(), "Paris".into()],
        is_video: false,
        is_raw: false,
    };

    // Act: Batch save to DB
    let save_res = db::save_images_batch(&[(&info, 1000u64)]);
    assert!(save_res.is_ok());

    // Act: Query back by path
    let fetched = db::get_images_by_paths(std::slice::from_ref(&img_path)).expect("Fetch failed");

    // Assert: Verify cross-feature attributes persisted (GPS + XMP + ML tags)
    assert_eq!(fetched.len(), 1);
    assert_eq!(fetched[0].rating, 5);
    assert_eq!(fetched[0].gps_location, Some((48.8566, 2.3522)));
    assert_eq!(fetched[0].tags, vec!["Eiffel", "Paris"]);

    // Cleanup DB record
    let _ = db::delete_images_batch(&[img_path]);
}

#[test]
fn test_tier4_e2e_scenarios_rust() {
    // Arrange: Create temp file and XMP sidecar on disk
    let temp_dir = std::env::temp_dir();
    let img_file = temp_dir.join("wiphoto_e2e_sample.jpg");
    let xmp_file = temp_dir.join("wiphoto_e2e_sample.xmp");

    let _ = fs::write(&img_file, b"fake image content");

    // Act: Write XMP sidecar via command function
    let write_res = xmp::write_xmp_sidecar(
        img_file.to_string_lossy().to_string(),
        4,
        "blue".to_string(),
        "picked".to_string(),
        vec!["Architecture".to_string(), "Urban".to_string()],
        Some("Created tag".to_string()),
    );
    assert!(write_res.is_ok());
    assert!(xmp_file.exists());

    // Act: Read back XMP sidecar via command function
    let read_res = xmp::read_xmp_sidecar(img_file.to_string_lossy().to_string());
    assert!(read_res.is_ok());

    let sidecar_data = read_res.unwrap().expect("Sidecar should exist");
    assert_eq!(sidecar_data.rating, 4);
    assert_eq!(sidecar_data.color_label, "blue");
    assert_eq!(sidecar_data.flag_status, "picked");
    assert_eq!(sidecar_data.tags, vec!["Architecture", "Urban"]);

    // Act: Vector similarity query simulating CLIP search
    let text_embedding = vec![0.5, 0.5, 0.5, 0.5];
    let mut image_embedding = vec![0.49, 0.51, 0.48, 0.52];
    onnx::normalize_vector(&mut image_embedding);
    let sim = onnx::cosine_similarity(&text_embedding, &image_embedding);

    // Assert: High similarity score for relevant match
    assert!(sim > 0.99);

    // Act: IPC search command search_clip_semantic
    let search_res = wiphoto_lib::commands::search::search_clip_semantic("".to_string(), 10);
    assert!(search_res.is_ok());

    // Cleanup temp files
    let _ = fs::remove_file(&img_file);
    let _ = fs::remove_file(&xmp_file);
}

#[test]
fn test_ota_updater_configuration_and_plugin_registration() {
    // Arrange: Verify app info and version string
    let app_info = settings::get_app_info();
    assert_eq!(app_info.version, env!("CARGO_PKG_VERSION"));

    // Arrange: Read tauri.conf.json configuration
    let conf_path = std::path::Path::new("tauri.conf.json");
    assert!(conf_path.exists(), "tauri.conf.json must exist");

    let conf_str = fs::read_to_string(conf_path).expect("Failed to read tauri.conf.json");
    let conf_val: serde_json::Value = serde_json::from_str(&conf_str).expect("Valid JSON config");

    // Assert: Verify plugins.updater is configured in tauri.conf.json
    let updater_conf = &conf_val["plugins"]["updater"];
    assert!(
        updater_conf.is_object(),
        "plugins.updater object must exist"
    );

    let endpoints = updater_conf["endpoints"]
        .as_array()
        .expect("Endpoints array must exist");
    assert!(!endpoints.is_empty(), "Updater endpoints must not be empty");
    assert!(
        endpoints[0].as_str().unwrap_or("").contains("github.com"),
        "Updater endpoint should target GitHub Releases"
    );

    let pubkey = updater_conf["pubkey"]
        .as_str()
        .expect("Pubkey must be configured");
    assert!(!pubkey.is_empty(), "Updater pubkey must not be empty");
}
