use base64::{engine::general_purpose::STANDARD, Engine};
use image::{DynamicImage, GenericImageView, ImageBuffer, Rgba};
use std::path::Path;

/// Apply an edit operation to an image and return base64 result
#[tauri::command]
pub fn apply_edit(
    path: String,
    operations: Vec<EditOp>,
    max_preview_size: Option<u32>,
) -> Result<String, String> {
    let mut img = image::open(&path).map_err(|e| format!("Failed to open: {}", e))?;

    // Resize for preview if needed
    if let Some(max) = max_preview_size {
        let (w, h) = img.dimensions();
        if w > max || h > max {
            img = img.resize(max, max, image::imageops::FilterType::Lanczos3);
        }
    }

    // Apply operations sequentially
    for op in &operations {
        img = apply_single_edit(img, op);
    }

    // Encode result
    let mut buf = Vec::new();
    let mut cursor = std::io::Cursor::new(&mut buf);
    img.write_to(&mut cursor, image::ImageFormat::Jpeg)
        .map_err(|e| format!("Failed to encode: {}", e))?;
    Ok(STANDARD.encode(&buf))
}

/// Save edited image to disk
#[tauri::command]
pub fn save_edited(
    path: String,
    operations: Vec<EditOp>,
    output_path: Option<String>,
    quality: Option<u8>,
) -> Result<String, String> {
    let mut img = image::open(&path).map_err(|e| format!("Failed to open: {}", e))?;

    for op in &operations {
        img = apply_single_edit(img, op);
    }

    let save_path = output_path.unwrap_or_else(|| {
        let p = Path::new(&path);
        let stem = p.file_stem().unwrap_or_default().to_string_lossy();
        let ext = p.extension().unwrap_or_default().to_string_lossy();
        let parent = p.parent().unwrap_or(Path::new("."));
        parent
            .join(format!("{}_edited.{}", stem, if ext.is_empty() { "jpg" } else { &ext }))
            .to_string_lossy()
            .to_string()
    });

    let save_ext = Path::new(&save_path)
        .extension()
        .unwrap_or_default()
        .to_string_lossy()
        .to_lowercase();

    match save_ext.as_str() {
        "jpg" | "jpeg" => {
            let q = quality.unwrap_or(95);
            let encoder = image::codecs::jpeg::JpegEncoder::new_with_quality(
                std::fs::File::create(&save_path).map_err(|e| e.to_string())?,
                q,
            );
            img.write_with_encoder(encoder).map_err(|e| e.to_string())?;
        }
        "png" => {
            img.save(&save_path).map_err(|e| e.to_string())?;
        }
        _ => {
            img.save(&save_path).map_err(|e| e.to_string())?;
        }
    }

    Ok(save_path)
}

#[derive(serde::Deserialize, Clone, Debug)]
pub struct EditOp {
    pub tool: String,
    pub value: f64,
}

fn apply_single_edit(img: DynamicImage, op: &EditOp) -> DynamicImage {
    match op.tool.as_str() {
        "exposure" => adjust_exposure(img, op.value),
        "contrast" => adjust_contrast(img, op.value),
        "brightness" => adjust_brightness(img, op.value),
        "highlights" => adjust_highlights(img, op.value),
        "shadows" => adjust_shadows(img, op.value),
        "whites" => adjust_whites(img, op.value),
        "blacks" => adjust_blacks(img, op.value),
        "temperature" => adjust_temperature(img, op.value),
        "tint" => adjust_tint(img, op.value),
        "vibrance" => adjust_vibrance(img, op.value),
        "saturation" => adjust_saturation(img, op.value),
        "clarity" => adjust_clarity(img, op.value),
        "sharpness" => adjust_sharpness(img, op.value),
        "vignette" => apply_vignette(img, op.value),
        "rotate" => rotate_image(img, op.value),
        "flip_h" => DynamicImage::ImageRgba8(image::imageops::flip_horizontal(&img)),
        "flip_v" => DynamicImage::ImageRgba8(image::imageops::flip_vertical(&img)),
        "crop" => img, // crop handled separately with rect
        _ => img,
    }
}

fn clamp(val: f64, min: f64, max: f64) -> f64 {
    val.max(min).min(max)
}

fn clamp_u8(val: f64) -> u8 {
    clamp(val, 0.0, 255.0) as u8
}

