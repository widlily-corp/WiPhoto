## 2026-07-30T08:32:00Z

<USER_REQUEST>
You are the Implementation Worker for Milestone 1: Zero-Copy Architecture (R4).
Working directory: `c:\Users\Widlily\Documents\projects\wiphoto`
Metadata directory: `c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_m1`

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Task:
1. Implement Zero-Copy Architecture (R4): Stop encoding images/thumbnails as Base64 strings in Rust (`STANDARD.encode`) and passing large base64 buffers to JS.
2. Implement custom Tauri v2 asset protocol (`tauri://` or `asset://`) in `src-tauri/src/lib.rs` / `src-tauri/tauri.conf.json` so images are loaded directly via URL tags `<img src="tauri://localhost/C:/path/to/image.jpg">` or similar URL protocol.
3. Update CSP in `tauri.conf.json` to allow `tauri:` / `asset:` protocols.
4. Refactor Rust commands in `src-tauri/src/commands/thumbnails.rs` and JS functions in `src/js/utils.js`, `src/js/virtualgrid.js`, `src/js/gallery.js`, `src/js/viewer.js`, `src/js/editor.js` to use protocol URLs for zero-copy loading.
5. Verify build and tests pass: `cargo check`, `cargo test`, `npm test`.
6. Make atomic conventional git commit: `feat(protocol): implement zero-copy tauri asset protocol`.
7. Write detailed handoff report with build/test outputs to `c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_m1\handoff.md` and report back to parent.
</USER_REQUEST>
