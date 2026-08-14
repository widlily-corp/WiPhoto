# Comprehensive Integration & Test Suite Survey Report: WiPhoto

## Executive Summary
This survey report presents a deep architectural audit of the **WiPhoto** application (Tauri v2 + Rust backend + Vanilla JS frontend), examining the Inter-Process Communication (IPC) contracts, Event Bus model, custom asset streaming protocol, Node.js and Rust test infrastructure, and concrete integration touchpoints for upcoming release requirements **R1** (Local AI & Deduplication), **R2** (Pro Workflow UI), **R3** (WebGPU & Web Workers), and **R4** (Advanced Formats & Batch Export).

---

## 1. IPC Architecture & Communication Flow

### 1.1 Tauri Invoke Mechanism (`window.__TAURI__.core.invoke`)
The frontend communicates synchronously (Promise-based) with the Rust backend via Tauri v2's IPC bridge. Commands are registered in `src-tauri/src/lib.rs` inside `.invoke_handler(tauri::generate_handler![...])` and wrapped centrally in `src/js/api.js` (`window.API`).

#### Key Registered Commands (Current Inventory)
| Domain | Command Name | Rust Handler Location | Parameters & Return Type |
|---|---|---|---|
| **Scanner** | `scan_folder` | `src-tauri/src/commands/scanner.rs` | `path: String, recursive: bool` $\rightarrow$ `Result<Vec<ImageInfo>, String>` |
| | `count_files` | `src-tauri/src/commands/scanner.rs` | `path: String, recursive: bool` $\rightarrow$ `Result<u32, String>` |
| **Thumbnails** | `get_thumbnail` | `src-tauri/src/commands/thumbnails.rs` | `path: String` $\rightarrow$ `Result<String, String>` |
| | `load_full_image` | `src-tauri/src/commands/thumbnails.rs` | `path: String, maxSize: Option<u32>` $\rightarrow$ `Result<String, String>` |
| **Metadata** | `read_exif` | `src-tauri/src/commands/metadata.rs` | `path: String` $\rightarrow$ `Result<ExifData, String>` |
| | `update_photo_metadata` | `src-tauri/src/commands/metadata.rs` | `path: String, rating: Option<u8>, ...` $\rightarrow$ `Result<(), String>` |
| **File Ops** | `delete_files` | `src-tauri/src/commands/file_ops.rs` | `paths: Vec<String>` $\rightarrow$ `Result<Vec<String>, String>` |
| | `move_files` | `src-tauri/src/commands/file_ops.rs` | `paths: Vec<String>, destDir: String` $\rightarrow$ `Result<Vec<String>, String>` |
| **Duplicates** | `find_duplicates` | `src-tauri/src/commands/duplicates.rs` | `paths: Vec<String>, method: String, threshold: u32` $\rightarrow$ `Result<Vec<DuplicateGroup>, String>` |
| | `compute_phash` | `src-tauri/src/commands/duplicates.rs` | `path: String` $\rightarrow$ `Result<String, String>` |
| **Editor** | `apply_edit` | `src-tauri/src/commands/editor.rs` | `path: String, operations: EditOps` $\rightarrow$ `Result<String, String>` |
| | `get_histogram` | `src-tauri/src/commands/editor.rs` | `path: String` $\rightarrow$ `Result<HistogramData, String>` |
| **Export** | `export_files` | `src-tauri/src/commands/export.rs` | `paths: Vec<String>, destDir: String, format: String, ...` $\rightarrow$ `Result<u32, String>` |
| **Search** | `search_clip_semantic`| `src-tauri/src/commands/search.rs` | `query: String, limit: u32` $\rightarrow$ `Result<Vec<SearchResult>, String>` |

---

### 1.2 Event Bus Architecture (`window.__TAURI__.event.listen`)
For long-running asynchronous tasks (scanning large photo libraries, computing perceptual hashes across thousands of images), the Rust backend streams event payloads to the frontend via `app.emit("event-name", payload)`.

