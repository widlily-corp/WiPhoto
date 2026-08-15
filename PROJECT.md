# Project: WiPhoto v5.1.4

## 1. System Architecture
- **Core Runtime & IPC**: Tauri v2 + Rust Backend + Vanilla JS Frontend. IPC implemented via strongly-typed Tauri `invoke` commands and zero-copy custom `asset:` / `tauri:` streaming protocol with HTTP Range requests, ETag caching, and Cyrillic percent-decoding.
- **Machine Learning & AI**: `tract-onnx 0.21.3` in Rust backend (`src-tauri/src/onnx.rs` & `commands/duplicates.rs`) for offline CLIP 512-dimensional vector embedding extraction, face detection, and BK-Tree perceptual hash indexing.
- **Image Processing & Decoders**: `image` crate (0.25) with native decoding for JPEG, PNG, WebP, AVIF, TIFF, BMP, GIF, and ICO, combined with `jxl-oxide` (0.9) for JPEG XL decoding and `kamadak-exif` for EXIF metadata parsing.
- **UI Architecture**: Vanilla HTML5 SPA (`src/index.html`), ES6 modular JS (`src/js/`), and modular CSS variables (`src/styles/`) implementing the *Refined Minimal* design system.
- **Hardware Acceleration**: WebGPU WGSL shader pipeline (`src/js/gpu-renderer.js`) for non-destructive exposure, contrast, temperature, tint, highlights, shadows, vibrance, and HSL color adjustments.
- **Multi-threading & Offloading**: Web Workers (`src/js/grid-worker.js` and `src/js/grid-worker-logic.js`) offload Virtual Grid sorting, filtering, and row layout geometry from the main UI thread.
- **Database & State**: SQLite 3 bundled via `rusqlite 0.31` and thread-safe connection pooling via `r2d2` (`src-tauri/src/db.rs`), featuring WAL mode and vector cosine search.
- **Metadata Synchronization**: Bidirectional XMP Sidecar engine (`src-tauri/src/commands/xmp.rs`) with atomic writes and Adobe Lightroom format compatibility.
- **OTA Updates**: `tauri-plugin-updater 2` integration with resilient network retry, progress event streaming, checksum verification, and Markdown release notes renderer (`src/js/updater.js`).

---

## 2. Feature Inventory

| # | Feature | Description | Milestone | Status |
|---|---------|-------------|-----------|--------|
| F1 | Local AI Face Indexing & Deduplication | Face recognition & image embedding similarity via `tract-onnx`, Tauri commands `index_faces` & `find_similar_images` | M1 | VERIFIED |
| F2 | Dummy ONNX Model Integration Test | Offline dummy ONNX model graph execution test without network calls (`r1_onnx_test.rs`) | M1 | VERIFIED |
| F3 | Advanced Formats (AVIF & JXL) | AVIF decoding via `image` crate feature & JXL decoding via `jxl-oxide` crate, MIME mappings | M2 | VERIFIED |
| F4 | Batch Export Module with EXIF Stripping | Resizing, format conversion, and `strip_exif: Option<bool>` option in `export_files` command & Rust test | M2 | VERIFIED |
| F5 | Pro Workflow UI: Split View / Compare Mode | Side-by-side photo comparison view (`#view-compare`), synchronized zoom/pan, state manager (`compare.js`) | M3 | VERIFIED |
| F6 | Pro Workflow UI: Filmstrip & Histograms | Loupe/Editor bottom thumbnail filmstrip (`filmstrip.js`), live RGB/Luminance histograms | M3 | VERIFIED |
| F7 | WebGPU Adjustments Renderer | Hardware-accelerated non-destructive adjustments (exposure, contrast, HSL) via WGSL shaders (`gpu-renderer.js`) | M4 | VERIFIED |
| F8 | Web Worker Virtual Grid Offloading | Background worker (`grid-worker.js`) for Virtual Grid sorting/filtering to unblock main UI thread | M4 | VERIFIED |
| F9 | Split View & Web Worker Node.js Tests | Node.js tests verifying Compare View state manager and Web Worker message passing (`compare.test.cjs`, `gpu-worker.test.cjs`) | M5 | VERIFIED |
| F10 | Full E2E & Test Suite Hardening | 100% passing tests in Node.js test runner (`npm test`) and Rust test framework (`cargo test`) with 0 errors | M5 | VERIFIED |
| F11 | XMP Sidecar Synchronization | Bidirectional XMP metadata sync (ratings, labels, tags, edits) with Lightroom compatibility and atomic writes (`xmp.rs`) | M6 | VERIFIED |
| F12 | Resilient OTA Update Subsystem | Modal progress streaming, network drop recovery, retry loops, ESC key handling, and GitHub Releases CI/CD (`updater.js`) | M7 | VERIFIED |
| F13 | Global Command Palette (Ctrl+K) | Fuzzy action searching, keyboard navigation, instant batch tagging, F2 rename, Ctrl+E export shortcuts (`commandpalette.js`) | M7 | VERIFIED |
| F14 | Zero-Copy Streaming Protocol | Custom `asset:` / `tauri:` protocol with Range requests, ETag caching, Cyrillic URL decoding (`src-tauri/src/lib.rs`) | M7 | VERIFIED |