fn adjust_exposure(img: DynamicImage, value: f64) -> DynamicImage {
    // value: -5.0 to +5.0, 0 = no change
    let factor = (2.0f64).powf(value);
    let rgba = img.to_rgba8();
    let (w, h) = rgba.dimensions();
    let mut out = ImageBuffer::new(w, h);
    for (x, y, pixel) in rgba.enumerate_pixels() {
        let r = clamp_u8(pixel[0] as f64 * factor);
        let g = clamp_u8(pixel[1] as f64 * factor);
        let b = clamp_u8(pixel[2] as f64 * factor);
        out.put_pixel(x, y, Rgba([r, g, b, pixel[3]]));
    }
    DynamicImage::ImageRgba8(out)
}

fn adjust_contrast(img: DynamicImage, value: f64) -> DynamicImage {
    // value: -100 to +100
    let factor = (259.0 * (value + 255.0)) / (255.0 * (259.0 - value));
    let rgba = img.to_rgba8();
    let (w, h) = rgba.dimensions();
    let mut out = ImageBuffer::new(w, h);
    for (x, y, pixel) in rgba.enumerate_pixels() {
        let r = clamp_u8(factor * (pixel[0] as f64 - 128.0) + 128.0);
        let g = clamp_u8(factor * (pixel[1] as f64 - 128.0) + 128.0);
        let b = clamp_u8(factor * (pixel[2] as f64 - 128.0) + 128.0);
        out.put_pixel(x, y, Rgba([r, g, b, pixel[3]]));
    }
    DynamicImage::ImageRgba8(out)
}

fn adjust_brightness(img: DynamicImage, value: f64) -> DynamicImage {
    // value: -100 to +100
    let rgba = img.to_rgba8();
    let (w, h) = rgba.dimensions();
    let mut out = ImageBuffer::new(w, h);
    for (x, y, pixel) in rgba.enumerate_pixels() {
        let r = clamp_u8(pixel[0] as f64 + value);
        let g = clamp_u8(pixel[1] as f64 + value);
        let b = clamp_u8(pixel[2] as f64 + value);
        out.put_pixel(x, y, Rgba([r, g, b, pixel[3]]));
    }
    DynamicImage::ImageRgba8(out)
}

fn adjust_highlights(img: DynamicImage, value: f64) -> DynamicImage {
    // Affects bright areas only. value: -100 to +100
    let amount = value / 100.0;
    let rgba = img.to_rgba8();
    let (w, h) = rgba.dimensions();
    let mut out = ImageBuffer::new(w, h);
    for (x, y, pixel) in rgba.enumerate_pixels() {
        let luminance = 0.299 * pixel[0] as f64 + 0.587 * pixel[1] as f64 + 0.114 * pixel[2] as f64;
        let mask = (luminance / 255.0).powf(2.0); // Highlight mask
        let adjustment = amount * mask * 60.0;
        let r = clamp_u8(pixel[0] as f64 + adjustment);
        let g = clamp_u8(pixel[1] as f64 + adjustment);
        let b = clamp_u8(pixel[2] as f64 + adjustment);
        out.put_pixel(x, y, Rgba([r, g, b, pixel[3]]));
    }
    DynamicImage::ImageRgba8(out)
}

fn adjust_shadows(img: DynamicImage, value: f64) -> DynamicImage {
    // Affects dark areas only. value: -100 to +100
    let amount = value / 100.0;
    let rgba = img.to_rgba8();
    let (w, h) = rgba.dimensions();
    let mut out = ImageBuffer::new(w, h);
    for (x, y, pixel) in rgba.enumerate_pixels() {
        let luminance = 0.299 * pixel[0] as f64 + 0.587 * pixel[1] as f64 + 0.114 * pixel[2] as f64;
        let mask = (1.0 - luminance / 255.0).powf(2.0); // Shadow mask
        let adjustment = amount * mask * 60.0;
        let r = clamp_u8(pixel[0] as f64 + adjustment);
        let g = clamp_u8(pixel[1] as f64 + adjustment);
        let b = clamp_u8(pixel[2] as f64 + adjustment);
        out.put_pixel(x, y, Rgba([r, g, b, pixel[3]]));
    }
    DynamicImage::ImageRgba8(out)
}

