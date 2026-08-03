use image::{DynamicImage, GenericImageView, ImageBuffer, Rgb, RgbImage};
use std::fs;
use std::path::PathBuf;
use tempfile::tempdir;
use wiphoto_lib::commands::export::{export_files, load_jxl};

fn create_test_jpeg(path: &PathBuf, width: u32, height: u32) {
    let img: RgbImage = ImageBuffer::from_fn(width, height, |x, y| {
        Rgb([((x * 7) % 255) as u8, ((y * 13) % 255) as u8, 200])
    });
    let dynamic_img = DynamicImage::ImageRgb8(img);
    let mut file = fs::File::create(path).unwrap();
    let encoder = image::codecs::jpeg::JpegEncoder::new_with_quality(&mut file, 90);
    dynamic_img.write_with_encoder(encoder).unwrap();
}

#[tokio::test]
async fn test_batch_export_resizing_scaling_up() {
    let dir = tempdir().unwrap();
    let src_dir = dir.path().join("source");
    let dest_dir = dir.path().join("export_up");
    fs::create_dir_all(&src_dir).unwrap();
    fs::create_dir_all(&dest_dir).unwrap();

    let img_path = src_dir.join("tiny.jpg");
    create_test_jpeg(&img_path, 100, 50);

    let count = export_files(
        vec![img_path.to_string_lossy().to_string()],
        dest_dir.to_string_lossy().to_string(),
        "jpeg".to_string(),
        Some(90),
        Some(500),
        Some(500),
        None,
        Some(false),
    )
    .await
    .unwrap();

    assert_eq!(count, 1);
    let out_path = dest_dir.join("tiny.jpg");
    let loaded = image::open(&out_path).unwrap();
    let (w, h) = loaded.dimensions();
    // 100x50 scaled up into 500x500 box maintaining 2:1 aspect ratio -> 500x250
    assert_eq!(w, 500);
    assert_eq!(h, 250);
}

#[tokio::test]
async fn test_batch_export_resizing_scaling_down() {
    let dir = tempdir().unwrap();
    let src_dir = dir.path().join("source");
    let dest_dir = dir.path().join("export_down");
    fs::create_dir_all(&src_dir).unwrap();
    fs::create_dir_all(&dest_dir).unwrap();

    let img_path = src_dir.join("large.jpg");
    create_test_jpeg(&img_path, 2400, 1800); // 4:3 ratio

    let count = export_files(
        vec![img_path.to_string_lossy().to_string()],
        dest_dir.to_string_lossy().to_string(),
        "jpeg".to_string(),
        Some(90),
        Some(400),
        Some(400),
        None,
        Some(false),
    )
    .await
    .unwrap();

    assert_eq!(count, 1);
    let out_path = dest_dir.join("large.jpg");
    let loaded = image::open(&out_path).unwrap();
    let (w, h) = loaded.dimensions();
    // 2400x1800 scaled down into 400x400 box -> 400x300
    assert_eq!(w, 400);
    assert_eq!(h, 300);
}

#[tokio::test]
async fn test_batch_export_resizing_non_square_aspect_ratios() {
    let dir = tempdir().unwrap();
    let src_dir = dir.path().join("source");
    let dest_dir = dir.path().join("export_aspects");
    fs::create_dir_all(&src_dir).unwrap();
    fs::create_dir_all(&dest_dir).unwrap();

    let ultrawide = src_dir.join("ultrawide.jpg");
    let tall_portrait = src_dir.join("portrait.jpg");
    let widescreen = src_dir.join("widescreen.jpg");

    create_test_jpeg(&ultrawide, 1600, 400); // 4:1
    create_test_jpeg(&tall_portrait, 400, 1600); // 1:4
    create_test_jpeg(&widescreen, 1920, 1080); // 16:9

    let paths = vec![
        ultrawide.to_string_lossy().to_string(),
        tall_portrait.to_string_lossy().to_string(),
        widescreen.to_string_lossy().to_string(),
    ];

    let count = export_files(
        paths,
        dest_dir.to_string_lossy().to_string(),
        "jpeg".to_string(),
        Some(90),
        Some(400),
        Some(300),
        None,
        Some(false),
    )
    .await
    .unwrap();

    assert_eq!(count, 3);

    let uw_out = image::open(dest_dir.join("ultrawide.jpg")).unwrap();
    let (uw_w, uw_h) = uw_out.dimensions();
    assert_eq!(uw_w, 400);
    assert_eq!(uw_h, 100);

    let port_out = image::open(dest_dir.join("portrait.jpg")).unwrap();
    let (port_w, port_h) = port_out.dimensions();
    assert_eq!(port_w, 75);
    assert_eq!(port_h, 300);

    let ws_out = image::open(dest_dir.join("widescreen.jpg")).unwrap();
    let (ws_w, ws_h) = ws_out.dimensions();
    assert_eq!(ws_w, 400);
    assert_eq!(ws_h, 225);
}

#[tokio::test]
async fn test_format_conversion_jpeg_to_png_and_avif() {
    let dir = tempdir().unwrap();
    let src_dir = dir.path().join("source");
    let dest_dir = dir.path().join("export_formats");
    fs::create_dir_all(&src_dir).unwrap();
    fs::create_dir_all(&dest_dir).unwrap();

    let img_path = src_dir.join("input.jpg");
    create_test_jpeg(&img_path, 400, 300);

    let paths = vec![img_path.to_string_lossy().to_string()];

    // Test JPEG to PNG
    let count_png = export_files(
        paths.clone(),
        dest_dir.to_string_lossy().to_string(),
        "png".to_string(),
        None,
        None,
        None,
        None,
        Some(false),
    )
    .await
    .unwrap();
    assert_eq!(count_png, 1);
    let png_file = dest_dir.join("input.png");
    assert!(png_file.exists());
    let png_img = image::open(&png_file).unwrap();
    assert_eq!(png_img.width(), 400);
    assert_eq!(png_img.height(), 300);

    // Test JPEG to AVIF
    let count_avif = export_files(
        paths,
        dest_dir.to_string_lossy().to_string(),
        "avif".to_string(),
        None,
        Some(200),
        Some(150),
        None,
        Some(false),
    )
    .await
    .unwrap();
    assert_eq!(count_avif, 1);
    let avif_file = dest_dir.join("input.avif");
    assert!(avif_file.exists());
    if let Ok(avif_img) = image::open(&avif_file) {
        assert_eq!(avif_img.width(), 200);
        assert_eq!(avif_img.height(), 150);
    }
}

#[tokio::test]
async fn test_jxl_loader_invalid_file_handling() {
    let dir = tempdir().unwrap();
    let dummy_path = dir.path().join("fake.jxl");
    fs::write(&dummy_path, b"not a real jxl file").unwrap();

    // load_jxl must return None for invalid JXL bytes rather than panic
    let result = load_jxl(&dummy_path);
    assert!(result.is_none());
}
