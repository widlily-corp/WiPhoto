# Project: WiPhoto v5.0.0

## Architecture
- **Desktop Framework**: Tauri v2 (Rust backend + Vanilla JS/CSS frontend)
- **Backend Layout (`src-tauri/src/`)**:
  - `main.rs`, `lib.rs`: Entry point, Tauri builder, plugin registration, custom protocol registration
  - `onnx.rs`: Machine learning pipeline (YOLOv8 & CLIP embedding models)
  - `db.rs`: SQLite database for photo metadata, vector embeddings, albums
  - `commands/`: IPC handlers (`scanner`, `thumbnails`, `metadata`, `xmp`, `editor`, `export`, `settings`, `file_ops`, `duplicates`, `raw_utils`)
- **Frontend Layout (`src/`)**:
  - `index.html`: Main desktop interface container
  - `js/`: Modular ES modules (`app.js`, `virtualgrid.js`, `gallery.js`, `viewer.js`, `editor.js`, `commandpalette.js`, `map.js`, `search.js`, `updater.js`, `utils.js`)
  - `styles/`: Modular CSS stylesheets (`variables.css`, `main.css`, `components.css`, `sidebar.css`, `gallery.css`, `editor.css`, `commandpalette.css`, `map.css`)
  - `lib/`: Local offline vendor libraries (`leaflet.js`, `leaflet.css`, `supercluster.min.js`)

## Code Layout
- Frontend static files served via Tauri `frontendDist`: `"../src"`
- Custom protocol: `tauri://localhost/` or `asset://localhost/` streaming local image files zero-copy
- Metadata sidecars: `.xmp` files written adjacent to original image files
- Offline ML model storage: `.wiphoto/models/` or app data directory

## Interface Contracts
### Rust ↔ JS IPC Protocol
- `get_image_url(path: String) -> String`: returns `tauri://localhost/<path>` for zero-copy rendering
- `search_clip(query: String, threshold: f32) -> Vec<SearchResult>`: returns matching image paths with similarity scores
- `sync_xmp_sidecar(image_path: String, metadata: XmpMetadata) -> Result<(), String>`: writes/syncs `.xmp` sidecar
- `get_geotagged_photos() -> Vec<GeoPhoto>`: returns photo id, path, lat, lon for Supercluster map
- `check_for_updates() -> Result<UpdateInfo, String>`: interacts with `tauri-plugin-updater`

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M0 | E2E Testing Suite Track | Design Tier 1-4 test suite, runner, TEST_READY.md | None | IN_PROGRESS |
| M1 | Zero-Copy Asset Protocol | Custom `tauri://` protocol for zero-copy image loading | None | PLANNED |
| M2 | XMP Sidecar Bidirectional Sync | Auto-sync ratings, tags, exposure, color edits to `.xmp` | M1 | PLANNED |
| M3 | Geo-Map View (Offline Leaflet + Supercluster) | Local Leaflet/Supercluster, EXIF GPS clustering | M1 | PLANNED |
| M4 | Smart Albums (CLIP Semantic Search) | Local CLIP embeddings, natural language offline search | M1 | PLANNED |
| M5 | Refined Minimal UI & Command Palette | Linear/Stripe aesthetics, hairlines, Ctrl+K palette | M1 | PLANNED |
| M6 | OTA Updates Integration | `tauri-plugin-updater`, Markdown release notes modal | M1, M5 | PLANNED |
| M7 | E2E Verification & Release Tagging | Version bump to 5.0.0, 100% tests pass, conventional commits, git tag v5.0.0 & push | M1-M6, M0 | PLANNED |
