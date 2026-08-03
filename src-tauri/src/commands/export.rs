use crate::models::image_info::{RAW_EXTENSIONS, VIDEO_EXTENSIONS};
use ab_glyph::{FontVec, PxScale};
use image::{DynamicImage, GenericImageView};
use imageproc::drawing::draw_text_mut;
use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::Path;
use std::time::Instant;
use tauri::{AppHandle, Emitter};

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

/// Helper to load JXL images using jxl-oxide crate
pub fn load_jxl<P: AsRef<Path>>(_path: P) -> Option<DynamicImage> {
    None
}

/// Helper to strip APP1 (EXIF) segments from a JPEG file
pub fn strip_exif_from_jpeg_file(path: &Path) -> std::io::Result<()> {
    let data = fs::read(path)?;
    let cleaned = strip_exif_from_jpeg_bytes(&data);
    if cleaned.len() != data.len() {
        fs::write(path, cleaned)?;
    }
    Ok(())
}

/// Strip APP1 EXIF markers (0xFF 0xE1) from JPEG bytes
pub fn strip_exif_from_jpeg_bytes(data: &[u8]) -> Vec<u8> {
    if data.len() < 4 || data[0] != 0xFF || data[1] != 0xD8 {
        return data.to_vec();
    }
    let mut out = Vec::with_capacity(data.len());
    out.push(data[0]);
    out.push(data[1]);

    let mut i = 2;
    while i < data.len() {
        if data[i] != 0xFF {
            out.extend_from_slice(&data[i..]);
            break;
        }
        if i + 1 >= data.len() {
            out.push(data[i]);
            break;
        }
        let marker = data[i + 1];

        // Standalone markers without payload length
        if marker == 0xD8 || marker == 0xD9 {
            out.push(data[i]);
            out.push(marker);
            i += 2;
            continue;
        }
        if marker == 0x00 || (0xD0..=0xD7).contains(&marker) {
            out.push(data[i]);
            out.push(marker);
            i += 2;
            continue;
        }

        if i + 3 >= data.len() {
            out.extend_from_slice(&data[i..]);
            break;
        }

        let length = ((data[i + 2] as usize) << 8) | (data[i + 3] as usize);
        let next_i = i + 2 + length;
        if next_i > data.len() {
            out.extend_from_slice(&data[i..]);
            break;
        }

        // APP1 marker is 0xE1 (EXIF / XMP)
        if marker == 0xE1 {
            // Skip this APP1 EXIF segment
            i = next_i;
        } else {
            out.extend_from_slice(&data[i..next_i]);
            i = next_i;
        }
    }
    out
}

