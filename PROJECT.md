# Project: WiPhoto v5.0

## Architecture
- Core Stack: Tauri v2 + Rust Backend + Vanilla JS Frontend.
- IPC & Streaming: Tauri `invoke` commands and custom `asset://` protocol with Range requests & ETag caching.
- ML & AI: `tract-onnx 0.21.3` in Rust backend (`src-tauri/src/onnx.rs` & `duplicates.rs`).
- Image Processing: `image` crate (with `jpeg`, `png`, `gif`, `bmp`, `tiff`, `webp`, `avif-native`) + `jxl-oxide` for JPEG XL decoding.
- UI Framework: Vanilla HTML5 + ES6 IIFE modules (`src/index.html`, `src/js/`), CSS variables in `src/styles/`.
- Hardware Acceleration: `webgpu_renderer.js` using WebGPU WGSL shaders for instant non-destructive adjustments (exposure, contrast, HSL).
- Multi-threading: Web Workers (`src/js/workers/grid_worker.js`) for Virtual Grid sorting, filtering, and row layout math.
- Test Architecture: Node.js native test runner (`npm run test` -> `node --test src/js/*.test.cjs`) + Rust test framework (`cargo test --manifest-path src-tauri/Cargo.toml`).

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F1 | Local AI Face Indexing & Deduplication | Face recognition & image embedding similarity via `tract-onnx`, Tauri commands `index_faces` & `find_similar_images` | M1 | R1 |
| F2 | Dummy ONNX Model Integration Test | Offline dummy ONNX model graph execution test without network calls | M1 | R1 (AC) |
| F3 | Advanced Formats (AVIF & JXL) | AVIF decoding via `image` crate feature & JXL decoding via `jxl-oxide` crate, MIME mappings | M2 | R4 |
| F4 | Batch Export Module with EXIF Stripping | Resizing, format conversion, and `strip_exif: Option<bool>` option in `export_files` command & Rust test | M2 | R4 & AC |
| F5 | Pro Workflow UI: Split View / Compare Mode | Side-by-side photo comparison view (`#view-compare`), `SplitView` state manager (`splitview.js`), UI toggles | M3 | R2 |
| F6 | Pro Workflow UI: Filmstrip & Histograms | Loupe/Editor bottom thumbnail filmstrip (`filmstrip.js`), live RGB/Luminance histograms | M3 | R2 |
| F7 | WebGPU Adjustments Renderer | Hardware-accelerated non-destructive adjustments (exposure, contrast, HSL) via WGSL shaders (`webgpu_renderer.js`) | M4 | R3 |
| F8 | Web Worker Virtual Grid Offloading | Background worker (`grid_worker.js`) for Virtual Grid sorting/filtering to unblock main UI thread | M4 | R3 |
| F9 | Split View & Web Worker Node.js Tests | Node.js tests verifying Split View state manager and Web Worker message passing | M5 | R2/R3 (AC) |
| F10 | Full E2E & Test Suite Hardening | Pass 100% of Node.js tests (`npm run test`) and Rust tests (`cargo test`) cleanly with 0 errors | M5 | AC |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Rust ML Engine & Deduplication (R1) | ONNX model offline/mock execution, face indexing, similarity commands, Rust integration test | none | DONE |
| M2 | Advanced Formats & Batch Export (R4) | AVIF & JPEG XL decoding support, MIME mappings, `strip_exif` batch export, Rust batch export test | M1 | IN_PROGRESS |
| M3 | Pro Workflow UI Components (R2) | Split View / Compare Mode (`splitview.js`), Filmstrip (`filmstrip.js`), live RGB/Luminance histograms | M2 | PLANNED |
| M4 | WebGPU Renderer & Web Workers (R3) | WebGPU adjustments shader pipeline (`webgpu_renderer.js`), Web Worker Virtual Grid offloading (`grid_worker.js`) | M3 | PLANNED |
| M5 | E2E Testing & Verification Hardening | Node.js unit tests (`splitview.test.cjs`, `grid_worker.test.cjs`), complete `npm run test` & `cargo test` verification | M4 | PLANNED |

## Interface Contracts
### Rust Backend ↔ Frontend IPC
- `index_faces(path: String) -> Result<Vec<FaceEmbedding>, String>`
- `find_similar_images(threshold: f32) -> Result<Vec<DuplicateGroup>, String>`
- `export_files(paths: Vec<String>, dest_dir: String, format: String, quality: u8, max_width: Option<u32>, max_height: Option<u32>, watermark_text: Option<String>, strip_exif: Option<bool>) -> Result<ExportResult, String>`

### Frontend JS ↔ Web Worker Protocol
- Message type: `{ action: 'SORT_GRID', items: Array, sortBy: string, sortOrder: 'asc'|'desc' }`
- Response type: `{ type: 'GRID_SORTED', sortedIds: Array, durationMs: number }`

## Code Layout
- Backend Rust: `src-tauri/Cargo.toml`, `src-tauri/src/lib.rs`, `src-tauri/src/onnx.rs`, `src-tauri/src/commands/duplicates.rs`, `src-tauri/src/commands/export.rs`, `src-tauri/src/models/image_info.rs`
- Frontend UI: `src/index.html`, `src/styles/compare.css`, `src/styles/filmstrip.css`, `src/js/splitview.js`, `src/js/filmstrip.js`, `src/js/histogram.js`, `src/js/webgpu_renderer.js`, `src/js/workers/grid_worker.js`, `src/js/gallery.js`, `src/js/viewer.js`, `src/js/editor.js`, `src/js/app.js`
- Test Suites: `src-tauri/tests/`, `src-tauri/src/onnx.rs`, `src-tauri/src/commands/export.rs`, `src/js/splitview.test.cjs`, `src/js/grid_worker.test.cjs`
