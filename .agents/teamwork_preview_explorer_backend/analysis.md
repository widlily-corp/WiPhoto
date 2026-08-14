# Rust Backend Survey Report & Feature Architecture Analysis (R1 & R4)

## Executive Summary
This survey presents a deep architectural audit of the WiPhoto Rust backend located in `src-tauri`. WiPhoto is built on **Tauri v2**, utilizing standard Rust crates (`tract-onnx 0.21`, `image 0.25`, `rusqlite 0.31`, `rayon 1`, `kamadak-exif 0.5`) and SQLite storage with connection pooling (`r2d2`).

The backend architecture is modular, high-performing, and well-structured, but requires target modifications to satisfy requirements **R1 (Local AI & Deduplication)** and **R4 (Advanced Formats & Batch Export)** for Release 5.0.

---

## 1. Existing Architecture & Tauri Setup Survey

### 1.1 Project & Crate Setup (`Cargo.toml`)
- **Package Name**: `wiphoto` (v5.0.10)
- **Library**: `wiphoto_lib` (staticlib, cdylib, rlib)
- **Tauri Framework**: Tauri v2 (`tauri 2.0`, `tauri-build 2.0`)
- **Tauri Plugins**:
  - `tauri-plugin-opener`
  - `tauri-plugin-dialog`
  - `tauri-plugin-fs`
  - `tauri-plugin-shell`
  - `tauri-plugin-updater`
  - `tauri-plugin-process`
- **Key Backend Dependencies**:
  - `tract-onnx = "0.21.3"` (ONNX runtime engine)
  - `image = { version = "0.25", features = ["jpeg", "png", "gif", "bmp", "tiff", "webp", "ico"] }`
  - `imageproc = "0.25"`, `ab_glyph = "0.2"` (Watermarking & graphic processing)
  - `rusqlite = "0.31"`, `r2d2 = "0.8.10"`, `r2d2_sqlite = "0.24.0"` (Database persistence & pooling)
  - `rayon = "1"` (Multi-threaded parallel processing)
  - `kamadak-exif = "0.5"` (EXIF metadata parsing)
  - `dirs = "6"`, `sha2 = "0.10"`, `hex = "0.4"`, `parking_lot = "0.12"`, `once_cell = "1"`

### 1.2 Custom URI Scheme & Asset Streaming Protocol (`src/lib.rs:70-229`)
- Custom protocols registered: `asset://localhost/...` and `tauri://localhost/...` mapped to `handle_asset_custom_protocol`.
- Features:
  - Percent decoding for paths with spaces/special characters (`decode_percent`).
  - HTTP Range header support (`206 Partial Content`) for video streaming and fast preview seeking.
  - ETag calculation and `304 Not Modified` caching headers (`Cache-Control: max-age=31536000, immutable`).
  - MIME type resolution covering standard formats, RAW extensions (`arw`, `cr2`, `nef`, `dng`, etc.), and `avif`.

### 1.3 Database Architecture (`src/db.rs`)
- SQLite database located at `~/.wiphoto/library.db` (or unique temp files during `cargo test`).
- Pool size 10 (`r2d2`), WAL journal mode (`PRAGMA journal_mode=WAL`), `synchronous = NORMAL`, busy timeout `5000ms`.
- `images` table schema includes image properties, PHash, EXIF metadata, rating, flag status, ML detection counts (`faces_count`, `animals_count`, `tags`), and vector `embedding` (TEXT column storing JSON array of 512 floats).
- Key helper functions: `save_images_batch`, `get_images_by_paths`, `save_image_embedding`, `get_image_embedding`, `search_clip_semantic_db`.

### 1.4 Existing Command Modules (`src/commands/`)
- `scanner.rs`: `scan_folder`, `count_files`, `log_js`
- `thumbnails.rs`: `get_thumbnail`, `load_full_image`, `clear_thumbnail_cache`, `get_image_url`
- `metadata.rs`: `read_exif`, `update_photo_metadata`, `get_geotagged_photos`
- `file_ops.rs`: File system operations, batch rename, trash management, folder tree.
- `duplicates.rs`: `find_duplicates`, `get_duplicate_stats`, `compute_phash`
- `editor.rs`: Image editing adjustments (crop, brightness, contrast, histogram).
- `export.rs`: `export_files`
- `settings.rs`: Application configuration, version and system info.
- `xmp.rs`: Sidecar read/write/sync (`.xmp`).
- `search.rs`: `search_clip_semantic`, `search_clip`.

---

## 2. Audit of Requirement R1: Local AI & Deduplication

