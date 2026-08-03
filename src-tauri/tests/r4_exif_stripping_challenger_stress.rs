use image::{DynamicImage, GenericImageView, ImageBuffer, Rgb, RgbImage};
use std::fs;
use std::path::PathBuf;
use tempfile::tempdir;
use wiphoto_lib::commands::export::{
    export_files, strip_exif_from_jpeg_bytes, strip_exif_from_jpeg_file,
};

/// Helper: Create a JPEG with multiple APP1 markers (e.g. EXIF + XMP + Extended EXIF)
fn create_jpeg_with_multiple_app1_markers(width: u32, height: u32) -> Vec<u8> {
    let img: RgbImage = ImageBuffer::from_fn(width, height, |x, y| {
        Rgb([((x * 7) % 255) as u8, ((y * 13) % 255) as u8, 200])
    });
    let dynamic_img = DynamicImage::ImageRgb8(img);
    let mut raw_jpeg = Vec::new();
    let encoder = image::codecs::jpeg::JpegEncoder::new_with_quality(&mut raw_jpeg, 85);
    dynamic_img.write_with_encoder(encoder).unwrap();

    let mut out = Vec::new();
    // SOI
    out.push(raw_jpeg[0]); // 0xFF
    out.push(raw_jpeg[1]); // 0xD8

    // Marker 1: APP1 (EXIF)
    let app1_exif = b"Exif\x00\x00PrimaryExifPayload12345";
    let len1 = (app1_exif.len() + 2) as u16;
    out.push(0xFF);
    out.push(0xE1);
    out.push((len1 >> 8) as u8);
    out.push((len1 & 0xFF) as u8);
    out.extend_from_slice(app1_exif);

    // Marker 2: APP1 (XMP metadata)
    let app1_xmp = b"http://ns.adobe.com/xap/1.0/\x00<x:xmpmeta>xmp_data</x:xmpmeta>";
    let len2 = (app1_xmp.len() + 2) as u16;
    out.push(0xFF);
    out.push(0xE1);
    out.push((len2 >> 8) as u8);
    out.push((len2 & 0xFF) as u8);
    out.extend_from_slice(app1_xmp);

    // Marker 3: APP1 (Secondary EXIF / Extended)
    let app1_ext = b"Exif\x00\x00SecondaryExifBlock99999";
    let len3 = (app1_ext.len() + 2) as u16;
    out.push(0xFF);
    out.push(0xE1);
    out.push((len3 >> 8) as u8);
    out.push((len3 & 0xFF) as u8);
    out.extend_from_slice(app1_ext);

    // Append rest of valid JPEG stream
    out.extend_from_slice(&raw_jpeg[2..]);
    out
}

/// Helper: Count occurrences of APP1 marker pattern (0xFF, 0xE1) in raw byte buffer
fn count_app1_markers(data: &[u8]) -> usize {
    if data.len() < 2 {
        return 0;
    }
    let mut count = 0;
    for i in 0..data.len() - 1 {
        if data[i] == 0xFF && data[i + 1] == 0xE1 {
            count += 1;
        }
    }
    count
}

#[test]
fn test_stress_exif_stripping_multiple_app1_markers() {
    // Arrange
    let multi_app1_jpeg = create_jpeg_with_multiple_app1_markers(320, 240);
    let initial_app1_count = count_app1_markers(&multi_app1_jpeg);
    assert_eq!(
        initial_app1_count, 3,
        "Input JPEG should contain exactly 3 APP1 markers"
    );

    // Act
    let stripped = strip_exif_from_jpeg_bytes(&multi_app1_jpeg);

    // Assert
    let stripped_app1_count = count_app1_markers(&stripped);
    assert_eq!(
        stripped_app1_count, 0,
        "All APP1 markers must be completely stripped"
    );
    assert!(
        stripped.len() < multi_app1_jpeg.len(),
        "Stripped output must be smaller than input with multiple APP1 blocks"
    );

    // Verify JPEG remains valid and readable by image loader
    let reloaded = image::load_from_memory(&stripped);
    assert!(
        reloaded.is_ok(),
        "JPEG with stripped APP1 markers must remain valid and readable"
    );
    let (w, h) = reloaded.unwrap().dimensions();
    assert_eq!(w, 320);
    assert_eq!(h, 240);
}

