use crate::models::image_info::{RAW_EXTENSIONS, VIDEO_EXTENSIONS};
use image::{DynamicImage, GenericImageView};
use rayon::prelude::*;
use std::fs;
use std::path::Path;
use ab_glyph::{FontVec, PxScale};
use imageproc::drawing::draw_text_mut;

fn load_system_font() -> Option<FontVec> {
    let font_paths = [
        "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\segoeui.ttf",
        "C:\\Windows\\Fonts\\calibri.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Cache/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ];
    for path in &font_paths {
        if let Ok(bytes) = fs::read(path) {
            if let Ok(font) = FontVec::try_from_vec(bytes) {
                return Some(font);
            }
        }
    }
    None
}

fn apply_watermark(img: &mut DynamicImage, text: &str) {
    if let Some(font) = load_system_font() {
        let (width, height) = img.dimensions();
        let scale_val = (width as f32 * 0.025).clamp(16.0, 72.0);
        let scale = PxScale::from(scale_val);

        let text_width = (text.chars().count() as f32 * scale_val * 0.55) as u32;
        let text_height = scale_val as u32;

        let margin_x = (width as f32 * 0.02) as u32;
        let margin_y = (height as f32 * 0.02) as u32;

        let x = width.saturating_sub(text_width).saturating_sub(margin_x) as i32;
        let y = height.saturating_sub(text_height).saturating_sub(margin_y) as i32;

        let mut rgba_img = img.to_rgba8();

        // Shadow
        draw_text_mut(
            &mut rgba_img,
            image::Rgba([0, 0, 0, 180]),
            x + 2,
            y + 2,
            scale,
            &font,
            text,
        );

        // White Text
        draw_text_mut(
            &mut rgba_img,
            image::Rgba([255, 255, 255, 255]),
            x,
            y,
            scale,
            &font,
            text,
        );

        *img = DynamicImage::ImageRgba8(rgba_img);
    }
}

/// Batch export files to destination folder with format conversion, resizing, and watermarking
#[tauri::command]
pub async fn export_files(
    paths: Vec<String>,
    dest_dir: String,
    format: String,
    quality: Option<u8>,
    max_width: Option<u32>,
    max_height: Option<u32>,
    watermark_text: Option<String>,
) -> Result<u32, String> {
    let result = tauri::async_runtime::spawn_blocking(move || {
        let dest_path = Path::new(&dest_dir);
        if !dest_path.exists() {
            return Err("Destination directory does not exist".into());
        }

        let count = std::sync::atomic::AtomicU32::new(0);

        paths.par_iter().for_each(|path_str| {
            let src_path = Path::new(path_str);
            if !src_path.exists() {
                return;
            }

            let ext = src_path.extension().map(|e| e.to_string_lossy().to_lowercase()).unwrap_or_default();
            if VIDEO_EXTENSIONS.contains(&ext.as_str()) {
                let filename = src_path.file_name().unwrap_or_default();
                let dest_file = dest_path.join(filename);
                if fs::copy(src_path, dest_file).is_ok() {
                    count.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
                }
                return;
            }

            let img = if RAW_EXTENSIONS.contains(&ext.as_str()) {
                if let Some(bytes) = super::raw_utils::extract_embedded_jpeg(src_path) {
                    image::load_from_memory(&bytes).ok()
                } else {
                    None
                }
            } else {
                image::open(src_path).ok()
            };

            if let Some(mut image) = img {
                if max_width.is_some() || max_height.is_some() {
                    let w = max_width.unwrap_or(u32::MAX);
                    let h = max_height.unwrap_or(u32::MAX);
                    image = image.resize(w, h, image::imageops::FilterType::Lanczos3);
                }

                if let Some(ref text) = watermark_text {
                    if !text.is_empty() {
                        apply_watermark(&mut image, text);
                    }
                }

                let stem = src_path.file_stem().unwrap_or_default().to_string_lossy();
                let out_ext = match format.as_str() {
                    "jpeg" | "jpg" => "jpg",
                    "png" => "png",
                    "webp" => "webp",
                    _ => &ext,
                };

                let out_filename = format!("{}.{}", stem, out_ext);
                let out_path = dest_path.join(out_filename);

                let save_success = match out_ext {
                    "jpg" | "jpeg" => {
                        let q = quality.unwrap_or(95);
                        if let Ok(file) = fs::File::create(&out_path) {
                            let encoder = image::codecs::jpeg::JpegEncoder::new_with_quality(file, q);
                            image.write_with_encoder(encoder).is_ok()
                        } else {
                            false
                        }
                    }
                    _ => {
                        image.save(&out_path).is_ok()
                    }
                };

                if save_success {
                    count.fetch_add(1, std::sync::atomic::Ordering::SeqCst);

                    if format == "original" {
                        let xmp_src = src_path.with_extension("xmp");
                        if xmp_src.exists() {
                            let xmp_dest = out_path.with_extension("xmp");
                            let _ = fs::copy(&xmp_src, xmp_dest);
                        }
                    }
                }
            }
        });

        Ok::<u32, String>(count.load(std::sync::atomic::Ordering::SeqCst))
    }).await.map_err(|e| format!("Task failed: {}", e))??;

    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_watermark_position_unicode() {
        // Arrange: width 1000, height 1000.
        // scale_val = (1000 * 0.025).max(16.0).min(72.0) = 25.0
        // scale_val * 0.55 = 13.75
        let width = 1000u32;
        let scale_val = 25.0f32;
        
        let text_ascii = "Watermark"; // 9 chars
        let text_cyrillic = "Ватермарк"; // 9 chars (but 18 bytes in UTF-8!)

        // Act
        let text_width_ascii = (text_ascii.chars().count() as f32 * scale_val * 0.55) as u32;
        let text_width_cyrillic = (text_cyrillic.chars().count() as f32 * scale_val * 0.55) as u32;

        // Assert: Both should have the same calculated text width since character counts are identical!
        assert_eq!(text_width_ascii, text_width_cyrillic);
        assert_eq!(text_width_ascii, 123); // 9 * 25 * 0.55 = 123.75 -> 123

        // Verify that x position remains identical and positive
        let margin_x = (width as f32 * 0.02) as u32; // 20
        let x_ascii = width.saturating_sub(text_width_ascii).saturating_sub(margin_x);
        let x_cyrillic = width.saturating_sub(text_width_cyrillic).saturating_sub(margin_x);

        assert_eq!(x_ascii, x_cyrillic);
        assert_eq!(x_ascii, 857); // 1000 - 123 - 20 = 857
    }

    #[test]
    fn test_apply_watermark_no_panic() {
        // Arrange
        let mut img = image::DynamicImage::ImageRgba8(image::RgbaImage::new(100, 100));
        let text = "Test Watermark";

        // Act
        apply_watermark(&mut img, text);

        // Assert
        assert_eq!(img.width(), 100);
        assert_eq!(img.height(), 100);
    }
}
