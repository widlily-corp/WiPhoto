## 2026-07-30T14:56:38Z
You are the Backend Worker for WiPhoto Rust Backend Performance & Error Elimination.

Workspace Root: c:\Users\Widlily\Documents\projects\wiphoto
Working Directory: c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_backend_m3_opt

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Tasks:
1. Inspect the Rust backend under `src-tauri/` (`src/main.rs`, `src/lib.rs`, `src/commands/`, `src/cache/`, `src/scanner/`, `src/db.rs`, `src/onnx.rs`).
2. Verify / implement Backend Performance Optimization:
   - Async & multi-threaded folder scanning using Rayon or tokio asynchronous tasks (`spawn_blocking`) so main UI thread never freezes.
   - Async thumbnail generation using `spawn_blocking` with an in-memory thumbnail cache (or fast disk cache hit path) to reduce duplicate thumbnail generation latency.
   - Decouple ONNX scanning / embedding computation from the initial folder indexing IPC stream so directory traversal completes rapidly and ONNX embedding runs in background.
   - SQLite DB connection pooling / reuse (`PRAGMA journal_mode = WAL; PRAGMA busy_timeout = 5000;`).
3. Error Elimination & Stability (Phase 3):
   - Fix any potential panic / unwrap paths in Rust code, ensure safe error handling with `Result<T, String>`.
   - Fix any non-recursive orphan cleanup or race conditions in scanning/db.
4. Static Analysis & Tests:
   - Run `cargo check --manifest-path src-tauri/Cargo.toml` and ensure 0 compilation errors.
   - Run `cargo clippy --manifest-path src-tauri/Cargo.toml -- -D warnings` and fix ALL clippy warnings until 0 warnings remain.
   - Run `cargo test --manifest-path src-tauri/Cargo.toml` and ensure all tests pass.
5. Record your findings, actions taken, exact outputs of `cargo check`, `cargo clippy -- -D warnings`, and `cargo test` in a handoff report at `c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_backend_m3_opt\handoff.md`.
