use std::fs::File;
use std::io::Read;
use std::path::Path;

#[derive(Debug)]
struct JpegStreamInfo {
    start: usize,
    length: usize,
    width: u32,
    height: u32,
}

impl JpegStreamInfo {
    fn pixel_count(&self) -> u64 {
        self.width as u64 * self.height as u64
    }
}

/// Extract the largest embedded JPEG stream from a RAW file (ARW, CR2, NEF, DNG, etc.)
pub fn extract_embedded_jpeg(path: &Path) -> Option<Vec<u8>> {
    let mut file = File::open(path).ok()?;
    let mut data = Vec::new();
    file.read_to_end(&mut data).ok()?;

    if data.len() < 4 {
        return None;
    }

    let candidates = scan_all_jpeg_streams(&data);
    if candidates.is_empty() {
        return fallback_scan_raw(&data);
    }

    let best = candidates.iter().max_by(|a, b| {
        let pixels_cmp = a.pixel_count().cmp(&b.pixel_count());
        if pixels_cmp != std::cmp::Ordering::Equal {
            pixels_cmp
        } else {
            a.length.cmp(&b.length)
        }
    })?;

    Some(data[best.start..best.start + best.length].to_vec())
}

fn scan_all_jpeg_streams(data: &[u8]) -> Vec<JpegStreamInfo> {
    let mut streams = Vec::new();
    let mut idx = 0;

    while idx + 3 < data.len() {
        if data[idx] == 0xFF && data[idx + 1] == 0xD8 && data[idx + 2] == 0xFF {
            if let Some(info) = parse_jpeg_stream(data, idx) {
                if info.length >= 1024 {
                    idx += info.length;
                    streams.push(info);
                    continue;
                }
            }
        }
        idx += 1;
    }

    streams
}

fn parse_jpeg_stream(data: &[u8], start_idx: usize) -> Option<JpegStreamInfo> {
    let mut pos = start_idx + 2;
    let mut width = 0u32;
    let mut height = 0u32;

    while pos + 1 < data.len() {
        while pos < data.len() && data[pos] == 0xFF {
            pos += 1;
        }
        if pos >= data.len() {
            return None;
        }

        let marker = data[pos];
        pos += 1;

        match marker {
            0xD9 => {
                let length = pos - start_idx;
                return Some(JpegStreamInfo {
                    start: start_idx,
                    length,
                    width,
                    height,
                });
            }
            0xD8 | 0x00 | 0xD0..=0xD7 => continue,
            0xDA => {
                if pos + 2 > data.len() {
                    return None;
                }
                let sos_len = u16::from_be_bytes([data[pos], data[pos + 1]]) as usize;
                if sos_len < 2 || pos + sos_len > data.len() {
                    return None;
                }
                pos += sos_len;

                while pos + 1 < data.len() {
                    if data[pos] == 0xFF {
                        let next = data[pos + 1];
                        if next == 0xD9 {
                            pos += 2;
                            let length = pos - start_idx;
                            return Some(JpegStreamInfo {
                                start: start_idx,
                                length,
                                width,
                                height,
                            });
                        } else if next == 0x00 || (0xD0..=0xD7).contains(&next) {
                            pos += 2;
                        } else {
                            pos += 1;
                        }
                    } else {
                        pos += 1;
                    }
                }
                return None;
            }
            _ => {
                if pos + 2 > data.len() {
                    return None;
                }
                let seg_len = u16::from_be_bytes([data[pos], data[pos + 1]]) as usize;
                if seg_len < 2 || pos + seg_len > data.len() {
                    return None;
                }

                if (0xC0..=0xC3).contains(&marker) && seg_len >= 7 {
                    let h = u16::from_be_bytes([data[pos + 3], data[pos + 4]]) as u32;
                    let w = u16::from_be_bytes([data[pos + 5], data[pos + 6]]) as u32;
                    height = h;
                    width = w;
                }

                pos += seg_len;
            }
        }
    }

    None
}

fn fallback_scan_raw(data: &[u8]) -> Option<Vec<u8>> {
    let mut best_start = None;
    let mut best_len = 0;

    for i in 0..data.len().saturating_sub(4) {
        if data[i] == 0xFF && data[i + 1] == 0xD8 && data[i + 2] == 0xFF {
            let mut j = i + 3;
            let mut last_eoi = None;
            while j + 1 < data.len() {
                if data[j] == 0xFF && data[j + 1] == 0xD9 {
                    last_eoi = Some(j + 2);
                }
                j += 1;
            }
            if let Some(end) = last_eoi {
                let len = end - i;
                if len > best_len {
                    best_start = Some(i);
                    best_len = len;
                }
            }
        }
    }

    if let Some(start) = best_start {
        if best_len >= 100 {
            return Some(data[start..start + best_len].to_vec());
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    #[test]
    fn test_extract_embedded_jpeg_success() {
        // Arrange
        let dir = std::env::temp_dir();
        let file_path = dir.join("mock_raw_photo.NEF");

        let mut mock_data = vec![0u8; 5000];
        // SOI marker at offset 1000
        mock_data[1000] = 0xFF;
        mock_data[1001] = 0xD8;
        mock_data[1002] = 0xFF;
        // EOI marker at offset 3000
        mock_data[3000] = 0xFF;
        mock_data[3001] = 0xD9;

        {
            let mut file = File::create(&file_path).unwrap();
            file.write_all(&mock_data).unwrap();
        }

        // Act
        let extracted = extract_embedded_jpeg(&file_path);

        // Cleanup
        let _ = std::fs::remove_file(&file_path);

        // Assert
        assert!(extracted.is_some());
        let jpeg = extracted.unwrap();
        assert_eq!(jpeg.len(), 2002); // 3000 + 2 - 1000 = 2002
        assert_eq!(jpeg[0], 0xFF);
        assert_eq!(jpeg[1], 0xD8);
        assert_eq!(jpeg[2], 0xFF);
        assert_eq!(jpeg[2000], 0xFF);
        assert_eq!(jpeg[2001], 0xD9);
    }
}
