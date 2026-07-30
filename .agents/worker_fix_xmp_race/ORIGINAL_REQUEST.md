## 2026-07-30T15:07:24Z

You are the XMP Race Fix Worker for WiPhoto.

Workspace Root: c:\Users\Widlily\Documents\projects\wiphoto
Working Directory: c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_fix_xmp_race

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Context & Issue:
`tests/xmp_roundtrip_stress.rs::test_xmp_1000_sequential_roundtrip_updates` randomly failed because `write_xmp_sidecar` in `src-tauri/src/commands/xmp.rs` silently ignored errors when reading an existing XMP file (`if let Ok(content) = read_to_string_with_retry(&xmp_path)`). On Windows NTFS, rapid file replacement (`fs::rename`) can briefly cause `read_to_string` or file open to return `PermissionDenied` or empty content. When `write_xmp_sidecar` swallowed this error, `history` and existing metadata were wiped, causing rating/history mismatches on subsequent iterations.

Your Tasks:
1. Edit `src-tauri/src/commands/xmp.rs`:
   - In `read_to_string_with_retry`: retry up to 10 times with exponential backoff (e.g. starting at 2ms) if `fs::read_to_string(path)` returns transient errors or empty string when file size > 0.
   - In `write_xmp_sidecar`: if `xmp_path.exists()`, call `read_to_string_with_retry(&xmp_path)`. If reading returns an error, return `Err(format!("Failed to read existing sidecar: {}", e))` rather than swallowing the error and wiping metadata.
2. Verification:
   - Run `cargo test --manifest-path src-tauri/Cargo.toml --test xmp_roundtrip_stress` multiple times to ensure 100% pass rate with zero failures.
   - Run `cargo check --manifest-path src-tauri/Cargo.toml` (0 errors).
   - Run `cargo clippy --manifest-path src-tauri/Cargo.toml -- -D warnings` (0 warnings).
   - Run `cargo test --manifest-path src-tauri/Cargo.toml` (all tests pass 100%).
3. Record your findings, code changes, and test execution results in `c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_fix_xmp_race\handoff.md`.