### 2.1 Existing Implementation (`src/onnx.rs` & `src/commands/duplicates.rs`)
- **Tract ONNX Integration**:
  - `src/onnx.rs` initializes a global static model (`MODEL: OnceCell<ModelType>`) using `tract_onnx::onnx().model_for_path(...)`.
  - Input tensor shape is `[1, 3, 640, 640]`.
  - Output tensor processing converts YOLOv8 output `[1, 84, 8400]` into object detections (class 0 = person, classes 14-23 = animals, remaining = objects) with Non-Maximum Suppression (`nms`, `iou`).
- **Embedding Generation & Vector Math**:
  - `cosine_similarity(v1, v2)` and `normalize_vector(v)` in `src/onnx.rs:365-393`.
  - `extract_text_embedding(text)` and `extract_image_embedding(path)` generate 512-dimensional normalized vectors.
- **Deduplication Engine**:
  - `src/commands/duplicates.rs` implements perceptual hashing (`phash`, `dhash`, `ahash`, `combined`) and clusters images into duplicate groups using a BK-Tree (`BKNode`, `bktree_query`) based on Hamming distance.

### 2.2 Identified Gaps & Missing Capabilities for R1
1. **Missing Tauri Commands for Face Indexing & AI Deduplication**:
   - R1 requires explicit Tauri commands to index faces and find similar/duplicate images based on local AI embeddings.
   - Currently, face indexing and face vector embedding extraction functions are missing from Tauri command exposure. Commands like `index_faces`, `find_similar_images` / `find_face_duplicates` need to be exposed in `src/commands/duplicates.rs` and registered in `src/lib.rs`.
2. **Offline Test Reliability / Dummy Model Requirement**:
   - `init_model()` currently attempts to download `yolov8n.onnx` from GitHub Releases (`ureq::get(...)`) if the file is missing from `~/.wiphoto/models/yolov8n.onnx`.
   - **Acceptance Criterion R1**: *"A Rust integration test must successfully load a dummy ONNX model (or mock) and generate an embedding/hash without panicking."*
   - Currently, unit/integration tests would panic or fail if executed offline without internet access. A fallback or mock mechanism to load a tiny in-memory dummy ONNX model or mock graph during testing is missing.

---

## 3. Audit of Requirement R4: Advanced Formats & Batch Export

### 3.1 Existing Implementation (`Cargo.toml` & `src/commands/export.rs`)
- **Format Decoding**:
  - `Cargo.toml` specifies: `image = { version = "0.25", features = ["jpeg", "png", "gif", "bmp", "tiff", "webp", "ico"] }`.
  - `src/models/image_info.rs:4-7` defines `IMAGE_EXTENSIONS`, which contains `"avif"`, but **not** `"jxl"`.
- **Batch Export**:
  - `src/commands/export.rs:73-177` defines `export_files` command taking `paths`, `dest_dir`, `format`, `quality`, `max_width`, `max_height`, `watermark_text`.
  - Format conversions supported: JPEG, PNG, WebP, Original.
  - Multi-threaded using `rayon::prelude::*`.

### 3.2 Identified Gaps & Missing Capabilities for R4
1. **AVIF Decoding Support**:
   - `Cargo.toml` line 27 does **not** enable the `avif` feature for the `image` crate. Adding `"avif"` / `"avif-native"` to `image` crate features is required so `image::open` and `image::load_from_memory` can decode `.avif` files.
2. **JPEG XL (`.jxl`) Decoding Support**:
   - No JPEG XL decoder crate is currently present in `Cargo.toml`.
   - `jxl-oxide = "0.9"` (pure-Rust JPEG XL decoder) needs to be added as a dependency in `Cargo.toml`.
   - Image loading helpers in `thumbnails.rs`, `raw_utils.rs`, and `export.rs` must be extended to decode `.jxl` files via `jxl-oxide` when encountered.
   - `"jxl"` must be added to `IMAGE_EXTENSIONS` in `src/models/image_info.rs` and mapped to `image/jxl` in `handle_asset_custom_protocol` (`src/lib.rs`).
3. **EXIF Stripping Option in Batch Export**:
   - `export_files` command in `src/commands/export.rs` lacks the `strip_exif: Option<bool>` parameter requested in R4.
   - When `strip_exif` is true, exported images must not retain EXIF metadata headers.
4. **Batch Export Pipeline Test**:
   - **Acceptance Criterion R4**: *"A Rust test (`cargo test`) must verify that an image can be processed through the batch export pipeline successfully."*
   - An explicit integration test exercising the batch export pipeline with format conversion, resizing, and EXIF stripping is required.

