## 2026-07-30T15:01:32Z
<USER_REQUEST>
You are the Remediation Worker for WiPhoto XMP Sidecar Atomic Write Fix.

Workspace Root: c:\Users\Widlily\Documents\projects\wiphoto
Working Directory: c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_remediation_xmp

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Audit Context:
Forensic Auditor reported INTEGRITY VIOLATION due to `tests/xmp_roundtrip_stress.rs::test_xmp_1000_sequential_roundtrip_updates` failing during 1,000 rapid sequential sidecar write/read updates on Windows. The failure is caused by non-atomic file writing / OS file handle caching contention in `write_xmp_sidecar` (`src-tauri/src/commands/xmp.rs`).

Your Tasks:
1. Inspect `src-tauri/src/commands/xmp.rs` and `write_xmp_sidecar`.
2. Implement atomic file writing and flushing for XMP sidecars:
   - Use atomic file replacement (e.g. write to temporary file `.tmp` and `fs::rename`, or use explicit file sync `file.sync_all()`).
   - Add exponential backoff / retry loop (up to 3-5 retries with short sleep e.g. 5ms) when opening/writing/renaming the sidecar file to handle transient Windows OS file locks.
3. Verification:
   - Run `cargo test --manifest-path src-tauri/Cargo.toml --test xmp_roundtrip_stress` and verify that `test_xmp_1000_sequential_roundtrip_updates` passes 100% reliably.
   - Run `cargo check --manifest-path src-tauri/Cargo.toml` (0 errors).
   - Run `cargo clippy --manifest-path src-tauri/Cargo.toml -- -D warnings` (0 warnings).
   - Run `cargo test --manifest-path src-tauri/Cargo.toml` (all tests pass 100%).
4. Record your findings, actions taken, and verification logs in `c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_remediation_xmp\handoff.md`.
</USER_REQUEST>