#[test]
fn test_stress_exif_stripping_no_exif_tags() {
    // Arrange: Standard JPEG generated directly by encoder (no APP1 markers inserted)
    let img: RgbImage = ImageBuffer::from_fn(100, 100, |x, y| Rgb([(x % 255) as u8, (y % 255) as u8, 50]));
    let dynamic_img = DynamicImage::ImageRgb8(img);
    let mut raw_jpeg = Vec::new();
    let encoder = image::codecs::jpeg::JpegEncoder::new_with_quality(&mut raw_jpeg, 90);
    dynamic_img.write_with_encoder(encoder).unwrap();

    let app1_count = count_app1_markers(&raw_jpeg);
    assert_eq!(app1_count, 0, "Clean JPEG should contain 0 APP1 markers");

    // Act
    let stripped = strip_exif_from_jpeg_bytes(&raw_jpeg);

    // Assert
    assert_eq!(
        stripped, raw_jpeg,
        "JPEG without EXIF/APP1 tags must remain unchanged"
    );
}

#[test]
fn test_stress_exif_stripping_non_jpeg_files() {
    // 1. PNG Header & Bytes
    let png_bytes = vec![0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00, 0x00, 0x0D];
    let stripped_png = strip_exif_from_jpeg_bytes(&png_bytes);
    assert_eq!(stripped_png, png_bytes, "PNG bytes must remain untouched");

    // 2. WebP Header Bytes
    let webp_bytes = b"RIFF\x20\x00\x00\x00WEBPVP8 \x14\x00\x00\x00".to_vec();
    let stripped_webp = strip_exif_from_jpeg_bytes(&webp_bytes);
    assert_eq!(stripped_webp, webp_bytes, "WebP bytes must remain untouched");

    // 3. GIF Header Bytes
    let gif_bytes = b"GIF89a\x0A\x00\x0A\x00\x80\x00\x00".to_vec();
    let stripped_gif = strip_exif_from_jpeg_bytes(&gif_bytes);
    assert_eq!(stripped_gif, gif_bytes, "GIF bytes must remain untouched");

    // 4. Plain Text File
    let text_bytes = b"This is a text file, not a JPEG image.".to_vec();
    let stripped_text = strip_exif_from_jpeg_bytes(&text_bytes);
    assert_eq!(stripped_text, text_bytes, "Text bytes must remain untouched");

    // 5. Random Binary Data starting with 0xFF (not SOI)
    let random_bytes = vec![0xFF, 0x00, 0x12, 0x34, 0x56, 0x78, 0x90, 0xAB, 0xCD, 0xEF];
    let stripped_random = strip_exif_from_jpeg_bytes(&random_bytes);
    assert_eq!(stripped_random, random_bytes, "Arbitrary binary data starting with 0xFF must remain untouched");
}