fn adjust_whites(img: DynamicImage, value: f64) -> DynamicImage {
    // Adjusts the white point. value: -100 to +100
    let amount = value / 100.0;
    let rgba = img.to_rgba8();
    let (w, h) = rgba.dimensions();
    let mut out = ImageBuffer::new(w, h);
    for (x, y, pixel) in rgba.enumerate_pixels() {
        let luminance = 0.299 * pixel[0] as f64 + 0.587 * pixel[1] as f64 + 0.114 * pixel[2] as f64;
        let mask = (luminance / 255.0).powf(4.0);
        let adjustment = amount * mask * 80.0;
        let r = clamp_u8(pixel[0] as f64 + adjustment);
        let g = clamp_u8(pixel[1] as f64 + adjustment);
        let b = clamp_u8(pixel[2] as f64 + adjustment);
        out.put_pixel(x, y, Rgba([r, g, b, pixel[3]]));
    }
    DynamicImage::ImageRgba8(out)
}

fn adjust_blacks(img: DynamicImage, value: f64) -> DynamicImage {
    // Adjusts the black point. value: -100 to +100
    let amount = value / 100.0;
    let rgba = img.to_rgba8();
    let (w, h) = rgba.dimensions();
    let mut out = ImageBuffer::new(w, h);
    for (x, y, pixel) in rgba.enumerate_pixels() {
        let luminance = 0.299 * pixel[0] as f64 + 0.587 * pixel[1] as f64 + 0.114 * pixel[2] as f64;
        let mask = (1.0 - luminance / 255.0).powf(4.0);
        let adjustment = amount * mask * 80.0;
        let r = clamp_u8(pixel[0] as f64 + adjustment);
        let g = clamp_u8(pixel[1] as f64 + adjustment);
        let b = clamp_u8(pixel[2] as f64 + adjustment);
        out.put_pixel(x, y, Rgba([r, g, b, pixel[3]]));
    }
    DynamicImage::ImageRgba8(out)
}

fn adjust_temperature(img: DynamicImage, value: f64) -> DynamicImage {
    // value: -100 (cool/blue) to +100 (warm/orange)
    let amount = value / 100.0;
    let rgba = img.to_rgba8();
    let (w, h) = rgba.dimensions();
    let mut out = ImageBuffer::new(w, h);
    for (x, y, pixel) in rgba.enumerate_pixels() {
        let r = clamp_u8(pixel[0] as f64 + amount * 30.0);
        let g = clamp_u8(pixel[1] as f64 + amount * 10.0);
        let b = clamp_u8(pixel[2] as f64 - amount * 30.0);
        out.put_pixel(x, y, Rgba([r, g, b, pixel[3]]));
    }
    DynamicImage::ImageRgba8(out)
}

fn adjust_tint(img: DynamicImage, value: f64) -> DynamicImage {
    // value: -100 (green) to +100 (magenta)
    let amount = value / 100.0;
    let rgba = img.to_rgba8();
    let (w, h) = rgba.dimensions();
    let mut out = ImageBuffer::new(w, h);
    for (x, y, pixel) in rgba.enumerate_pixels() {
        let r = clamp_u8(pixel[0] as f64 + amount * 15.0);
        let g = clamp_u8(pixel[1] as f64 - amount * 25.0);
        let b = clamp_u8(pixel[2] as f64 + amount * 15.0);
        out.put_pixel(x, y, Rgba([r, g, b, pixel[3]]));
    }
    DynamicImage::ImageRgba8(out)
}

fn adjust_vibrance(img: DynamicImage, value: f64) -> DynamicImage {
    // Selectively saturates less-saturated colors
    let amount = value / 100.0;
    let rgba = img.to_rgba8();
    let (w, h) = rgba.dimensions();
    let mut out = ImageBuffer::new(w, h);
    for (x, y, pixel) in rgba.enumerate_pixels() {
        let r = pixel[0] as f64 / 255.0;
        let g = pixel[1] as f64 / 255.0;
        let b = pixel[2] as f64 / 255.0;
        let max_c = r.max(g).max(b);
        let min_c = r.min(g).min(b);
        let sat = if max_c > 0.0 { (max_c - min_c) / max_c } else { 0.0 };
        // Less saturated pixels get more boost
        let factor = 1.0 + amount * (1.0 - sat);
        let gray = 0.299 * r + 0.587 * g + 0.114 * b;
        let nr = clamp_u8((gray + (r - gray) * factor) * 255.0);
        let ng = clamp_u8((gray + (g - gray) * factor) * 255.0);
        let nb = clamp_u8((gray + (b - gray) * factor) * 255.0);
        out.put_pixel(x, y, Rgba([nr, ng, nb, pixel[3]]));
    }
    DynamicImage::ImageRgba8(out)
}

