# Handoff Report — explorer_stability

## 1. Observation
During a static code analysis and stability audit of WiPhoto v5.0 (frontend ES Modules JS & backend Tauri Rust), several critical stability risks, silent errors, race conditions, event contract mismatches, and data loss bugs were identified across the codebase:

### A. IPC Event Contract Mismatch & Broken Real-Time Scanning UI
- **Files**: `src-tauri/src/commands/scanner.rs` (Lines 405, 428) & `src/js/welcome.js` (Lines 88–90) & `src/js/api.js` (Line 72).
- **Code Snippets**:
  - `scanner.rs:405`: `let _ = app.emit("image-scanned-batch", chunk.to_vec());`
  - `scanner.rs:428`: `let _ = app_clone.emit("image-scanned-batch", batch);`
  - `api.js:72`: `onImageScanned: (callback) => listen('image-scanned', (event) => callback(event.payload))`
  - `welcome.js:88-90`:
    ```js
    unlistenScanned = await API.onImageScanned((info) => {
      scanBuffer.push(info);
    });
    ```
- **Observed Behavior**: The Rust backend emits `"image-scanned-batch"`, while `api.js` listens to `"image-scanned"`. Consequently, real-time progressive loading during folder scanning fails to trigger. Images are loaded into the gallery only after the entire scan promise resolves.

### B. Subfolder Record Wiping in Non-Recursive Folder Scans
- **File**: `src-tauri/src/commands/scanner.rs` (Lines 364, 489–499) & `src-tauri/src/db.rs` (Lines 278–304).
- **Code Snippet**:
  - `scanner.rs:364`: `let db_mtimes = crate::db::get_folder_mtimes(&path).unwrap_or_default();`
  - `scanner.rs:489-499`:
    ```rust
    let mut to_delete = Vec::new();
    for cached_path in db_mtimes.keys() {
        if !file_paths_set.contains(cached_path) {
            to_delete.push(cached_path.clone());
        }
    }
    if !to_delete.is_empty() {
        if let Err(e) = crate::db::delete_images_batch(&to_delete) { ... }
    }
    ```
- **Observed Behavior**: `db::get_folder_mtimes(&path)` uses SQL `WHERE path LIKE 'path/%'`, which retrieves all indexed images in the root folder **and all nested subfolders**. When `recursive` is `false`, `collect_files` only gathers direct files in root. `file_paths_set` does not contain subfolder paths. `scan_folder` treats all subfolder image records as "orphaned" and permanently deletes them from SQLite!

### C. Duplicate Finder Failure on Missing Thumbnail Cache
- **File**: `src-tauri/src/commands/duplicates.rs` (Lines 13–30, 215–237).
- **Code Snippet**:
  - `duplicates.rs:22-29`:
    ```rust
    let cache_file = cache_dir.join(format!("{}.jpg", hash));
    if cache_file.exists() {
        if let Ok(img) = image::open(&cache_file) {
            return Some(img);
        }
    }
    None
    ```
- **Observed Behavior**: `get_image_for_hashing` ONLY checks for pre-existing thumbnail files in `.wiphoto/cache/thumbnails`. If `find_duplicates` is called before thumbnails have been generated or cached for a directory, `get_image_for_hashing` returns `None` for every file. `valid_hashes` is 0, and `find_duplicates` returns `[]` silently without computing hashes or building the BK-Tree.

### D. Data State Loss on Clearing Semantic Search
- **File**: `src/js/search.js` (Lines 46–63).
- **Code Snippet**:
  - `search.js:59`: `Gallery.setImages(matchedImgs);`
- **Observed Behavior**: When CLIP semantic search finishes, `Gallery.setImages(matchedImgs)` overwrites `Gallery`'s internal `allImages` array with only the search results. When the user subsequently clears the search input, `Gallery.applyFilters()` operates on the truncated `allImages` array. All other images in the user's folder vanish from the app state until a complete folder re-scan is performed.

### E. Index-Based Selection Corruption in Gallery UI
- **File**: `src/js/gallery.js` (Lines 7, 267–273, 371–393, 443).
- **Code Snippet**:
  - `gallery.js:7`: `let selectedIndices = new Set();`
  - `gallery.js:443`: `getSelectedImages() { return Array.from(selectedIndices).map(i => filteredImages[i]).filter(Boolean); }`
- **Observed Behavior**: `Gallery.js` tracks selection using numeric array indices (`selectedIndices`). Changing sort order (e.g. Name -> Date) or applying a filter (e.g. Rated, Faces, Tag) reorders/filters `filteredImages`, but `selectedIndices` is not cleared or updated. As a result, selection indices point to completely different images after sorting/filtering. Furthermore, `addImageBatch` during background scans calls `renderGrid()`, which executes `selectedIndices.clear()`, wiping out user selection mid-scan.

### F. Unhandled Panics & Error Suppression in Backend Rust
- **Files**: `src-tauri/src/lib.rs` (Lines 111, 119, 158), `src-tauri/src/file_ops.rs` (Lines 19–25, 87–90), `src-tauri/src/commands/scanner.rs` (Lines 303–318).
- **Observations**:
  - `lib.rs:111,119`: `tauri::http::Response::builder().unwrap()` can panic if response headers or status codes fail construction.
  - `lib.rs:158`: `if let Err(e) = db::init_db() { log::error!("Failed to initialize database: {}", e); }` allows the app to startup even if DB setup fails, leading to unhandled errors in all subsequent DB operations.
  - `file_ops.rs:19–25,87–90`: `.trash_metadata.json` is read and rewritten as raw JSON without mutex/file locking. Concurrent delete/restore operations cause race conditions and file corruption.
  - `scanner.rs:303–318`: EXIF GPS rational parsing with zero denominators produces `NaN` or `Infinity` coordinate tuples `(NaN, NaN)`, leading to invalid JSON outputs or map rendering errors.

