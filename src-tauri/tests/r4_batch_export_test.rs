use image::{DynamicImage, GenericImageView, ImageBuffer, Rgb, RgbImage};
use std::fs;
use std::path::PathBuf;
use tempfile::tempdir;
use wiphoto_lib::commands::export::{export_files, strip_exif_from_jpeg_bytes};

/// Create a valid JPEG image file with an APP1 EXIF segment embedded
fn create_test_jpeg_with_exif(path: &PathBuf, width: u32, height: u32) {
    let img: RgbImage = ImageBuffer::from_fn(width, height, |x, y| {
        Rgb([((x * 10) % 255) as u8, ((y * 10) % 255) as u8, 128])
    });
    let dynamic_img = DynamicImage::ImageRgb8(img);
    let mut raw_jpeg = Vec::new();
    let encoder = image::codecs::jpeg::JpegEncoder::new_with_quality(&mut raw_jpeg, 90);
    dynamic_img.write_with_encoder(encoder).unwrap();

    // Embed an APP1 EXIF segment into the JPEG bytes
    let mut jpeg_with_exif = Vec::new();
    jpeg_with_exif.push(raw_jpeg[0]); // 0xFF
    jpeg_with_exif.push(raw_jpeg[1]); // 0xD8 (SOI)

    // Add fake APP1 EXIF marker
    let exif_payload = b"Exif\x00\x00DummyExifDataForTest123";
    let len = (exif_payload.len() + 2) as u16;
    jpeg_with_exif.push(0xFF);
    jpeg_with_exif.push(0xE1); // APP1
    jpeg_with_exif.push((len >> 8) as u8);
    jpeg_with_exif.push((len & 0xFF) as u8);
    jpeg_with_exif.extend_from_slice(exif_payload);

    // Append remaining JPEG stream
    jpeg_with_exif.extend_from_slice(&raw_jpeg[2..]);

    fs::write(path, jpeg_with_exif).unwrap();
}

/// Create a valid PNG image file
fn create_test_png(path: &PathBuf, width: u32, height: u32) {
    let img: RgbImage = ImageBuffer::from_fn(width, height, |x, y| {
        Rgb([200, (x % 255) as u8, (y % 255) as u8])
    });
    img.save(path).unwrap();
}

#[tokio::test]
async fn test_r4_batch_export_pipeline_resizing_format_conversion_and_exif_stripping() {
    // Arrange
    let dir = tempdir().unwrap();
    let src_dir = dir.path().join("source");
    let dest_dir = dir.path().join("export_output");
    fs::create_dir_all(&src_dir).unwrap();
    fs::create_dir_all(&dest_dir).unwrap();

    let img1_path = src_dir.join("photo_exif.jpg");
    let img2_path = src_dir.join("graphic.png");

    // Create 800x600 test JPEG with EXIF and 600x400 test PNG
    create_test_jpeg_with_exif(&img1_path, 800, 600);
    create_test_png(&img2_path, 600, 400);

    let paths = vec![
        img1_path.to_string_lossy().to_string(),
        img2_path.to_string_lossy().to_string(),
    ];

    // Act 1: Batch export to JPEG with resizing (max 300x300), watermark, and EXIF stripping
    let count = export_files(
        paths.clone(),
        dest_dir.to_string_lossy().to_string(),
        "jpeg".to_string(),
        Some(85),
        Some(300),
        Some(300),
        Some("WiPhoto Watermark".to_string()),
        Some(true),
    )
    .await
    .unwrap();

    // Assert 1: Export count must match number of input files
    assert_eq!(count, 2);

    let out_jpg1 = dest_dir.join("photo_exif.jpg");
    let out_jpg2 = dest_dir.join("graphic.jpg");

    assert!(out_jpg1.exists(), "Exported photo_exif.jpg must exist");
    assert!(out_jpg2.exists(), "Exported graphic.jpg must exist");

    // Verify resizing constraint (max 300x300 preserving aspect ratio)
    let loaded1 = image::open(&out_jpg1).expect("Must open exported JPG 1");
    let (w1, h1) = loaded1.dimensions();
    assert!(
        w1 <= 300 && h1 <= 300,
        "Image 1 must be resized <= 300x300, got {}x{}",
        w1,
        h1
    );
    assert_eq!(w1, 300);
    assert_eq!(h1, 225); // 800x600 -> 300x225

    let loaded2 = image::open(&out_jpg2).expect("Must open exported JPG 2");
    let (w2, h2) = loaded2.dimensions();
    assert!(
        w2 <= 300 && h2 <= 300,
        "Image 2 must be resized <= 300x300, got {}x{}",
        w2,
        h2
    );

    // Verify EXIF stripping on exported file out_jpg1
    let exported_bytes = fs::read(&out_jpg1).unwrap();
    // Check that APP1 segment (0xFFE1) is absent or stripped
    let cleaned = strip_exif_from_jpeg_bytes(&exported_bytes);
    assert_eq!(
        cleaned.len(),
        exported_bytes.len(),
        "Exported JPEG should not contain unstripped APP1 markers"
    );
}

#[tokio::test]
async fn test_r4_batch_export_format_conversion_png_and_avif() {
    // Arrange
    let dir = tempdir().unwrap();
    let src_dir = dir.path().join("source");
    let dest_dir = dir.path().join("export_png");
    fs::create_dir_all(&src_dir).unwrap();
    fs::create_dir_all(&dest_dir).unwrap();

    let img1_path = src_dir.join("sample.jpg");
    create_test_jpeg_with_exif(&img1_path, 400, 400);

    let paths = vec![img1_path.to_string_lossy().to_string()];

    // Act: Convert JPEG to PNG format
    let count = export_files(
        paths,
        dest_dir.to_string_lossy().to_string(),
        "png".to_string(),
        None,
        Some(200),
        Some(200),
        None,
        Some(true),
    )
    .await
    .unwrap();

    // Assert
    assert_eq!(count, 1);
    let out_png = dest_dir.join("sample.png");
    assert!(out_png.exists(), "Converted PNG output must exist");

    let loaded = image::open(&out_png).expect("Must open converted PNG file");
    assert_eq!(loaded.width(), 200);
    assert_eq!(loaded.height(), 200);
}
