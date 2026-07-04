use std::fs::File;
use std::io::{Read, Seek, SeekFrom};
use std::path::Path;

/// Extract the largest embedded JPEG from a RAW file by searching for SOI and EOI markers in chunks
pub fn extract_embedded_jpeg(path: &Path) -> Option<Vec<u8>> {
    let mut file = File::open(path).ok()?;
    let mut search_file = File::open(path).ok()?;
    let file_len = file.metadata().ok()?.len();
    if file_len < 4 {
        return None;
    }

    let mut best_start = None;
    let mut best_length = 0;

    let chunk_size = 64 * 1024; // 64KB
    let mut buffer = vec![0u8; chunk_size + 4];
    let mut offset = 0u64;

    while offset < file_len {
        let to_read = (chunk_size as u64).min(file_len - offset);
        if to_read < 3 {
            break;
        }

        if file.seek(SeekFrom::Start(offset)).is_err() {
            break;
        }

        if file.read_exact(&mut buffer[..to_read as usize]).is_err() {
            break;
        }

        let mut i = 0;
        while i < to_read as usize - 2 {
            if buffer[i] == 0xFF && buffer[i + 1] == 0xD8 && buffer[i + 2] == 0xFF {
                let start = offset + i as u64;
                
                // Scan for EOI (0xFF 0xD9)
                let max_search = (start + 25 * 1024 * 1024).min(file_len);
                let mut search_offset = start + 2;
                let mut search_buf = vec![0u8; 64 * 1024];

                while search_offset < max_search {
                    let search_to_read = (search_buf.len() as u64).min(max_search - search_offset);
                    if search_to_read < 2 {
                        break;
                    }

                    if search_file.seek(SeekFrom::Start(search_offset)).is_ok() {
                        if search_file.read_exact(&mut search_buf[..search_to_read as usize]).is_ok() {
                            let mut found_eoi = false;
                            for j in 0..(search_to_read as usize - 1) {
                                if search_buf[j] == 0xFF && search_buf[j + 1] == 0xD9 {
                                    let length = (search_offset + j as u64 + 2) - start;
                                    if length > best_length {
                                        best_start = Some(start);
                                        best_length = length;
                                    }
                                    found_eoi = true;
                                    break;
                                }
                            }
                            if found_eoi {
                                break;
                            }
                        }
                    }
                    search_offset += search_to_read - 1; // overlap by 1 byte
                }
            }
            i += 1;
        }

        offset += to_read - 2; // overlap by 2 bytes
    }

    if let Some(start) = best_start {
        if best_length > 1024 {
            let mut result = vec![0u8; best_length as usize];
            if file.seek(SeekFrom::Start(start)).is_ok() {
                if file.read_exact(&mut result).is_ok() {
                    return Some(result);
                }
            }
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
