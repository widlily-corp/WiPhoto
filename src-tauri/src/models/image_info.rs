use serde::{Deserialize, Serialize};

/// Supported image extensions
pub const IMAGE_EXTENSIONS: &[&str] = &[
    "jpg", "jpeg", "jpe", "jfif", "png", "bmp", "gif", "tiff", "tif", "webp",
    "ico", "ppm", "pgm", "pbm", "pnm",
    "heic", "heif", "avif", "jp2", "j2k", "jpx", "jpm",
];

/// Supported RAW extensions
pub const RAW_EXTENSIONS: &[&str] = &[
    "arw", "cr2", "cr3", "nef", "nrw", "dng", "raw", "rw2", "orf", "pef",
    "raf", "srw", "x3f", "3fr", "ari", "bay", "cap", "iiq", "eip", "fff",
    "mef", "mos", "mrw", "rwl", "rwz", "sr2", "srf", "sti",
];

/// Supported video extensions
pub const VIDEO_EXTENSIONS: &[&str] = &[
    "mp4", "avi", "mkv", "mov", "wmv", "flv", "webm", "m4v",
    "mpg", "mpeg", "3gp", "ogv", "ts", "mts", "m2ts",
];

/// Main image data structure, mirrors Python's ImageInfo dataclass
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImageInfo {
    pub path: String,
    pub filename: String,
    pub thumbnail: String,      // base64-encoded thumbnail
    pub phash: Option<String>,
    pub sharpness: f64,
    pub is_best_in_group: bool,
    pub group_id: Option<String>,

    // Analysis data
    pub faces_count: u32,
    pub animals_count: u32,
    pub gps_location: Option<(f64, f64)>,
    pub aspect_ratio: f64,
    pub camera_model: String,
    pub date_taken: String,
    pub rating: u8,             // 0-5 stars
    pub file_size: u64,
    pub width: u32,
    pub height: u32,
    pub animal_species: Vec<String>,
    pub color_label: String,    // "", "red", "yellow", "green", "blue", "purple"
    pub flag_status: String,    // "", "picked", "rejected"
    pub tags: Vec<String>,
    pub is_video: bool,
    pub is_raw: bool,
}

impl ImageInfo {
    pub fn new(path: &str) -> Self {
        let filename = std::path::Path::new(path)
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .to_string();
        let ext = std::path::Path::new(path)
            .extension()
            .unwrap_or_default()
            .to_string_lossy()
            .to_lowercase();
        let is_video = VIDEO_EXTENSIONS.contains(&ext.as_str());
        let is_raw = RAW_EXTENSIONS.contains(&ext.as_str());

        Self {
            path: path.to_string(),
            filename,
            thumbnail: String::new(),
            phash: None,
            sharpness: 0.0,
            is_best_in_group: false,
            group_id: None,
            faces_count: 0,
            animals_count: 0,
            gps_location: None,
            aspect_ratio: 0.0,
            camera_model: String::new(),
            date_taken: String::new(),
            rating: 0,
            file_size: 0,
            width: 0,
            height: 0,
            animal_species: vec![],
            color_label: String::new(),
            flag_status: String::new(),
            tags: vec![],
            is_video,
            is_raw,
        }
    }
}

/// EXIF metadata key-value
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExifEntry {
    pub key: String,
    pub value: String,
}

/// Duplicate group
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DuplicateGroup {
    pub group_id: String,
    pub images: Vec<String>,   // paths
    pub best_path: String,
}

/// Editor edit operation
#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(dead_code)]
pub struct EditOperation {
    pub tool: String,
    pub value: f64,
}

/// Settings structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppSettings {
    pub worker_count: u32,
    pub raw_quality: String,       // "full" or "half"
    pub calculate_sharpness: bool,
    pub hamming_threshold: u32,
    pub thumbnail_cache_path: String,
}

impl Default for AppSettings {
    fn default() -> Self {
        let cpu_count = std::thread::available_parallelism()
            .map(|n| n.get() as u32)
            .unwrap_or(2);
        let cache_path = dirs::home_dir()
            .unwrap_or_default()
            .join(".wiphoto")
            .join("cache")
            .join("thumbnails")
            .to_string_lossy()
            .to_string();
        Self {
            worker_count: cpu_count.saturating_sub(1).max(1),
            raw_quality: "half".to_string(),
            calculate_sharpness: true,
            hamming_threshold: 5,
            thumbnail_cache_path: cache_path,
        }
    }
}

/// Scan result for progress tracking
#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(dead_code)]
pub struct ScanProgress {
    pub current: u32,
    pub total: u32,
    pub current_file: String,
}

/// XMP sidecar data
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct XmpData {
    pub rating: u8,
    pub color_label: String,
    pub flag_status: String,
    pub tags: Vec<String>,
    pub history: Vec<String>,
}

/// Check if a file extension is supported
pub fn is_supported_extension(ext: &str) -> bool {
    let ext_lower = ext.to_lowercase();
    IMAGE_EXTENSIONS.contains(&ext_lower.as_str())
        || RAW_EXTENSIONS.contains(&ext_lower.as_str())
        || VIDEO_EXTENSIONS.contains(&ext_lower.as_str())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_is_supported_extension() {
        // Arrange
        let jpg = "jpg";
        let nef = "NEF";
        let mp4 = "mp4";
        let txt = "txt";

        // Act
        let is_jpg_supported = is_supported_extension(jpg);
        let is_nef_supported = is_supported_extension(nef);
        let is_mp4_supported = is_supported_extension(mp4);
        let is_txt_supported = is_supported_extension(txt);

        // Assert
        assert!(is_jpg_supported);
        assert!(is_nef_supported);
        assert!(is_mp4_supported);
        assert!(!is_txt_supported);
    }

    #[test]
    fn test_image_info_new_constructor() {
        // Arrange
        let path = "C:/photos/test_image.NEF";

        // Act
        let info = ImageInfo::new(path);

        // Assert
        assert_eq!(info.path, "C:/photos/test_image.NEF");
        assert_eq!(info.filename, "test_image.NEF");
        assert!(info.is_raw);
        assert!(!info.is_video);
        assert_eq!(info.rating, 0);
    }

    #[test]
    fn test_app_settings_default() {
        // Arrange & Act
        let settings = AppSettings::default();

        // Assert
        assert!(settings.worker_count > 0);
        assert_eq!(settings.raw_quality, "half");
        assert!(settings.calculate_sharpness);
        assert_eq!(settings.hamming_threshold, 5);
        assert!(settings.thumbnail_cache_path.contains(".wiphoto"));
    }
}