fn adjust_saturation(img: DynamicImage, value: f64) -> DynamicImage {
    let factor = 1.0 + value / 100.0;
    let rgba = img.to_rgba8();
    let (w, h) = rgba.dimensions();
    let mut out = ImageBuffer::new(w, h);
    for (x, y, pixel) in rgba.enumerate_pixels() {
        let r = pixel[0] as f64 / 255.0;
        let g = pixel[1] as f64 / 255.0;
        let b = pixel[2] as f64 / 255.0;
        let gray = 0.299 * r + 0.587 * g + 0.114 * b;
        let nr = clamp_u8((gray + (r - gray) * factor) * 255.0);
        let ng = clamp_u8((gray + (g - gray) * factor) * 255.0);
        let nb = clamp_u8((gray + (b - gray) * factor) * 255.0);
        out.put_pixel(x, y, Rgba([nr, ng, nb, pixel[3]]));
    }
    DynamicImage::ImageRgba8(out)
}

fn adjust_clarity(img: DynamicImage, value: f64) -> DynamicImage {
    if value.abs() < 0.1 {
        return img;
    }
    // Clarity = midtone contrast via unsharp mask on luminosity
    let amount = value / 100.0;
    let blurred = img.blur(10.0);
    let rgba = img.to_rgba8();
    let blurred_rgba = blurred.to_rgba8();
    let (w, h) = rgba.dimensions();
    let mut out = ImageBuffer::new(w, h);
    for (x, y, pixel) in rgba.enumerate_pixels() {
        let bp = blurred_rgba.get_pixel(x, y);
        let r = clamp_u8(pixel[0] as f64 + (pixel[0] as f64 - bp[0] as f64) * amount);
        let g = clamp_u8(pixel[1] as f64 + (pixel[1] as f64 - bp[1] as f64) * amount);
        let b = clamp_u8(pixel[2] as f64 + (pixel[2] as f64 - bp[2] as f64) * amount);
        out.put_pixel(x, y, Rgba([r, g, b, pixel[3]]));
    }
    DynamicImage::ImageRgba8(out)
}

fn adjust_sharpness(img: DynamicImage, value: f64) -> DynamicImage {
    if value.abs() < 0.1 {
        return img;
    }
    let amount = value / 100.0;
    let blurred = img.blur(1.5);
    let rgba = img.to_rgba8();
    let blurred_rgba = blurred.to_rgba8();
    let (w, h) = rgba.dimensions();
    let mut out = ImageBuffer::new(w, h);
    for (x, y, pixel) in rgba.enumerate_pixels() {
        let bp = blurred_rgba.get_pixel(x, y);
        let r = clamp_u8(pixel[0] as f64 + (pixel[0] as f64 - bp[0] as f64) * amount);
        let g = clamp_u8(pixel[1] as f64 + (pixel[1] as f64 - bp[1] as f64) * amount);
        let b = clamp_u8(pixel[2] as f64 + (pixel[2] as f64 - bp[2] as f64) * amount);
        out.put_pixel(x, y, Rgba([r, g, b, pixel[3]]));
    }
    DynamicImage::ImageRgba8(out)
}

fn apply_vignette(img: DynamicImage, value: f64) -> DynamicImage {
    if value.abs() < 0.1 {
        return img;
    }
    let amount = value / 100.0;
    let rgba = img.to_rgba8();
    let (w, h) = rgba.dimensions();
    let cx = w as f64 / 2.0;
    let cy = h as f64 / 2.0;
    let max_dist = (cx * cx + cy * cy).sqrt();
    let mut out = ImageBuffer::new(w, h);
    for (x, y, pixel) in rgba.enumerate_pixels() {
        let dx = x as f64 - cx;
        let dy = y as f64 - cy;
        let dist = (dx * dx + dy * dy).sqrt() / max_dist;
        let vignette_factor = 1.0 - amount * dist * dist;
        let vf = vignette_factor.max(0.0);
        let r = clamp_u8(pixel[0] as f64 * vf);
        let g = clamp_u8(pixel[1] as f64 * vf);
        let b = clamp_u8(pixel[2] as f64 * vf);
        out.put_pixel(x, y, Rgba([r, g, b, pixel[3]]));
    }
    DynamicImage::ImageRgba8(out)
}