```
┌────────────────────────┐                   ┌────────────────────────┐
│  Rust Backend (Rayon)  │ ── app.emit() ──> │ Frontend (API.listen)  │
└────────────────────────┘                   └────────────────────────┘
  - scan-progress                              - Gallery.updateProgress
  - dup-progress                               - Settings.showDupStatus
  - scan-finished                              - Gallery.onScanComplete
  - image-scanned-batch                        - VirtualGrid.addBatch
```

#### Event Channels Matrix
- `scan-progress`: `{ scanned: u32, total: u32, current_file: String }`
- `dup-progress`: `{ current: u32, total: u32 }`
- `scan-finished`: `{ total_scanned: u32, total_added: u32, duration_ms: u64 }`
- `image-scanned-batch`: `Vec<ImageInfo>` (emitted in chunks of 50 images to avoid UI thread freeze)

---

### 1.3 Custom Asset Streaming Protocol (`asset://`)
To avoid base64 encoding overhead for high-resolution photo previews and RAW formats, WiPhoto registers custom URI protocols `asset://` and `tauri://` in `src-tauri/src/lib.rs` (`handle_asset_custom_protocol`).

#### Key Capabilities:
1. **Zero-Copy Streaming**: Reads image/video files directly into `Response<Cow<[u8]>>`.
2. **HTTP 206 Partial Content (Byte Ranges)**: Supports `Range: bytes=start-end` headers for fast video scrubbing and instant high-res JPEG preview extraction from RAW formats (ARW, CR2, NEF, DNG).
3. **HTTP 304 Caching**: Calculates `ETag: "{file_len}-{mtime_secs}"` and returns empty 304 response on `If-None-Match` match.
4. **MIME Mapping**: Automatic MIME type resolution for `.jpg`, `.png`, `.webp`, `.arw`, `.cr2`, `.nef`, `.dng`, `.mp4`, etc.

---

### 1.4 State Management Strategy
- **Frontend**: Lightweight modular Singleton pattern (`App`, `Gallery`, `Viewer`, `Editor`, `Settings`, `VirtualGrid`, `Utils`). State is maintained in-memory with UI rendering handled by `VirtualGrid` DOM card recycling.
- **Backend**: SQLite database (`src-tauri/src/db.rs`) managed via `r2d2` connection pooling (`r2d2_sqlite`), caching metadata, face vectors, and perceptual hashes. Persistent thumbnail cache stored under `~/.wiphoto/cache/thumbnails/`.

---

## 2. Test Infrastructure Analysis

### 2.1 Node.js Test Suite (`npm run test`)
- **Runner**: Node.js native test runner (`node:test`) configured in `package.json` as `"test": "node --test src/js/*.test.cjs"`.
- **Assertions**: `node:assert/strict`.
- **Execution Model**: `node:vm` context sandboxing for browser JS modules (`updater.js`, `utils.js`, `virtualgrid.js`), allowing full DOM event loop simulation without requiring Puppeteer/Selenium or heavy browser binaries.
- **Current Inventory**: **109 passing tests across 46 test suites** running in ~2.5 seconds.

#### Test Files & Tier Structure
- `src/js/updater_e2e.test.cjs` & `src/js/updater.test.cjs`: OTA Updater 4-Tier test suite (Requirements R1 & R2).
- `src/js/m1_challenger_stress.test.cjs` & `src/js/updater_m2_challenger_stress.test.cjs`: Adversarial stress tests (500-cycle open/close, state transition invariants).
- `src/js/tier1_tier2_features.test.cjs`: Happy-path feature coverage & edge cases.
- `src/js/tier3_cross_features.test.cjs`: Cross-feature interaction tests.
- `src/js/tier4_e2e_scenarios.test.cjs`: Real-world end-to-end workflow simulations.
- `src/js/utils.test.cjs`: Unit tests for helper utilities (`formatSize`, `getExtension`, `assetUrl`).
- `src/js/spatial_stress.test.cjs`: Geo-spatial clustering performance benchmarks.
- `src/js/virtualgrid_stress.test.cjs`: VirtualGrid 50,000 item recycling and memory leak verification.

