use crate::db;
use crate::models::image_info::ImageInfo;
use crate::onnx;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchResult {
    pub path: String,
    pub filename: String,
    pub thumbnail: String,
    pub score: f32,
    pub info: ImageInfo,
}

/// Perform offline CLIP semantic search for smart albums
#[tauri::command]
pub fn search_clip_semantic(query: String, limit: usize) -> Result<Vec<SearchResult>, String> {
    let trimmed = query.trim();
    if trimmed.is_empty() {
        return Ok(Vec::new());
    }

    let query_vector = onnx::extract_text_embedding(trimmed);
    let limit_val = if limit == 0 { 100 } else { limit };
    let ranked_db_results = db::search_clip_semantic_db(&query_vector, limit_val)
        .map_err(|e| format!("Database search error: {}", e))?;

    let search_results = ranked_db_results
        .into_iter()
        .map(|(info, score)| SearchResult {
            path: info.path.clone(),
            filename: info.filename.clone(),
            thumbnail: info.thumbnail.clone(),
            score,
            info,
        })
        .collect();

    Ok(search_results)
}

/// Perform offline CLIP semantic search filtered by similarity threshold (PROJECT.md contract)
#[tauri::command]
pub fn search_clip(query: String, threshold: f32) -> Result<Vec<SearchResult>, String> {
    let trimmed = query.trim();
    if trimmed.is_empty() {
        return Ok(Vec::new());
    }

    let query_vector = onnx::extract_text_embedding(trimmed);
    let ranked_db_results = db::search_clip_semantic_db(&query_vector, 0)
        .map_err(|e| format!("Database search error: {}", e))?;

    let search_results = ranked_db_results
        .into_iter()
        .filter(|(_info, score)| *score >= threshold)
        .map(|(info, score)| SearchResult {
            path: info.path.clone(),
            filename: info.filename.clone(),
            thumbnail: info.thumbnail.clone(),
            score,
            info,
        })
        .collect();

    Ok(search_results)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_search_clip_semantic_empty_query() {
        // Arrange
        let query = "".to_string();

        // Act
        let res = search_clip_semantic(query, 10).unwrap();

        // Assert
        assert!(res.is_empty());
    }

    #[test]
    fn test_search_clip_empty_query() {
        // Arrange
        let query = "".to_string();

        // Act
        let res = search_clip(query, 0.5).unwrap();

        // Assert
        assert!(res.is_empty());
    }
}

