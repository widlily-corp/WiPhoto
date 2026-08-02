## 2026-08-02T04:59:46Z

You are a Worker agent assigned to fix an XMP sidecar history truncation defect in WiPhoto's Rust backend uncovered by stress testing.

Your identity:
- Archetype: teamwork_preview_worker
- Working directory: c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_remediation_xmp
- Scope document: c:\Users\Widlily\Documents\projects\wiphoto\.agents\orchestrator\PROJECT.md

Defect Details:
In `src-tauri/src/commands/xmp.rs` (around lines 129-142), `write_xmp_sidecar` reads existing XMP file content and calls `parse_xmp_content(&content)`. During rapid sequential updates (e.g. `test_xmp_1000_sequential_roundtrip_updates` in `tests/xmp_roundtrip_stress.rs`), if `parse_xmp_content` returns `None` (or if file reading encounters a brief lock/flush delay), `existing` evaluates to `None` and `history` defaults to an empty `Vec::new()`. Pushing the new entry appends only 1 item, silently truncating all previous history entries.

Task Objectives:
1. Modify `src-tauri/src/commands/xmp.rs` so `write_xmp_sidecar` reliably reads and parses existing sidecar files without dropping history.
2. Implement file read retry logic (e.g., exponential backoff / retry loop for reading existing file content) if the sidecar file exists on disk, and handle parse errors gracefully so existing history entries are never overwritten or reset to empty on transient read failures.
3. Run `cargo test --manifest-path src-tauri/Cargo.toml --test xmp_roundtrip_stress` and ensure `test_xmp_1000_sequential_roundtrip_updates` passes 100% without any history length mismatch.
4. Run `cargo test --manifest-path src-tauri/Cargo.toml` (all tests) and `cargo clippy --manifest-path src-tauri/Cargo.toml -- -D warnings` to verify clean compilation, 0 warnings, and 100% test pass rate.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Maintain `progress.md` in your working directory. Report all changes, build outputs, and test results in your handoff report to `c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_remediation_xmp\handoff.md`. Send your handoff path to parent via `send_message`.
