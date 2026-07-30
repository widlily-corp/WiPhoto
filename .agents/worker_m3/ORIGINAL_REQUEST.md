## 2026-07-30T14:38:19Z
You are worker_backend_m3. Your working directory is `c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_m3`.

Scope & Mission: Optimize Rust backend performance in `src-tauri/`, implement async thumbnail generation and caching, decouple ONNX scan, optimize SQLite connection pooling, fix bugs, and achieve zero Clippy warnings.

Upstream Explorer Reports:
- Read `c:\Users\Widlily\Documents\projects\wiphoto\.agents\explorer_backend\handoff.md`
- Read `c:\Users\Widlily\Documents\projects\wiphoto\.agents\explorer_stability\handoff.md`

Detailed Tasks:
1. `src-tauri/src/db.rs`: Connection Pooling / Connection Handle Reuse.
   - Stop opening a fresh SQLite connection on every command query. Maintain a shared, persistent connection handle or connection pool (e.g. wrapped in `Mutex`/`RwLock` or `r2d2`/pool) so DB ops are low-overhead.
2. `src-tauri/src/commands/thumbnails.rs`: Async & Cached Thumbnails.
   - Refactor image decoding and resizing to execute asynchronously using `tokio::task::spawn_blocking` and Rayon parallel iterator.
   - Implement an in-memory thumbnail cache using `parking_lot::RwLock<HashMap<String, Vec<u8>>>` (or LRU cache) to avoid re-generating existing thumbnails.
3. `src-tauri/src/scanner.rs`: Fast Decoupled Directory Scanning.
   - Decouple heavy ONNX model loading and vector embedding generation from the directory traversal scan loop.
   - Traverse directory with Rayon / fast async I/O, insert/update file metadata into DB, and enqueue embedding tasks asynchronously so folder scanning finishes in sub-seconds.
   - Fix non-recursive orphan file deletion logic (ensure missing files in subdirectories are correctly marked or pruned).
4. `src-tauri/src/commands/duplicates.rs`:
   - Fix duplicate finder fallback hashing logic when primary hash is missing or fails, preventing silent empty return.
5. `src-tauri/src/lib.rs` & `src-tauri/src/file_ops.rs`:
   - Fix unhandled `unwrap()` calls and potential panic points in Tauri command handlers and file operations.
   - Protect GPS EXIF extraction against NaN / Infinity coordinates.
6. Verification & Quality:
   - Run `cargo check` in `src-tauri/`.
   - Run `cargo clippy -- -D warnings` in `src-tauri/` and fix all warnings.
   - Run `cargo test` in `src-tauri/` and verify all tests pass.
7. Write `handoff.md` in `c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_m3\handoff.md` with:
   - Observation, Logic Chain, Caveats, Conclusion, Verification Results (`cargo clippy` and `cargo test` output).
   - Notify parent agent via `send_message`.
