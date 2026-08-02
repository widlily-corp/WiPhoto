## 2026-08-02T04:51:49Z
You are a Worker agent implementing Rust backend fixes and protocol optimizations for WiPhoto.

Your identity:
- Archetype: teamwork_preview_worker
- Working directory: c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_m1_backend
- Scope document: c:\Users\Widlily\Documents\projects\wiphoto\.agents\orchestrator\PROJECT.md

Task Objectives:
1. Fix custom protocol URL handling in `src-tauri/src/commands/thumbnails.rs` and `src-tauri/src/lib.rs`:
   - Update `get_image_url` to match the registered custom protocol scheme `asset://localhost/` (or register `tauri://` custom protocol handler as well in `lib.rs` so both `asset` and `tauri` custom protocol URLs stream local image files cleanly zero-copy).
2. Fix RAW (ARW) embedded JPEG preview extraction in `src-tauri/src/raw_utils.rs` & `thumbnails.rs`:
   - Replace naive brute-force JPEG scanner (which picks the tiny 160x120 IFD0 thumbnail) with logic that selects the largest embedded JPEG stream in Sony ARW/RAW files (or uses EXIF/TIFF IFD offsets).
3. Enhance `handle_asset_custom_protocol` in `src-tauri/src/lib.rs`:
   - Add HTTP Range requests support (`206 Partial Content`).
   - Add HTTP caching headers (`Cache-Control: max-age=31536000, immutable`, `ETag`).
   - Add RAW image format MIME type mappings (`image/x-sony-arw`, etc.).
4. Fix concurrency & thread pool issues:
   - Replace blocking `tauri::async_runtime::block_on` in `list_trash` and `duplicates.rs` with proper async tasks to prevent Tokio worker thread starvation.
5. Fix database initialization and Clippy warnings:
   - Handle `DB_POOL` initialization errors gracefully in `src-tauri/src/db.rs` instead of unwrap/expect.
   - Resolve Clippy warnings (`clippy::items_after_test_module`, `clippy::map_entry`).
6. Run `cargo test` and `cargo clippy -- -D warnings` to verify clean compilation and zero warnings.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Maintain `progress.md` in your working directory. Report all changes, build outputs, and test results in your handoff report to `c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_m1_backend\handoff.md`. Send your handoff path to parent via `send_message`.
