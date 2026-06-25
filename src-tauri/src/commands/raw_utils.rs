use std::fs;
use std::path::Path;

/// Extract the largest embedded JPEG from a RAW file by searching for SOI and EOI markers
pub fn extract_embedded_jpeg(path: &Path) -> Option<Vec<u8>> {
    let bytes = fs::read(path).ok()?;
    if bytes.len() < 4 {
        return None;
    }

    let mut i = 0;
    let mut best_start = None;
    let mut best_length = 0;
    let file_len = bytes.len();

    while i < file_len.saturating_sub(3) {
        if bytes[i] == 0xFF && bytes[i + 1] == 0xD8 && bytes[i + 2] == 0xFF {
            let start = i;
            let mut j = start + 2;
            // Limit scanning to 25MB from the start marker to prevent runaway on huge files
            let max_search = (start + 25 * 1024 * 1024).min(file_len.saturating_sub(1));
            while j < max_search {
                if bytes[j] == 0xFF && bytes[j + 1] == 0xD9 {
                    let length = j + 2 - start;
                    if length > best_length {
                        best_start = Some(start);
                        best_length = length;
                    }
                    break;
                }
                j += 1;
            }
            i = j; // skip past EOI marker
        }
        i += 1;
    }

    if let Some(start) = best_start {
        if best_length > 1024 { // Sanity check size
            return Some(bytes[start..(start + best_length)].to_vec());
        }
    }
    None
}