---

### 2.2 Rust Test Suite (`cargo test --manifest-path src-tauri/Cargo.toml`)
- **Runner**: Cargo built-in test runner.
- **Structure**: Co-located unit tests inside module files under `#[cfg(test)] mod tests` and integration benchmarks under `tests/backend_stress_suite.rs`.
- **Execution Results**:
  - **Unit Tests**: **33 out of 33 tests passed cleanly (100% pass, 0 failures)**.
  - **Integration Stress Suite**: 3 out of 4 tests passed (`test_multi_threaded_folder_scan_simulation`, `test_thumbnail_cache_concurrency_and_hit_latency`, `test_database_multi_threaded_concurrency_stress`).
  - **Benchmark Note**: 1 integration benchmark (`test_bktree_10000_items_duplicate_query_benchmark`) recorded 2.491ms in unoptimized debug build mode (`cargo test`), slightly exceeding the 2.0ms limit. Passes cleanly when executed in release profile (`cargo test --release`).
- **Current Unit Test Coverage**:
  - `lib.rs`: Percent decoding (`test_decode_percent_utf8_cyrillic`), custom asset protocol byte range requests (`test_handle_asset_custom_protocol_range_and_headers`).
  - `onnx.rs`: IoU calculation (`test_iou_calculation`), Non-Maximum Suppression (`test_nms_suppression`), Cosine similarity & vector normalization (`test_cosine_similarity_and_normalization`), Text & Image embedding extraction (`test_text_and_image_embedding_generation`).
  - `export.rs`: Unicode watermark positioning calculation (`test_watermark_position_unicode`), Watermark execution stability (`test_apply_watermark_no_panic`).
  - `duplicates.rs`: Hamming distance calculation (`test_hamming_distance`), Duplicate stats computation (`test_get_duplicate_stats`), 32-bit pHash computation (`test_compute_hash_32_phash`), BK-Tree similarity query (`test_bktree_query`).


---

## 3. Required Feature Touchpoints (R1, R2, R3, R4)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                             WiPhoto Frontend                             │
│  ┌────────────────────┐ ┌────────────────────┐ ┌──────────────────────┐  │
│  │ Split View / Loupe │ │   Live Histogram   │ │ Web Worker Grid Sort │  │
│  │    (src/js/ viewer)│ │ (src/js/ editor)   │ │ (grid-sorter.worker) │  │
│  └─────────┬──────────┘ └─────────┬──────────┘ └──────────┬───────────┘  │
└────────────┼──────────────────────┼───────────────────────┼──────────────┘
             │ IPC Bridge (invoke)  │ asset:// Streaming    │ Web Worker
┌────────────┼──────────────────────┼───────────────────────┼──────────────┐
│  ┌─────────▼──────────┐ ┌─────────▼──────────┐ ┌──────────▼───────────┐  │
│  │ tract-onnx AI Embed│ │ Batch Export & JXL │ │ Custom Asset Protocol│  │
│  │ (src-tauri/onnx.rs)│ │ (commands/export)  │ │ (src-tauri/lib.rs)   │  │
│  └────────────────────┘ └────────────────────┘ └──────────────────────┘  │
│                              Rust Backend                                │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3.1 R1: Local AI & Deduplication
- **Rust Backend Touchpoints**:
  - `src-tauri/src/onnx.rs`: Extend `tract-onnx` model pipeline to support face embedding extraction alongside object detection.
  - `src-tauri/src/commands/duplicates.rs`: Implement new commands:
    - `index_faces(paths: Vec<String>) -> Result<u32, String>`: Extract face embeddings and store in SQLite.
    - `find_similar_images(path: String, threshold: f32) -> Result<Vec<SimilarMatch>, String>`: Perform cosine similarity vector search across face/image embeddings.
    - `get_face_clusters() -> Result<Vec<FaceCluster>, String>`: Group face embeddings into recognized person clusters.
  - `src-tauri/src/lib.rs`: Register `index_faces`, `find_similar_images`, `get_face_clusters` in `tauri::generate_handler![]`.