---

## 2. Logic Chain

1. **IPC Event Mismatch**:
   - Backend emits `image-scanned-batch` (array of `ImageInfo`).
   - Frontend `API` wrapper subscribes to `image-scanned` (single `ImageInfo`).
   - Event callback is never executed during scanning.
   - `scanBuffer` remains empty until `scanFolder` promise completes.
   - Therefore, progressive rendering is completely broken during folder scanning.

2. **Non-Recursive Orphan Deletion**:
   - `get_folder_mtimes(folder)` executes `WHERE path LIKE 'folder/%'`.
   - SQLite returns cached paths for `folder/a.jpg` AND `folder/sub/b.jpg`.
   - In non-recursive mode, `collect_files` returns `[folder/a.jpg]`.
   - `file_paths_set` = `{"folder/a.jpg"}`.
   - `to_delete` collects `folder/sub/b.jpg` because it is in `db_mtimes` but missing from `file_paths_set`.
   - `delete_images_batch` removes `folder/sub/b.jpg` from DB.
   - Therefore, non-recursive scans wipe subfolder metadata records from database.

3. **Duplicate Search Cache Lock-In**:
   - `find_duplicates` calls `get_image_for_hashing(path)` for each file.
   - `get_image_for_hashing` opens `.wiphoto/cache/thumbnails/{hash}.jpg`.
   - If thumbnail file does not exist, returns `None`.
   - No fallback to open source image file or generate thumbnail on-demand.
   - All paths produce `None` hash.
   - `valid_hashes` = `[]`.
   - Returns 0 duplicate groups without any error or warning.

4. **Gallery Selection State Invalidation**:
   - Selection state stores `Set<number>` corresponding to `filteredImages` array indices.
   - Array element positions shift when `currentSort` or `currentFilter` changes.
   - Operations operating on `getSelectedImages()` (e.g. Delete, Rating, Tagging) perform actions on the wrong image objects after re-sorting.

5. **Search Mutation Data Loss**:
   - `runSemanticSearch` receives CLIP search results.
   - Filtered images array is passed to `Gallery.setImages(matchedImgs)`.
   - `Gallery.setImages` assigns `allImages = images`.
   - Original full dataset in `allImages` is permanently overwritten.
   - Clearing search query filters `allImages` (which now only contains previous search results).
   - Entire library becomes invisible until folder is re-opened.

---

## 3. Caveats

- **Network Restrictions**: Investigation was conducted in CODE_ONLY mode (local filesystem analysis only). No external web requests or ONNX model downloads were executed against remote servers.
- **OS-Specific Pathing**: File path normalization (`/` vs `\`) on Windows was inspected statically; runtime behavior under UNC paths or mapped network drives remains an unverified edge case.
- **Hardware GPU Acceleration**: Behavior of canvas drawing and Leaflet webgl map rendering was verified via static code inspection without a live display server.

---

## 4. Conclusion

WiPhoto v5.0 features a solid baseline architecture (Tauri v2 + Rayon + ES Modules), but currently suffers from critical stability and data integrity bugs:
1. **Broken Progressive Scan UX** due to IPC event string mismatch (`image-scanned-batch` vs `image-scanned`).
2. **Database Record Corruption** in non-recursive scans deleting subfolder entries.
3. **Silent Failure in Duplicate Finder** due to hard reliance on pre-existing thumbnail files.
4. **Data Truncation Bug in Search** overwriting `Gallery.allImages`.
5. **Selection State Pollution** in `Gallery.js` due to index-based tracking.

### Recommended Fixes:
1. **Fix IPC Event**: Update `API.onImageScanned` (or `welcome.js`) to listen for `image-scanned-batch` and handle arrays of `ImageInfo`.
2. **Fix Non-Recursive DB Cleanup**: In `scanner.rs`, only execute `to_delete` orphan cleanup when `recursive == true`, or restrict `db_mtimes` query to direct child paths.
3. **Fix Duplicate Hashing Fallback**: In `duplicates.rs`, if thumbnail file is missing, generate thumbnail on-the-fly or open image directly via `image::open`.
4. **Preserve Master Image List in Search**: In `search.js`, call `Gallery.setFilteredImages(...)` or apply search as a filter predicate rather than mutating `allImages`.
5. **Use Stable Unique IDs for Selection**: In `Gallery.js`, store `selectedPaths = new Set()` (file paths) instead of row indices.

---

## 5. Verification Method

### Automated & Manual Test Commands:
1. **Rust Backend Compilation & Tests**:
   ```powershell
   cd c:\Users\Widlily\Documents\projects\wiphoto\src-tauri
   cargo test
   cargo clippy -- -D warnings
   ```
2. **Frontend Test Suite Execution**:
   ```powershell
   cd c:\Users\Widlily\Documents\projects\wiphoto\src
   node --test js/utils.test.cjs
   ```
3. **Inspection Verification**:
   - Inspect `src-tauri/src/commands/scanner.rs:405` and `src/js/api.js:72` for matching event names.
   - Inspect `src-tauri/src/commands/duplicates.rs:22` for thumbnail fallback handling.
   - Inspect `src/js/search.js:59` to verify `allImages` immutability.
   - Inspect `src/js/gallery.js:7` to verify path-based selection.

### Invalidation Conditions:
- If `cargo test` fails due to changed command signatures.
- If progressive scanning fails to emit events when scanning large test folders.