---

## 3. Milestones & Delivery Status

| # | Milestone Name | Scope | Verification Gate | Status |
|---|----------------|-------|-------------------|--------|
| M1 | Rust ML Engine & Deduplication | ONNX model offline inference, face indexing, similarity commands, pHash BK-Tree | `r1_onnx_test.rs`, `r1_challenger_stress.rs` | COMPLETED |
| M2 | Advanced Formats & Batch Export | AVIF & JPEG XL decoding, batch export pipeline, EXIF stripping, memory benchmarks | `r4_batch_export_test.rs`, `r4_challenger_stress_test.rs` | COMPLETED |
| M3 | Pro Workflow UI Components | Compare Mode (`compare.js`), Filmstrip (`filmstrip.js`), live histograms, shortcuts | `compare.test.cjs`, `tier1_tier2_features.test.cjs` | COMPLETED |
| M4 | WebGPU Renderer & Web Workers | WGSL shader pipeline (`gpu-renderer.js`), Web Worker sorting math (`grid-worker.js`) | `gpu-worker.test.cjs`, `virtualgrid_stress.test.cjs` | COMPLETED |
| M5 | E2E Testing & Verification Hardening | Full 4-tier Node.js test suite + Rust test suites passing 100% cleanly | `npm test` (117 tests) & `cargo test` (74 tests) | COMPLETED |
| M6 | XMP Sidecar Synchronization | Lightroom-compatible `.xmp` reading, writing, retries, and concurrent update safety | `xmp_roundtrip_stress.rs`, `db.rs` tests | COMPLETED |
| M7 | Resilient OTA Updates & Release 5.1.4 | OTA progress events, error recovery, changelog modal, CI/CD multi-platform release | `updater_e2e.test.cjs`, `ci.yml` matrix | COMPLETED |

---

## 4. Interface Contracts

### 4.1 Rust Backend ↔ Frontend IPC Commands
- `scan_folder(path: String, recursive: bool) -> Result<ScanSummary, String>`
- `get_photos(album_id: Option<i64>, filter: Option<PhotoFilter>) -> Result<Vec<ImageInfo>, String>`
- `index_faces(path: String) -> Result<Vec<FaceEmbedding>, String>`
- `find_similar_images(threshold: f32) -> Result<Vec<DuplicateGroup>, String>`
- `search_clip(query: String, limit: usize) -> Result<Vec<SearchResult>, String>`
- `export_files(paths: Vec<String>, dest_dir: String, format: String, quality: u8, max_width: Option<u32>, max_height: Option<u32>, watermark_text: Option<String>, strip_exif: Option<bool>) -> Result<ExportResult, String>`
- `save_adjustments(path: String, adjustments: AdjustmentParams, sync_xmp: bool) -> Result<bool, String>`
- `read_xmp_sidecar(path: String) -> Result<XmpMetadata, String>`
- `write_xmp_sidecar(path: String, metadata: XmpMetadata) -> Result<bool, String>`
- `move_to_trash(paths: Vec<String>) -> Result<usize, String>`
- `restore_from_trash(paths: Vec<String>) -> Result<usize, String>`

### 4.2 Frontend JS ↔ Web Worker Protocol (`grid-worker.js`)
- **Worker Request**:
  ```json
  {
    "action": "SORT_GRID",
    "items": [{ "id": 1, "date_taken": 1700000000, "rating": 5, "file_name": "photo.jpg" }],
    "sortBy": "date_taken" | "rating" | "file_name" | "file_size",
    "sortOrder": "asc" | "desc"
  }
  ```
