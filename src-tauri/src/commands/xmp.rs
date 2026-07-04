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

/// Parse XMP content string into XmpData
pub fn parse_xmp_content(content: &str) -> Option<XmpData> {
    let mut data = XmpData {
        rating: 0,
        color_label: String::new(),
        flag_status: String::new(),
        tags: vec![],
        history: vec![],
    };

    // Simple XML parsing (no full XML parser dependency needed)
    // Parse Rating
    if let Some(val) = extract_attr(content, "xmp:Rating") {
        data.rating = val.parse().unwrap_or(0);
    }
    // Parse Label
    if let Some(val) = extract_attr(content, "xmp:Label") {
        data.color_label = val;
    }
    // Parse FlagStatus
    if let Some(val) = extract_attr(content, "xmp:FlagStatus") {
        data.flag_status = val;
    }
    // Parse tags from rdf:li elements inside dc:subject
    if let Some(subject_block) = extract_block(content, "dc:subject") {
        data.tags = extract_list_items(&subject_block);
    }
    // Parse history from rdf:li elements inside xmpMM:History
    if let Some(history_block) = extract_block(content, "xmpMM:History") {
        data.history = extract_list_items(&history_block);
    }

    Some(data)
}

fn extract_attr(content: &str, attr: &str) -> Option<String> {
    let search_double = format!("{}=\"", attr);
    if let Some(start) = content.find(&search_double) {
        let value_start = start + search_double.len();
        if let Some(end) = content[value_start..].find('"') {
            return Some(content[value_start..value_start + end].to_string());
        }
    }
    let search_single = format!("{}='", attr);
    if let Some(start) = content.find(&search_single) {
        let value_start = start + search_single.len();
        if let Some(end) = content[value_start..].find('\'') {
            return Some(content[value_start..value_start + end].to_string());
        }
    }
    None
}

fn extract_block(content: &str, tag: &str) -> Option<String> {
    let open_tag = format!("<{}", tag);
    let close_tag = format!("</{}>", tag);
    if let Some(start) = content.find(&open_tag) {
        if let Some(end) = content[start..].find(&close_tag) {
            return Some(content[start..start + end + close_tag.len()].to_string());
        }
    }
    None
}

fn extract_list_items(block: &str) -> Vec<String> {
    let mut items = Vec::new();
    let mut search_from = 0;
    let open = "<rdf:li>";
    let close = "</rdf:li>";
    while let Some(start) = block[search_from..].find(open) {
        let abs_start = search_from + start + open.len();
        if let Some(end) = block[abs_start..].find(close) {
            let item = block[abs_start..abs_start + end].trim().to_string();
            if !item.is_empty() {
                items.push(xml_unescape(&item));
            }
            search_from = abs_start + end + close.len();
        } else {
            break;
        }
    }
    items
}

fn xml_escape(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
}

fn xml_unescape(s: &str) -> String {
    s.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", "\"")
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
