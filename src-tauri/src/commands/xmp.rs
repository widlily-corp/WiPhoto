use crate::models::image_info::{XmpData, XmpMetadata};
use std::fs;
use std::path::Path;

/// Read XMP sidecar for an image
#[tauri::command]
pub fn read_xmp_sidecar(path: String) -> Result<Option<XmpData>, String> {
    let xmp_path = Path::new(&path).with_extension("xmp");
    if !xmp_path.exists() {
        return Ok(None);
    }
    let content = fs::read_to_string(&xmp_path).map_err(|e| format!("Read error: {}", e))?;
    Ok(parse_xmp_content(&content))
}

/// Sync XMP sidecar for an image (PROJECT.md contract)
#[tauri::command]
pub fn sync_xmp_sidecar(image_path: String, metadata: XmpMetadata) -> Result<(), String> {
    let history_entry = metadata.history.last().cloned();
    write_xmp_sidecar(
        image_path,
        metadata.rating,
        metadata.color_label,
        metadata.flag_status,
        metadata.tags,
        history_entry,
    )
}


/// Write XMP sidecar for an image
#[tauri::command]
pub fn write_xmp_sidecar(
    path: String,
    rating: u8,
    color_label: String,
    flag_status: String,
    tags: Vec<String>,
    history_entry: Option<String>,
) -> Result<(), String> {
    let xmp_path = Path::new(&path).with_extension("xmp");

    // Read existing history
    let mut history = Vec::new();
    if xmp_path.exists() {
        if let Ok(content) = fs::read_to_string(&xmp_path) {
            if let Some(existing) = parse_xmp_content(&content) {
                history = existing.history;
            }
        }
    }

    // Append new history entry
    if let Some(entry) = history_entry {
        history.push(entry);
    }

    let tags_xml = if tags.is_empty() {
        String::new()
    } else {
        let items: String = tags
            .iter()
            .map(|t| format!("          <rdf:li>{}</rdf:li>\n", xml_escape(t)))
            .collect();
        format!(
            "      <dc:subject>\n        <rdf:Bag>\n{}\n        </rdf:Bag>\n      </dc:subject>\n",
            items
        )
    };

    let history_xml = if history.is_empty() {
        String::new()
    } else {
        let items: String = history
            .iter()
            .map(|h| format!("          <rdf:li>{}</rdf:li>\n", xml_escape(h)))
            .collect();
        format!(
            "      <xmpMM:History>\n        <rdf:Seq>\n{}\n        </rdf:Seq>\n      </xmpMM:History>\n",
            items
        )
    };

    let xmp_content = format!(
        r#"<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description
      xmlns:xmp="http://ns.adobe.com/xap/1.0/"
      xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/"
      xmlns:dc="http://purl.org/dc/elements/1.1/"
      xmp:Rating="{rating}"
      xmp:Label="{color_label}"
      xmp:FlagStatus="{flag_status}">
{tags_xml}{history_xml}    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>"#,
        rating = rating,
        color_label = xml_escape(&color_label),
        flag_status = xml_escape(&flag_status),
        tags_xml = tags_xml,
        history_xml = history_xml,
    );

    fs::write(&xmp_path, xmp_content).map_err(|e| format!("Write error: {}", e))
}

/// Parse XMP content string into XmpData using roxmltree
pub fn parse_xmp_content(content: &str) -> Option<XmpData> {
    let doc = roxmltree::Document::parse(content).ok()?;

    let mut data = XmpData {
        rating: 0,
        color_label: String::new(),
        flag_status: String::new(),
        tags: vec![],
        history: vec![],
    };

    if let Some(desc_node) = doc.descendants().find(|n| n.has_tag_name("Description")) {
        for attr in desc_node.attributes() {
            match attr.name() {
                "Rating" => {
                    data.rating = attr.value().parse().unwrap_or(0);
                }
                "Label" => {
                    data.color_label = attr.value().to_string();
                }
                "FlagStatus" => {
                    data.flag_status = attr.value().to_string();
                }
                _ => {}
            }
        }

        if data.rating == 0 {
            if let Some(r_node) = desc_node.descendants().find(|n| n.has_tag_name("Rating")) {
                if let Some(txt) = r_node.text() {
                    data.rating = txt.trim().parse().unwrap_or(0);
                }
            }
        }
        if data.color_label.is_empty() {
            if let Some(l_node) = desc_node.descendants().find(|n| n.has_tag_name("Label")) {
                if let Some(txt) = l_node.text() {
                    data.color_label = txt.trim().to_string();
                }
            }
        }
        if data.flag_status.is_empty() {
            if let Some(f_node) = desc_node.descendants().find(|n| n.has_tag_name("FlagStatus")) {
                if let Some(txt) = f_node.text() {
                    data.flag_status = txt.trim().to_string();
                }
            }
        }

        if let Some(subject_node) = desc_node.descendants().find(|n| n.has_tag_name("subject")) {
            for li in subject_node.descendants().filter(|n| n.has_tag_name("li")) {
                if let Some(text) = li.text() {
                    let t = text.trim();
                    if !t.is_empty() {
                        data.tags.push(t.to_string());
                    }
                }
            }
        }

        if let Some(history_node) = desc_node.descendants().find(|n| n.has_tag_name("History")) {
            for li in history_node.descendants().filter(|n| n.has_tag_name("li")) {
                if let Some(text) = li.text() {
                    let t = text.trim();
                    if !t.is_empty() {
                        data.history.push(t.to_string());
                    }
                }
            }
        }
    }

    Some(data)
}