#[test]
fn test_stress_exif_stripping_zero_byte_and_truncated_files() {
    // 0-byte file
    let empty_bytes: Vec<u8> = vec![];
    let stripped_empty = strip_exif_from_jpeg_bytes(&empty_bytes);
    assert_eq!(stripped_empty, empty_bytes, "0-byte slice must return empty slice without panic");

    // 1-byte file
    let byte_1 = vec![0xFF];
    assert_eq!(strip_exif_from_jpeg_bytes(&byte_1), byte_1);

    // 2-byte file (valid SOI only)
    let byte_2 = vec![0xFF, 0xD8];
    assert_eq!(strip_exif_from_jpeg_bytes(&byte_2), byte_2);

    // 3-byte truncated file
    let byte_3 = vec![0xFF, 0xD8, 0xFF];
    assert_eq!(strip_exif_from_jpeg_bytes(&byte_3), byte_3);

    // Test file operations on disk
    let dir = tempdir().unwrap();

    // Zero-byte file on disk
    let zero_path = dir.path().join("empty.jpg");
    fs::write(&zero_path, b"").unwrap();
    let result_zero = strip_exif_from_jpeg_file(&zero_path);
    assert!(result_zero.is_ok(), "strip_exif_from_jpeg_file on 0-byte file must succeed");
    assert_eq!(fs::metadata(&zero_path).unwrap().len(), 0);

    // Non-JPEG file on disk
    let txt_path = dir.path().join("document.txt");
    fs::write(&txt_path, b"Hello World").unwrap();
    let result_txt = strip_exif_from_jpeg_file(&txt_path);
    assert!(result_txt.is_ok(), "strip_exif_from_jpeg_file on non-JPEG file must succeed");
    assert_eq!(fs::read(&txt_path).unwrap(), b"Hello World");
}

#[tokio::test]
async fn test_stress_batch_export_mixed_files_with_exif_stripping() {
    // Arrange
    let dir = tempdir().unwrap();
    let src_dir = dir.path().join("src_mixed");
    let dest_dir = dir.path().join("out_mixed");
    fs::create_dir_all(&src_dir).unwrap();
    fs::create_dir_all(&dest_dir).unwrap();

    // 1. JPEG with multiple APP1 markers
    let multi_app1_path = src_dir.join("multi_app1.jpg");
    let jpeg_bytes = create_jpeg_with_multiple_app1_markers(400, 300);
    fs::write(&multi_app1_path, &jpeg_bytes).unwrap();

    // 2. Clean JPEG without APP1 markers
    let clean_jpeg_path = src_dir.join("clean.jpg");
    let img: RgbImage = ImageBuffer::from_fn(200, 200, |x, y| Rgb([(x % 255) as u8, 100, 50]));
    img.save(&clean_jpeg_path).unwrap();

    // 3. Non-JPEG text file
    let txt_path = src_dir.join("readme.txt");
    fs::write(&txt_path, b"Not an image").unwrap();

    // 4. Zero-byte file
    let zero_path = src_dir.join("corrupt.jpg");
    fs::write(&zero_path, b"").unwrap();

    let paths = vec![
        multi_app1_path.to_string_lossy().to_string(),
        clean_jpeg_path.to_string_lossy().to_string(),
        txt_path.to_string_lossy().to_string(),
        zero_path.to_string_lossy().to_string(),
    ];

    // Act: Batch export with strip_exif = Some(true)
    let export_res = export_files(
        paths,
        dest_dir.to_string_lossy().to_string(),
        "jpeg".to_string(),
        Some(90),
        Some(250),
        Some(250),
        None,
        Some(true),
    )
    .await;

    // Assert
    assert!(export_res.is_ok(), "Batch export must execute without error");
    let count = export_res.unwrap();
    assert_eq!(count, 2, "Only valid images (multi_app1.jpg and clean.jpg) should be processed");

    let out_multi = dest_dir.join("multi_app1.jpg");
    assert!(out_multi.exists(), "Exported multi_app1.jpg must exist");
    let out_multi_bytes = fs::read(&out_multi).unwrap();
    assert_eq!(
        count_app1_markers(&out_multi_bytes),
        0,
        "Exported JPEG must have 0 APP1 markers"
    );

    let out_clean = dest_dir.join("clean.jpg");
    assert!(out_clean.exists(), "Exported clean.jpg must exist");
    let out_clean_bytes = fs::read(&out_clean).unwrap();
    assert_eq!(
        count_app1_markers(&out_clean_bytes),
        0,
        "Exported clean JPEG must have 0 APP1 markers"
    );
}