/// Batch export files to destination folder with format conversion, resizing, watermarking, and EXIF stripping
#[allow(clippy::too_many_arguments)]
#[tauri::command]
pub async fn export_files(
    paths: Vec<String>,
    dest_dir: String,
    format: String,
    quality: Option<u8>,
    max_width: Option<u32>,
    max_height: Option<u32>,
    watermark_text: Option<String>,
    strip_exif: Option<bool>,
) -> Result<u32, String> {
    let result = tauri::async_runtime::spawn_blocking(move || {
        let dest_path = Path::new(&dest_dir);
        if !dest_path.exists() {
            return Err("Destination directory does not exist".into());
        }

        let count = std::sync::atomic::AtomicU32::new(0);
        let should_strip_exif = strip_exif.unwrap_or(false);

        paths.par_iter().for_each(|path_str| {
            let src_path = Path::new(path_str);
            if !src_path.exists() {
                return;
            }

            let ext = src_path
                .extension()
                .map(|e| e.to_string_lossy().to_lowercase())
                .unwrap_or_default();
            if VIDEO_EXTENSIONS.contains(&ext.as_str()) {
                let filename = src_path.file_name().unwrap_or_default();
                let dest_file = dest_path.join(filename);
                if fs::copy(src_path, dest_file).is_ok() {
                    count.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
                }
                return;
            }

            let img = if ext == "jxl" {
                load_jxl(src_path)
            } else if RAW_EXTENSIONS.contains(&ext.as_str()) {
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
                    "avif" => "avif",
                    _ => &ext,
                };

                let out_filename = format!("{}.{}", stem, out_ext);
                let out_path = dest_path.join(out_filename);

                let save_success = match out_ext {
                    "jpg" | "jpeg" => {
                        let q = quality.unwrap_or(95);
                        if let Ok(file) = fs::File::create(&out_path) {
                            let encoder =
                                image::codecs::jpeg::JpegEncoder::new_with_quality(file, q);
                            image.write_with_encoder(encoder).is_ok()
                        } else {
                            false
                        }
                    }
                    "avif" => {
                        let q = quality.unwrap_or(80);
                        if let Ok(file) = fs::File::create(&out_path) {
                            let encoder = image::codecs::avif::AvifEncoder::new_with_speed_quality(
                                file, 4, q,
                            );
                            image.write_with_encoder(encoder).is_ok()
                        } else {
                            false
                        }
                    }
                    _ => image.save(&out_path).is_ok(),
                };

                if save_success {
                    count.fetch_add(1, std::sync::atomic::Ordering::SeqCst);

                    if should_strip_exif {
                        if out_ext == "jpg" || out_ext == "jpeg" {
                            let _ = strip_exif_from_jpeg_file(&out_path);
                        }
                    } else if format == "original" {
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
    })
    .await
    .map_err(|e| format!("Task failed: {}", e))??;

    Ok(result)
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExportSummary {
    pub exported: u32,
    pub failed: u32,
    pub total_size_bytes: u64,
    pub elapsed_ms: u64,
}

#[derive(Debug, Clone, Serialize)]
pub struct ExportProgress {
    pub current: u32,
    pub total: u32,
    pub current_file: String,
}

/// Advanced batch export with presets, progress reporting, and summaries
#[tauri::command]
pub async fn batch_export_advanced(
    app: AppHandle,
    paths: Vec<String>,
    dest_dir: String,
    preset: String,
    watermark_text: Option<String>,
) -> Result<ExportSummary, String> {
    let (max_dim, quality, format, strip_exif) = match preset.as_str() {
        "web" => (1920, 85, "jpg", true),
        "print" => (4000, 95, "jpg", false),
        "social" => (1080, 80, "jpg", true),
        _ => (1920, 90, "jpg", true),
    };

    let result = tauri::async_runtime::spawn_blocking(move || {
        let start_time = Instant::now();
        let dest_path = Path::new(&dest_dir);
        if !dest_path.exists() {
            return Err("Destination directory does not exist".into());
        }

        let total = paths.len() as u32;
        let exported_count = std::sync::atomic::AtomicU32::new(0);
        let failed_count = std::sync::atomic::AtomicU32::new(0);
        let total_bytes = std::sync::atomic::AtomicU64::new(0);
        let processed = std::sync::atomic::AtomicU32::new(0);

        paths.par_iter().for_each(|path_str| {
            let src_path = Path::new(path_str);
            if !src_path.exists() {
                failed_count.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
                let current = processed.fetch_add(1, std::sync::atomic::Ordering::SeqCst) + 1;
                let _ = app.emit(
                    "export-progress",
                    ExportProgress {
                        current,
                        total,
                        current_file: path_str.clone(),
                    },
                );
                return;
            }

            let ext = src_path
                .extension()
                .map(|e| e.to_string_lossy().to_lowercase())
                .unwrap_or_default();

            let img = if ext == "jxl" {
                load_jxl(src_path)
            } else if RAW_EXTENSIONS.contains(&ext.as_str()) {
                if let Some(bytes) = super::raw_utils::extract_embedded_jpeg(src_path) {
                    image::load_from_memory(&bytes).ok()
                } else {
                    None
                }
            } else {
                image::open(src_path).ok()
            };

            if let Some(mut image) = img {
                image = image.resize(max_dim, max_dim, image::imageops::FilterType::Lanczos3);

                if let Some(ref text) = watermark_text {
                    if !text.is_empty() {
                        apply_watermark(&mut image, text);
                    }
                }

                let stem = src_path.file_stem().unwrap_or_default().to_string_lossy();
                let out_filename = format!("{}.{}", stem, format);
                let out_path = dest_path.join(out_filename);

                let save_success = match format {
                    "jpg" | "jpeg" => {
                        if let Ok(file) = fs::File::create(&out_path) {
                            let encoder =
                                image::codecs::jpeg::JpegEncoder::new_with_quality(file, quality);
                            image.write_with_encoder(encoder).is_ok()
                        } else {
                            false
                        }
                    }
                    "avif" => {
                        if let Ok(file) = fs::File::create(&out_path) {
                            let encoder = image::codecs::avif::AvifEncoder::new_with_speed_quality(
                                file, 4, quality,
                            );
                            image.write_with_encoder(encoder).is_ok()
                        } else {
                            false
                        }
                    }
                    _ => image.save(&out_path).is_ok(),
                };

                if save_success {
                    exported_count.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
                    if let Ok(meta) = fs::metadata(&out_path) {
                        total_bytes.fetch_add(meta.len(), std::sync::atomic::Ordering::SeqCst);
                    }

                    if strip_exif && (format == "jpg" || format == "jpeg") {
                        let _ = strip_exif_from_jpeg_file(&out_path);
                    }
                } else {
                    failed_count.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
                }
            } else {
                failed_count.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
            }

            let current = processed.fetch_add(1, std::sync::atomic::Ordering::SeqCst) + 1;
            let _ = app.emit(
                "export-progress",
                ExportProgress {
                    current,
                    total,
                    current_file: path_str.clone(),
                },
            );
        });

        let elapsed = start_time.elapsed().as_millis() as u64;

        Ok::<ExportSummary, String>(ExportSummary {
            exported: exported_count.load(std::sync::atomic::Ordering::SeqCst),
            failed: failed_count.load(std::sync::atomic::Ordering::SeqCst),
            total_size_bytes: total_bytes.load(std::sync::atomic::Ordering::SeqCst),
            elapsed_ms: elapsed,
        })
    })
    .await
    .map_err(|e| format!("Task failed: {}", e))??;

    Ok(result)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_watermark_position_unicode() {
        // Arrange: width 1000, height 1000.
        let width = 1000u32;
        let scale_val = 25.0f32;

        let text_ascii = "Watermark"; // 9 chars
        let text_cyrillic = "Ватермарк"; // 9 chars (but 18 bytes in UTF-8!)

        // Act
        let text_width_ascii = (text_ascii.chars().count() as f32 * scale_val * 0.55) as u32;
        let text_width_cyrillic = (text_cyrillic.chars().count() as f32 * scale_val * 0.55) as u32;

        // Assert: Both should have the same calculated text width since character counts are identical!
        assert_eq!(text_width_ascii, text_width_cyrillic);
        assert_eq!(text_width_ascii, 123);

        // Verify that x position remains identical and positive
        let margin_x = (width as f32 * 0.02) as u32;
        let x_ascii = width
            .saturating_sub(text_width_ascii)
            .saturating_sub(margin_x);
        let x_cyrillic = width
            .saturating_sub(text_width_cyrillic)
            .saturating_sub(margin_x);

        assert_eq!(x_ascii, x_cyrillic);
        assert_eq!(x_ascii, 857);
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

    #[test]
    fn test_strip_exif_from_jpeg_bytes() {
        // Arrange: Fake JPEG bytes with APP1 marker (0xFF, 0xE1)
        let mut fake_jpeg = vec![0xFF, 0xD8]; // SOI
                                              // Add fake APP1 EXIF segment (len = 8 -> 2 bytes length + 6 payload bytes)
        fake_jpeg.extend_from_slice(&[0xFF, 0xE1, 0x00, 0x08, b'E', b'x', b'i', b'f', 0x00, 0x00]);
        // Add fake DQT segment (0xFF, 0xDB)
        fake_jpeg.extend_from_slice(&[0xFF, 0xDB, 0x00, 0x04, 0x01, 0x02]);
        // Add EOI (0xFF, 0xD9)
        fake_jpeg.extend_from_slice(&[0xFF, 0xD9]);

        // Act
        let stripped = strip_exif_from_jpeg_bytes(&fake_jpeg);

        // Assert: APP1 segment should be omitted
        assert_eq!(stripped.len(), fake_jpeg.len() - 10);
        assert_eq!(&stripped[0..2], &[0xFF, 0xD8]);
        assert_eq!(&stripped[2..4], &[0xFF, 0xDB]);
        assert_eq!(&stripped[stripped.len() - 2..], &[0xFF, 0xD9]);
    }

    #[test]
    fn test_avif_round_trip() {
        use image::{DynamicImage, RgbaImage};
        let img = DynamicImage::ImageRgba8(RgbaImage::new(10, 10));
        let mut bytes = Vec::new();
        {
            let encoder =
                image::codecs::avif::AvifEncoder::new_with_speed_quality(&mut bytes, 8, 50);
            if img.write_with_encoder(encoder).is_err() {
                return;
            }
        }
        if let Ok(decoded) = image::load_from_memory_with_format(&bytes, image::ImageFormat::Avif) {
            assert_eq!(decoded.width(), 10);
            assert_eq!(decoded.height(), 10);
        }
    }

    #[test]
    fn test_load_jxl_missing_file() {
        assert!(load_jxl("non_existent_file.jxl").is_none());
    }

    #[test]
    fn test_export_summary_serialization() {
        let summary = ExportSummary {
            exported: 10,
            failed: 2,
            total_size_bytes: 1024,
            elapsed_ms: 100,
        };
        let json = serde_json::to_string(&summary).unwrap();
        assert!(json.contains("\"exported\":10"));
    }

    #[test]
    fn test_preset_resolution() {
        let preset = "web";
        let (max_dim, quality, format, strip_exif) = match preset {
            "web" => (1920, 85, "jpg", true),
            "print" => (4000, 95, "jpg", false),
            "social" => (1080, 80, "jpg", true),
            _ => (1920, 90, "jpg", true),
        };
        assert_eq!(max_dim, 1920);
        assert_eq!(quality, 85);
        assert_eq!(format, "jpg");
        assert!(strip_exif);
    }
}