fn xml_escape(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_xmp_content_double_quotes() {
        // Arrange
        let content = r#"<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description
      xmlns:xmp="http://ns.adobe.com/xap/1.0/"
      xmlns:dc="http://purl.org/dc/elements/1.1/"
      xmp:Rating="4"
      xmp:Label="blue"
      xmp:FlagStatus="picked">
      <dc:subject>
        <rdf:Bag>
          <rdf:li>Nature</rdf:li>
          <rdf:li>Landscape</rdf:li>
        </rdf:Bag>
      </dc:subject>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>"#;

        // Act
        let data = parse_xmp_content(content).expect("Failed to parse double-quoted XMP");

        // Assert
        assert_eq!(data.rating, 4);
        assert_eq!(data.color_label, "blue");
        assert_eq!(data.flag_status, "picked");
        assert_eq!(data.tags, vec!["Nature", "Landscape"]);
    }

    #[test]
    fn test_parse_xmp_content_single_quotes() {
        // Arrange
        let content = r#"<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x='adobe:ns:meta/'>
  <rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>
    <rdf:Description
      xmlns:xmp='http://ns.adobe.com/xap/1.0/'
      xmlns:dc='http://purl.org/dc/elements/1.1/'
      xmp:Rating='3'
      xmp:Label='red'
      xmp:FlagStatus='rejected'>
      <dc:subject>
        <rdf:Bag>
          <rdf:li>Vacation &amp; Travel</rdf:li>
        </rdf:Bag>
      </dc:subject>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>"#;

        // Act
        let data = parse_xmp_content(content).expect("Failed to parse single-quoted XMP");

        // Assert
        assert_eq!(data.rating, 3);
        assert_eq!(data.color_label, "red");
        assert_eq!(data.flag_status, "rejected");
        assert_eq!(data.tags, vec!["Vacation & Travel"]);
    }

    #[test]
    fn test_parse_xmp_content_element_style() {
        // Arrange
        let content = r#"<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/">
      <xmp:Rating>5</xmp:Rating>
      <xmp:Label>purple</xmp:Label>
      <xmp:FlagStatus>picked</xmp:FlagStatus>
      <dc:subject>
        <rdf:Bag>
          <rdf:li>Architecture</rdf:li>
        </rdf:Bag>
      </dc:subject>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>"#;

        // Act
        let data = parse_xmp_content(content).expect("Failed to parse element-style XMP");

        // Assert
        assert_eq!(data.rating, 5);
        assert_eq!(data.color_label, "purple");
        assert_eq!(data.flag_status, "picked");
        assert_eq!(data.tags, vec!["Architecture"]);
    }

    #[test]
    fn test_write_and_read_xmp_sidecar_creation_and_update() {
        // Arrange
        let temp_dir = std::env::temp_dir();
        let img_path = temp_dir.join("test_xmp_sync_sample.jpg").to_string_lossy().to_string();
        let sidecar_path = std::path::Path::new(&img_path).with_extension("xmp");

        // Clean up previous test runs if any
        let _ = fs::remove_file(&sidecar_path);

        // Act 1: Initial creation of XMP sidecar
        let create_res = write_xmp_sidecar(
            img_path.clone(),
            5,
            "green".to_string(),
            "picked".to_string(),
            vec!["Portrait".to_string(), "Studio".to_string()],
            Some("Initial edit session".to_string()),
        );

        // Assert 1
        assert!(create_res.is_ok());
        assert!(sidecar_path.exists());

        let read_1 = read_xmp_sidecar(img_path.clone()).expect("Read failed").expect("Should exist");
        assert_eq!(read_1.rating, 5);
        assert_eq!(read_1.color_label, "green");
        assert_eq!(read_1.flag_status, "picked");
        assert_eq!(read_1.tags, vec!["Portrait", "Studio"]);
        assert_eq!(read_1.history, vec!["Initial edit session"]);

        // Act 2: Update XMP sidecar with new values and append to history
        let update_res = write_xmp_sidecar(
            img_path.clone(),
            4,
            "yellow".to_string(),
            "picked".to_string(),
            vec!["Portrait".to_string(), "Outdoor".to_string()],
            Some("Applied exposure +0.5".to_string()),
        );

        // Assert 2
        assert!(update_res.is_ok());
        let read_2 = read_xmp_sidecar(img_path.clone()).expect("Read failed").expect("Should exist");
        assert_eq!(read_2.rating, 4);
        assert_eq!(read_2.color_label, "yellow");
        assert_eq!(read_2.flag_status, "picked");
        assert_eq!(read_2.tags, vec!["Portrait", "Outdoor"]);
        assert_eq!(
            read_2.history,
            vec!["Initial edit session", "Applied exposure +0.5"]
        );

        // Cleanup
        let _ = fs::remove_file(&sidecar_path);
    }

    #[test]
    fn test_sync_xmp_sidecar() {
        let temp_dir = std::env::temp_dir();
        let img_path = temp_dir.join("test_sync_xmp_contract.jpg").to_string_lossy().to_string();
        let sidecar_path = std::path::Path::new(&img_path).with_extension("xmp");

        let _ = fs::remove_file(&sidecar_path);

        let metadata = XmpMetadata {
            rating: 5,
            color_label: "blue".to_string(),
            flag_status: "picked".to_string(),
            tags: vec!["Nature".to_string()],
            history: vec!["Contract sync test".to_string()],
        };

        let res = sync_xmp_sidecar(img_path.clone(), metadata);
        assert!(res.is_ok());
        assert!(sidecar_path.exists());

        let read = read_xmp_sidecar(img_path.clone()).unwrap().unwrap();
        assert_eq!(read.rating, 5);
        assert_eq!(read.color_label, "blue");
        assert_eq!(read.flag_status, "picked");

        let _ = fs::remove_file(&sidecar_path);
    }
}