- **Frontend Touchpoints**:
  - `src/js/api.js`: Add `indexFaces`, `findSimilarImages`, `getFaceClusters` wrappers.
  - `src/js/gallery.js` & `src/js/search.js`: Add face cluster filter chips, duplicate group badges, and "Find Similar" context menu action.
  - **Event Bus**: Emit `ai-index-progress` events `{ current: u32, total: u32 }`.

---

### 3.2 R2: Pro Workflow UI
- **Frontend Touchpoints**:
  - `src/index.html`: Add `#view-split` workspace container with split-screen splitters (`#split-left`, `#split-right`, `#split-divider`), `#filmstrip-container` inside Loupe view, and `#histogram-canvas`.
  - `src/js/viewer.js`: Implement `SplitViewManager`:
    - Side-by-side photo comparison mode (left vs right photo selection).
    - Synchronized zoom & pan event listeners across both viewports.
    - Wipe slider comparison mode (clip-path manipulation).
    - Horizontal Filmstrip view with keyboard shortcut navigation (Left/Right arrow keys).
  - `src/js/editor.js`: Implement live RGB and Luminance histogram calculation using 2D Canvas context / WebGL pixel extraction.

---

### 3.3 R3: WebGPU & Web Workers
- **Frontend Touchpoints**:
  - `src/js/webgpu-renderer.js`: Implement WebGPU non-destructive adjustment pipeline using `navigator.gpu`, `GPURenderPipeline`, and WGSL shaders (exposure, contrast, highlights, shadows, HSL adjustments) with automatic fallback to 2D Canvas when WebGPU is unsupported.
  - `src/js/workers/grid-sorter.worker.js`: Create dedicated Web Worker for offloading VirtualGrid filtering (date, rating, color label, search query) and multi-column array sorting across 50,000 photo records.
  - `src/js/virtualgrid.js`: Refactor `VirtualGrid` to delegate sorting tasks to `grid-sorter.worker.js` via `postMessage` and non-blocking asynchronous array transfer.

---

### 3.4 R4: Advanced Formats & Batch Export
- **Rust Backend Touchpoints**:
  - `src-tauri/Cargo.toml`: Enable AVIF and JPEG XL decoding/encoding in `image` crate dependencies (or add `image = { version = "0.25", features = ["jpeg", "png", "gif", "webp", "avif"] }` and `jxl-oxide` / `jpeg-xl-rs`).
  - `src-tauri/src/lib.rs`: Add MIME type resolution for `.avif` (`image/avif`) and `.jxl` (`image/jxl`) in `handle_asset_custom_protocol`.
  - `src-tauri/src/commands/export.rs`: Extend `export_files` command:
    - Support AVIF and JXL format encoding options.
    - Add `strip_exif: bool` option to drop EXIF metadata during output generation.
    - Add `max_width: Option<u32>`, `max_height: Option<u32>` aspect-ratio preserving downscaling.
- **Frontend Touchpoints**:
  - `src/js/batch.js` & `src/index.html`: Update Batch Export modal to include output format dropdown (`JPEG`, `PNG`, `WebP`, `AVIF`, `JPEG XL`), resolution constraint inputs, EXIF stripping toggle checkbox, and watermark text box.
  - `src/js/api.js`: Update `exportFiles` parameter signature.

---

## 4. Testing Requirements & Verification Criteria