---

## 4. Test Suite Audit (`src-tauri/tests/` & Unit Tests)

### 4.1 Existing Tests & Clean Pass Verification
- `cargo test --manifest-path src-tauri/Cargo.toml` executes and passes 100% cleanly with **45 total tests passing and 0 failures**:
  - **33 Unit Tests** in `wiphoto_lib`: BK-Tree queries, pHash computation, watermark calculation, EXIF geotags, CLIP empty search queries, XMP XML single/double quote parsing, image embedding normalization, percent decoding, custom protocol HTTP range/ETag caching, SQLite DB init/cache.
  - **4 Integration Tests** in `backend_stress_suite.rs`: Multi-threaded folder scan simulation, thumbnail cache lookup latency (< 10µs limit), BK-Tree 10,000 item query benchmark (< 2.0ms limit), DB concurrency stress (10 threads, 1,000 ops).
  - **5 Integration Tests** in `e2e_v500_tests.rs`: Version checks, cosine similarity, XMP sidecar parsing/writing, CLIP vector search, OTA updater config validation.
  - **3 Integration Tests** in `xmp_roundtrip_stress.rs`: XMP special characters/Unicode, malformed XML, 1,000 sequential roundtrip updates.

### 4.2 Required Test Additions for R1 & R4
1. **R1 Integration Test**:
   - Dedicated test in `tests/ai_onnx_r1_test.rs` or `e2e_v500_tests.rs` verifying that a dummy ONNX model or mock can be loaded without network calls and generate an embedding vector / hash without panicking.
2. **R4 Integration Test**:
   - Dedicated test in `tests/batch_export_r4_test.rs` or `e2e_v500_tests.rs` creating dummy images, calling `export_files` with resizing, format conversion (e.g. JPEG, PNG, AVIF), and EXIF stripping, asserting successful export counts and file integrity.

---

## 5. Key Rust Files to Modify / Add

| Target File | Action | Rationale |
|---|---|---|
| `src-tauri/Cargo.toml` | Modify | Add `jxl-oxide = "0.9"`, update `image` features to include `"avif-native"` or `"avif"`. |
| `src-tauri/src/models/image_info.rs` | Modify | Add `"jxl"` to `IMAGE_EXTENSIONS`. |
| `src-tauri/src/lib.rs` | Modify | Add `"jxl"` => `"image/jxl"` in `handle_asset_custom_protocol`; register new R1 Tauri commands in `invoke_handler!`. |
| `src-tauri/src/onnx.rs` | Modify | Support offline dummy model loading / mock embedding generation for test suite; implement face embedding / face indexing helpers. |
| `src-tauri/src/commands/duplicates.rs` | Modify | Implement and expose `index_faces`, `find_similar_images` / AI face deduplication Tauri commands. |
| `src-tauri/src/commands/export.rs` | Modify | Add `strip_exif: Option<bool>` parameter to `export_files`, implement EXIF metadata stripping, support AVIF/JXL export output. |
| `src-tauri/tests/ai_onnx_r1_test.rs` | Create/Modify | Rust integration test verifying dummy ONNX model loading and embedding/hash generation. |
| `src-tauri/tests/batch_export_r4_test.rs` | Create/Modify | Rust integration test verifying batch export pipeline (resizing, format conversion, EXIF stripping). |

---

## 6. Implementation Roadmap Recommendations

1. **Phase 1: Dependencies & Format Decoding (R4 Part 1)**
   - Update `Cargo.toml` with `avif-native` and `jxl-oxide`.
   - Update `image_info.rs` and `lib.rs` for JXL MIME & extension recognition.
   - Implement JXL decoding helper fallback in image loader functions.

2. **Phase 2: Batch Export Enhancement & Verification (R4 Part 2)**
   - Modify `export_files` in `commands/export.rs` to support `strip_exif` and expanded format conversions.
   - Write integration test verifying batch export pipeline.

3. **Phase 3: Local AI & Face Deduplication (R1)**
   - Enhance `onnx.rs` to support dummy model loading / offline testing.
   - Expose `index_faces` and `find_similar_images` Tauri commands in `commands/duplicates.rs` and register them in `lib.rs`.
   - Write integration test for dummy ONNX model loading & embedding generation.

4. **Phase 4: Verification & Regression Testing**
   - Run `cargo test --manifest-path src-tauri/Cargo.toml` to ensure 0 errors and all tests passing cleanly.