fn rotate_image(img: DynamicImage, degrees: f64) -> DynamicImage {
    match degrees as i32 % 360 {
        90 | -270 => img.rotate90(),
        180 | -180 => img.rotate180(),
        270 | -90 => img.rotate270(),
        _ => img,
    }
}

/// Crop an image
#[tauri::command]
pub fn crop_image(
    path: String,
    x: u32,
    y: u32,
    width: u32,
    height: u32,
) -> Result<String, String> {
    let mut img = image::open(&path).map_err(|e| format!("Failed to open: {}", e))?;
    let cropped = img.crop(x, y, width, height);

    let mut buf = Vec::new();
    let mut cursor = std::io::Cursor::new(&mut buf);
    cropped
        .write_to(&mut cursor, image::ImageFormat::Jpeg)
        .map_err(|e| format!("Failed to encode: {}", e))?;
    Ok(STANDARD.encode(&buf))
}

/// Get image histogram data
#[tauri::command]
pub fn get_histogram(path: String) -> Result<HistogramData, String> {
    let img = image::open(&path).map_err(|e| format!("Failed to open: {}", e))?;
    let rgba = img.to_rgba8();

    let mut r_hist = [0u32; 256];
    let mut g_hist = [0u32; 256];
    let mut b_hist = [0u32; 256];
    let mut l_hist = [0u32; 256];

    for pixel in rgba.pixels() {
        r_hist[pixel[0] as usize] += 1;
        g_hist[pixel[1] as usize] += 1;
        b_hist[pixel[2] as usize] += 1;
        let lum = (0.299 * pixel[0] as f64 + 0.587 * pixel[1] as f64 + 0.114 * pixel[2] as f64) as usize;
        l_hist[lum.min(255)] += 1;
    }

    Ok(HistogramData {
        red: r_hist.to_vec(),
        green: g_hist.to_vec(),
        blue: b_hist.to_vec(),
        luminance: l_hist.to_vec(),
    })
}

#[derive(serde::Serialize)]
pub struct HistogramData {
    pub red: Vec<u32>,
    pub green: Vec<u32>,
    pub blue: Vec<u32>,
    pub luminance: Vec<u32>,
}

/// Extract dominant colors from an image
#[tauri::command]
pub fn get_color_palette(path: String, count: Option<u32>) -> Result<Vec<String>, String> {
    let img = image::open(&path).map_err(|e| format!("Failed to open: {}", e))?;
    let small = img.resize(50, 50, image::imageops::FilterType::Nearest);
    let rgba = small.to_rgba8();

    let count = count.unwrap_or(6) as usize;

    // Simple k-means-like color extraction
    let mut colors: Vec<[f64; 3]> = rgba
        .pixels()
        .map(|p| [p[0] as f64, p[1] as f64, p[2] as f64])
        .collect();

    // Sort by hue-brightness and pick evenly spaced
    colors.sort_by(|a, b| {
        let ha = hue(a);
        let hb = hue(b);
        ha.partial_cmp(&hb).unwrap_or(std::cmp::Ordering::Equal)
    });

    let step = colors.len() / count.max(1);
    let palette: Vec<String> = (0..count)
        .map(|i| {
            let idx = (i * step).min(colors.len().saturating_sub(1));
            let c = &colors[idx];
            format!("#{:02x}{:02x}{:02x}", c[0] as u8, c[1] as u8, c[2] as u8)
        })
        .collect();

    Ok(palette)
}

fn hue(c: &[f64; 3]) -> f64 {
    let r = c[0] / 255.0;
    let g = c[1] / 255.0;
    let b = c[2] / 255.0;
    let max = r.max(g).max(b);
    let min = r.min(g).min(b);
    if (max - min).abs() < 1e-6 {
        return 0.0;
    }
    let h = if max == r {
        60.0 * ((g - b) / (max - min)) % 360.0
    } else if max == g {
        60.0 * ((b - r) / (max - min)) + 120.0
    } else {
        60.0 * ((r - g) / (max - min)) + 240.0
    };
    if h < 0.0 { h + 360.0 } else { h }
}
