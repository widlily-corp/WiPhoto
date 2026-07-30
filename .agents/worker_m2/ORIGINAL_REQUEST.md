## 2026-07-30T08:37:20Z

You are the Implementation Worker for Milestone 2: XMP Sidecar Sync (R2).
Working directory: `c:\Users\Widlily\Documents\projects\wiphoto`
Metadata directory: `c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_m2`

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Task:
1. Implement real-time bidirectional XMP sidecar synchronization (R2).
2. Wire up Rust metadata and editing commands (`src-tauri/src/commands/metadata.rs`, `xmp.rs`, `editor.rs`) so that whenever rating, label, tags, or exposure/color edits are saved, a valid standard `.xmp` sidecar file is created/updated adjacent to the original image (`filename.ext` -> `filename.xmp`).
3. Wire up scanner (`scanner.rs`) to read adjacent `.xmp` files when indexing photos and load existing ratings, tags, and edits.
4. Add unit and integration tests covering XMP creation, parsing, and update sync in Rust (`xmp.rs` unit tests) and JS (`src/js/tier1_tier2_features.test.cjs`).
5. Verify `cargo check`, `cargo test`, and `npm test` pass with 100% success rate.
6. Make atomic conventional commit: `feat(xmp): implement real-time bidirectional xmp sidecar sync`.
7. Write handoff report to `c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_m2\handoff.md` and notify parent.
