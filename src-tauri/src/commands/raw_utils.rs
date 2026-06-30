use std::fs;
use std::path::Path;
use memchr::memchr;

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
        if let Some(pos) = memchr(0xFF, &bytes[i..file_len.saturating_sub(3)]) {
            i += pos;
            if bytes[i + 1] == 0xD8 && bytes[i + 2] == 0xFF {
                let start = i;
                let j = start + 2;
                // Limit scanning to 25MB from the start marker to prevent runaway on huge files
                let max_search = (start + 25 * 1024 * 1024).min(file_len.saturating_sub(1));
                
                let mut search_pos = j;
                while search_pos < max_search {
                    if let Some(offset) = memchr(0xFF, &bytes[search_pos..max_search]) {
                        let eoi_idx = search_pos + offset;
                        if eoi_idx + 1 < file_len && bytes[eoi_idx + 1] == 0xD9 {
                            let length = eoi_idx + 2 - start;
                            if length > best_length {
                                best_start = Some(start);
                                best_length = length;
                            }
                            search_pos = eoi_idx;
                            break;
                        }
                        search_pos = eoi_idx + 1;
                    } else {
                        break;
                    }
                }
                i = search_pos;
            }
            i += 1;
        } else {
            break;
        }
    }

    if let Some(start) = best_start {
        if best_length > 1024 { // Sanity check size
            return Some(bytes[start..(start + best_length)].to_vec());
        }
    }
    None
}
