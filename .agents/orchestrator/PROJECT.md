# Project: WiPhoto v5.0.0 — Audit, Thumbnail Fix, OTA CI/CD, & Release

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
- **CI/CD Layout (`.github/workflows/`)**:
  - GitHub Actions workflow files for multi-platform build, test, and release (Windows, macOS, Linux).

## Interface Contracts
### Rust ↔ JS IPC Protocol
- `get_image_url(path: String) -> String`: returns custom protocol URL (`tauri://...` or `asset://...`) for zero-copy rendering
- `generate_thumbnail(path: String) -> Result<String, String>`: generates or retrieves cached thumbnail for ARW/RAW/JPG
- `check_for_updates() -> Result<UpdateInfo, String>`: interacts with `tauri-plugin-updater`
- `sync_xmp_sidecar(image_path: String, metadata: XmpMetadata) -> Result<(), String>`: XMP sidecar sync

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Fix Thumbnail Display (ARW/JPG) & Deep Audit | Investigate thumbnail rendering bug in ARW/JPG, protocol streaming, virtual grid, perform deep audit of JS & Rust backend for bugs/races | None | IN_PROGRESS |
| M2 | GitHub Actions CI/CD Pipeline Optimization | Review & rewrite GitHub Actions workflows for fast multi-platform builds (Win/macOS/Linux), caching, and OTA artifact publishing | None | PLANNED |
| M3 | Tauri OTA Update Mechanism Verification | Verify `tauri-plugin-updater` configuration, GitHub Releases endpoints, update dialog UI, Markdown renderer, update checks | M2 | PLANNED |
| M4 | Final Build Verification, Forensic Audit & Release 5.0 | Verify clean build/test (0 lint errors, 0 warnings), run Forensic Auditor, commit changes, push `v5.0.0` tag & release | M1, M2, M3 | PLANNED |
