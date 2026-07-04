use crate::models::image_info::XmpData;
use std::fs;
use std::path::Path;

/// Read XMP sidecar for an image
#[tauri::command]
pub fn read_xmp_sidecar(path: String) -> Result<Option<XmpData>, String> {
    let xmp_path = Path::new(&path).with_extension("xmp");
    if !xmp_path.exists() {
        return Ok(None);
    }
    let content = fs::read_to_string(&xmp_path)
        .map_err(|e| format!("Read error: {}", e))?;
    Ok(parse_xmp_content(&content))
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
}
