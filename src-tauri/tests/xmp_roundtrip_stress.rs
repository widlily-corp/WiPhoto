use std::fs;
use wiphoto_lib::commands::xmp;

#[test]
fn test_xmp_1000_sequential_roundtrip_updates() {
    // Arrange: Create temp image path
    let temp_dir = std::env::temp_dir();
    let img_path = temp_dir
        .join("wiphoto_stress_1000_roundtrip.jpg")
        .to_string_lossy()
        .to_string();
    let sidecar_path = std::path::Path::new(&img_path).with_extension("xmp");

    let _ = fs::remove_file(&sidecar_path);

    // Act & Assert: Execute 1,000 sequential updates
    for i in 1..=1000 {
        let rating = ((i % 5) + 1) as u8;
        let label = match i % 4 {
            0 => "red",
            1 => "green",
            2 => "blue",
            _ => "yellow",
        }
        .to_string();
        let status = if i % 2 == 0 { "picked" } else { "rejected" }.to_string();
        let tags = vec![format!("Tag_{}", i), format!("Batch_{}", i / 100)];
        let history_msg = format!("Edit iteration #{}", i);

        let write_res = xmp::write_xmp_sidecar(
            img_path.clone(),
            rating,
            label.clone(),
            status.clone(),
            tags.clone(),
            Some(history_msg.clone()),
        );
        assert!(write_res.is_ok(), "Write failed at iteration {}", i);

        let read_data = xmp::read_xmp_sidecar(img_path.clone())
            .expect("Read returned Result::Err")
            .expect("Read returned None for existing sidecar");

        assert_eq!(
            read_data.rating, rating,
            "Rating mismatch at iteration {}",
            i
        );
        assert_eq!(
            read_data.color_label, label,
            "Color label mismatch at iteration {}",
            i
        );
        assert_eq!(
            read_data.flag_status, status,
            "Flag status mismatch at iteration {}",
            i
        );
        assert_eq!(read_data.tags, tags, "Tags mismatch at iteration {}", i);
        assert_eq!(
            read_data.history.len(),
            i,
            "History length mismatch at iteration {}",
            i
        );
        assert_eq!(
            read_data.history[i - 1],
            history_msg,
            "Latest history entry mismatch at iteration {}",
            i
        );
    }

    // Clean up
    let _ = fs::remove_file(&sidecar_path);
}

#[test]
fn test_xmp_special_characters_and_unicode_escaping() {
    let temp_dir = std::env::temp_dir();
    let img_path = temp_dir
        .join("wiphoto_stress_unicode.jpg")
        .to_string_lossy()
        .to_string();
    let sidecar_path = std::path::Path::new(&img_path).with_extension("xmp");

    let _ = fs::remove_file(&sidecar_path);

    // Adversarial strings with XML special chars & Unicode
    let complex_label = "Tom & Jerry <Special> \"Quotes\" 'Single'";
    let complex_status = "Status & <Pending> \"Active\"";
    let complex_tags = vec![
        "Rock & Roll".to_string(),
        "<TagWithBrackets>".to_string(),
        "\"DoubleQuotes\"".to_string(),
        "'SingleQuotes'".to_string(),
        "Non-ASCII: Привет, Мир!".to_string(),
        "CJK: 写真 & 景色".to_string(),
        "Emoji: 📸 🌲 🏔️".to_string(),
    ];
    let complex_history = "Applied preset: <HDR & Vibrant> + \"Sharpness\" + 📸";

    // Act: Write sidecar
    let write_res = xmp::write_xmp_sidecar(
        img_path.clone(),
        5,
        complex_label.to_string(),
        complex_status.to_string(),
        complex_tags.clone(),
        Some(complex_history.to_string()),
    );
    assert!(
        write_res.is_ok(),
        "Failed to write XMP with complex unicode characters"
    );

    // Act: Read sidecar back
    let read_data = xmp::read_xmp_sidecar(img_path.clone())
        .expect("Read Result::Err")
        .expect("Read None");

    // Assert exact string roundtrip preservation
    assert_eq!(read_data.rating, 5);
    assert_eq!(read_data.color_label, complex_label);
    assert_eq!(read_data.flag_status, complex_status);
    assert_eq!(read_data.tags, complex_tags);
    assert_eq!(read_data.history, vec![complex_history.to_string()]);

    // Clean up
    let _ = fs::remove_file(&sidecar_path);
}

#[test]
fn test_xmp_large_payload_and_malformed_xml_handling() {
    let temp_dir = std::env::temp_dir();
    let img_path = temp_dir
        .join("wiphoto_stress_large.jpg")
        .to_string_lossy()
        .to_string();
    let sidecar_path = std::path::Path::new(&img_path).with_extension("xmp");

    let _ = fs::remove_file(&sidecar_path);

    // 1. Write 500 tags
    let large_tags: Vec<String> = (0..500)
        .map(|i| format!("Tag_Category_{}_Value", i))
        .collect();
    let write_res = xmp::write_xmp_sidecar(
        img_path.clone(),
        3,
        "purple".to_string(),
        "picked".to_string(),
        large_tags.clone(),
        Some("Bulk tag assignment".to_string()),
    );
    assert!(write_res.is_ok());

    let read_data = xmp::read_xmp_sidecar(img_path.clone())
        .expect("Read Result::Err")
        .expect("Read None");
    assert_eq!(read_data.tags.len(), 500);
    assert_eq!(read_data.tags[499], "Tag_Category_499_Value");

    // 2. Test malformed XML parsing robustness
    let malformed_xmls = vec![
        "Not XML at all",
        "<x:xmpmeta><rdf:RDF><rdf:Description",
        "<?xml version=\"1.0\"?><x:xmpmeta><rdf:RDF><rdf:Description xmp:Rating=\"abc\"/></rdf:RDF></x:xmpmeta>",
        "",
    ];

    for xml_str in malformed_xmls {
        let parsed = xmp::parse_xmp_content(xml_str);
        if let Some(data) = parsed {
            // If parsed, rating should default to 0 gracefully
            assert_eq!(data.rating, 0);
        }
    }

    // Clean up
    let _ = fs::remove_file(&sidecar_path);
}
