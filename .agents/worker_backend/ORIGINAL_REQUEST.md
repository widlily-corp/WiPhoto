## 2026-07-30T19:34:38+05:00

You are worker_backend (teamwork_preview_worker).
Your working directory is: c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_backend
Project root: c:\Users\Widlily\Documents\projects\wiphoto
Project spec: c:\Users\Widlily\Documents\projects\wiphoto\.agents\orchestrator_v3\PROJECT.md
Backend handoff report: c:\Users\Widlily\Documents\projects\wiphoto\.agents\explorer_backend\handoff.md
Stability handoff report: c:\Users\Widlily\Documents\projects\wiphoto\.agents\explorer_stability\handoff.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Tasks:
1. Initialize your working directory `.agents/worker_backend` with `BRIEFING.md` and `progress.md`.
2. Optimize Thumbnail Generation & Caching (`src-tauri/src/commands/thumbnails.rs`):
   - Add global lock-free in-memory cache `THUMBNAIL_CACHE` (`parking_lot::RwLock<HashMap<String, String>>`). Return cached thumbnail path in sub-millisecond lookups.
   - Convert `get_thumbnail` and `load_full_image` commands to `async fn` using `tauri::async_runtime::spawn_blocking` to avoid blocking Tauri IPC threads.
3. Decouple ONNX Inference from Folder Scanner (`src-tauri/src/commands/scanner.rs`):
   - Remove synchronous `crate::onnx::analyze_image(path)` from the core `scan_folder` / `process_single_file` loop to make folder scanning instant. Optionally queue background ONNX tasks asynchronously.
4. Fix Non-Recursive Scan Subfolder Record Deletion (`src-tauri/src/commands/scanner.rs`):
   - Fix `to_delete` orphan cleanup logic: only execute orphan deletion if `recursive == true`, or restrict `db_mtimes` lookup to direct child paths.
5. Fix Duplicate Finder Silent Failure (`src-tauri/src/commands/duplicates.rs`):
   - In `get_image_for_hashing`, if cached thumbnail is missing, generate thumbnail on-the-fly or fallback to reading source image via `image::open`.
6. Optimize SQLite DB Connection Handling (`src-tauri/src/db.rs`):
   - Implement thread-safe connection pooling or reusable database connection handle (`parking_lot::Mutex<Connection>`) to avoid re-opening file handles & setting PRAGMAs on every query.
7. Robustness & Error Handling (`src-tauri/src/lib.rs`, `src-tauri/src/file_ops.rs`, `src-tauri/src/commands/scanner.rs`):
   - Replace `.unwrap()` calls on HTTP response builder in `lib.rs` with safe error handling.
   - Handle database initialization error in `lib.rs` properly.
   - Fix GPS division-by-zero (`NaN`) in `scanner.rs` EXIF parser.
8. Verification:
   - Run `cargo check` in `src-tauri/` (0 errors).
   - Run `cargo clippy -- -D warnings` in `src-tauri/` (0 warnings/errors).
   - Run `cargo test` in `src-tauri/` (all tests pass).
9. Create handoff report `c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_backend\handoff.md` documenting code changes, build/test results, and send completion message to parent.