- **Worker Response**:
  ```json
  {
    "type": "GRID_SORTED",
    "sortedIds": [1, 2, 3],
    "durationMs": 1.45
  }
  ```

### 4.3 OTA Update State Machine Protocol (`updater.js`)
- **States**: `IDLE` ➔ `CHECKING` ➔ `AVAILABLE` ➔ `DOWNLOADING` ➔ `VERIFYING` ➔ `RESTARTING` (with branch to `ERROR` on network drop / verification failure).
- **Progress Event Payload**:
  - `Started { contentLength: Option<u64> }`
  - `Progress { chunkLength: usize }`
  - `Finished`

---

## 5. Code Layout

```text
src/
├── index.html                   # Master UI markup & view containers
├── js/
│   ├── api.js                   # Tauri IPC wrappers & command invocations
│   ├── app.js                   # Application lifecycle & view router
│   ├── batch.js                 # Batch operations, tagging & export dialogs
│   ├── commandpalette.js        # Global command palette & shortcut registry
│   ├── compare.js               # Side-by-side photo comparison view
│   ├── editor.js                # Photo editor logic & adjustment sliders
│   ├── filmstrip.js             # Bottom thumbnail filmstrip for Loupe/Editor
│   ├── gallery.js               # Gallery state, album filtering, selection
│   ├── gpu-renderer.js          # WebGPU WGSL adjustment pipeline
│   ├── grid-worker.js           # Web Worker message coordinator
│   ├── grid-worker-logic.js     # Pure sorting & filtering algorithms
│   ├── logger.js                # Structured logging & error capture
│   ├── map.js                   # Leaflet + Supercluster GPS map view
│   ├── search.js                # Semantic CLIP search & text queries
│   ├── settings.js              # Settings modal & updater triggers
│   ├── shortcuts.js             # Global keyboard shortcut dispatcher
│   ├── sidebar.js               # Navigation panel (albums, tags, places)
│   ├── slideshow.js             # Fullscreen slideshow presentation
│   ├── tags.js                  # Tagging, color labels, ratings manager
│   ├── timeline.js              # Timeline group builder & jump scroll
│   ├── trash.js                 # Safe deletion & trash restore manager
│   ├── updater.js               # OTA update UI, state machine & retry loop
│   ├── utils.js                 # Helpers (zero-copy URLs, debounce, toast)
│   ├── viewer.js                # Single photo loupe view & zoom engine
│   ├── virtualgrid.js           # Virtual scrolling DOM grid with diffing
│   ├── welcome.js               # Welcome view & folder onboarding
│   └── *.test.cjs               # 12 Node.js unit and integration test suites
├── lib/
│   ├── leaflet.js / .css        # Map rendering library
│   └── supercluster.min.js      # Geo-spatial point clustering
└── styles/                      # Refined Minimal design system stylesheets
    ├── commandpalette.css, components.css, crop.css, editor.css,
    ├── gallery.css, main.css, map.css, sidebar.css, variables.css, viewer-pro.css

src-tauri/
├── Cargo.toml                   # Rust crate configuration & dependencies
├── tauri.conf.json              # Tauri v2 application configuration
├── src/
│   ├── main.rs                  # Native application entry point
│   ├── lib.rs                   # Plugin registration, custom protocol, commands
│   ├── db.rs                    # SQLite r2d2 connection pool, migrations, vectors
│   ├── onnx.rs                  # tract-onnx CLIP and face embedding inference
│   ├── models/
│   │   ├── image_info.rs        # ImageInfo, ExifData, Adjustments, Duplicates models
│   │   └── mod.rs
│   └── commands/
│       ├── duplicates.rs        # pHash, Hamming distance, BK-Tree similarity
│       ├── editor.rs            # Image adjustments engine & atomic file save
│       ├── export.rs            # Batch export, format conversion, EXIF stripping
│       ├── file_ops.rs          # File move, copy, rename, delete to trash
│       ├── metadata.rs          # EXIF/IPTC/GPS extraction & geotagging
│       ├── raw_utils.rs         # RAW preview thumbnail extraction
│       ├── scanner.rs           # Multi-threaded Rayon directory scanner
│       ├── search.rs            # Semantic CLIP vector search command handlers
│       ├── settings.rs          # Persistent application settings
│       ├── thumbnails.rs        # Multi-tier thumbnail generation & caching
│       ├── xmp.rs               # XMP sidecar reading, writing, sync
│       └── mod.rs
└── tests/                       # 9 Rust integration and stress test suites
```
