## 2026-07-30T09:11:28Z
You are the Remediation Worker for WiPhoto v5.0.0.
Working directory: `c:\Users\Widlily\Documents\projects\wiphoto`
Metadata directory: `c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_remediation`

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Task:
1. Fix R7 Release Cycle & Git Tagging:
   - Stage and commit uncommitted changes in `src/index.html` (and any other version references) so `v5.0.0` is committed everywhere across `package.json`, `Cargo.toml`, `tauri.conf.json`, `settings.rs`, `lib.rs`, and `index.html`.
   - Commit with atomic conventional commit: `feat(release): bump version to 5.0.0 and align index.html`.
   - Create local git tag `v5.0.0` (`git tag -a v5.0.0 -m "Release v5.0.0"`).
   - Push commits and tag to remote (`git push origin main --tags` / `git push origin v5.0.0`).

2. Fix IPC Interface Contract Discrepancies with `PROJECT.md`:
   - Implement `get_image_url(path: String) -> String` IPC handler in Rust (`src-tauri/src/commands/thumbnails.rs` or `lib.rs`) returning `asset://localhost/<path>` or `tauri://localhost/<path>` and register it in `tauri::generate_handler![]` in `lib.rs`.
   - Implement `search_clip(query: String, threshold: f32) -> Result<Vec<SearchResult>, String>` IPC handler in Rust (`src-tauri/src/commands/search.rs`) matching `PROJECT.md` contract.
   - Implement `sync_xmp_sidecar(image_path: String, metadata: XmpMetadata) -> Result<(), String>` IPC handler in Rust (`src-tauri/src/commands/xmp.rs`) matching `PROJECT.md` contract.

3. Fix Percent-Decoding in `src-tauri/src/lib.rs`:
   - Fix `decode_percent` function to decode percent-encoded UTF-8 byte sequences correctly (handling multi-byte Cyrillic and special characters like `%D1%85`) using proper UTF-8 byte decoding.

4. Verify compilation and test suites:
   - Run `cargo check`, `cargo test`, and `npm test` to ensure 100% pass rate.
   - Verify `git tag -l v5.0.0` returns `v5.0.0` and `git status` shows clean working tree.

5. Write detailed handoff report to `c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_remediation\handoff.md` and report back to parent agent.