| Requirement | Test Scope | Framework | Execution Command | Target File Location | Verification Criteria |
|---|---|---|---|---|---|
| **R1.1 ONNX AI Test** | Rust Integration Test | `cargo test` | `cargo test --manifest-path src-tauri/Cargo.toml -- test_onnx` | `src-tauri/src/onnx.rs` or `src-tauri/tests/onnx_test.rs` | Load dummy ONNX model graph / mock tensor; generate 512-dim embedding; verify non-zero normalized vector output without panic. |
| **R2 Split View Test** | Node.js Unit Test | `node:test` | `npm run test` | `src/js/splitview.test.cjs` | Verify `SplitViewManager` state transitions: image loading, synchronized pan/zoom calculations, split-slider position bounds, and clean exit resets. |
| **R3 Web Worker Test** | Node.js Unit Test | `node:test` | `npm run test` | `src/js/virtualgrid_worker.test.cjs` | Verify Worker message passing: post 50,000 item dataset to worker, perform multi-column sort & filter, receive sorted index array without main thread blocking. |
| **R4 Batch Export Test** | Rust Integration Test | `cargo test` | `cargo test --manifest-path src-tauri/Cargo.toml -- test_batch_export` | `src-tauri/src/commands/export.rs` or `src-tauri/tests/export_test.rs` | Execute batch export pipeline with resizing, format conversion (JPG $\rightarrow$ AVIF/PNG), EXIF stripping, and watermarking; assert output files exist and are valid. |
| **Full Suite Readiness** | E2E Regression | Node + Cargo | `npm run test` && `cargo test --manifest-path src-tauri/Cargo.toml` | Entire Repository | 100% test pass rate, 0 errors, 0 panics across Node.js and Rust test suites. |

---

## 5. Recommended Milestone Boundaries

### Milestone 1 (M1): Backend Engine Expansion & ML Foundation (R1 & R4 Backend)
- Update `src-tauri/Cargo.toml` with AVIF/JXL and ML dependencies.
- Implement Rust ONNX face index & similar image commands (`index_faces`, `find_similar_images`) in `src-tauri/src/onnx.rs` & `duplicates.rs`.
- Implement AVIF/JXL asset protocol handling and enhanced batch export (resizing, format conversion, EXIF stripping) in `src-tauri/src/commands/export.rs`.
- Implement Rust integration tests: `R1.1` ONNX test and `R4` batch export test.
- **Verification**: `cargo test --manifest-path src-tauri/Cargo.toml` passes with 0 errors.

### Milestone 2 (M2): Pro Workflow UI & Histogram Integration (R2)
- Add Split View UI (`#view-split`), Loupe Filmstrip view, and `#histogram-canvas` to `src/index.html` and `src/styles/`.
- Implement `SplitViewManager` in `src/js/viewer.js` with sync zoom/pan and split slider controls.
- Implement live RGB and Luminance histogram rendering in `src/js/editor.js`.
- Add Node.js test suite `src/js/splitview.test.cjs` for `SplitViewManager`.
- **Verification**: Node.js tests for Split View pass cleanly under `npm run test`.

### Milestone 3 (M3): WebGPU Renderer & Web Workers (R3)
- Create Web Worker `src/js/workers/grid-sorter.worker.js` for 50,000-item array sorting/filtering.
- Integrate worker message channel into `src/js/virtualgrid.js`.
- Implement WebGPU shader-based color adjustment pipeline in `src/js/webgpu-renderer.js` with 2D Canvas fallback.
- Add Node.js test suite `src/js/virtualgrid_worker.test.cjs` verifying Web Worker message passing and grid state sync.
- **Verification**: Node.js tests for Web Worker pass cleanly under `npm run test`.

### Milestone 4 (M4): E2E Integration, Verification & Release Readiness
- Full regression run of both test suites (`npm run test` and `cargo test`).
- Execute 50,000 item virtual grid stress test and adversarial OTA update harness.
- Audit public IPC contracts and verify 0 console errors/panics.
- **Verification**: 100% pass across all test suites; ready for 5.0 release tagging.
