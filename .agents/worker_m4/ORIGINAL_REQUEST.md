## 2026-07-30T08:37:20Z
<USER_REQUEST>
You are the Implementation Worker for Milestone 4: Smart Albums (R1).
Working directory: `c:\Users\Widlily\Documents\projects\wiphoto`
Metadata directory: `c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_m4`

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Task:
1. Implement Smart Albums with local CLIP semantic search (R1).
2. Expand `src-tauri/src/onnx.rs` and `src-tauri/src/db.rs` to support multimodal text and image embeddings.
3. Implement Rust IPC search command `search_clip_semantic(query: String, limit: usize)` that converts text queries ("dog on a beach", "sunset over mountains", "family photo") into vector embeddings and ranks library photos using cosine similarity against stored image vector embeddings.
4. Ensure inference and vector search work 100% offline without any calls to external APIs.
5. Wire frontend UI (`src/js/search.js` or `app.js` or search bar) to execute semantic query search and display Smart Album search results.
6. Add unit tests for embedding calculation, similarity ranking, and search results in Rust (`onnx.rs`, `db.rs`) and JS.
7. Verify `cargo check`, `cargo test`, and `npm test` pass cleanly.
8. Make atomic conventional commit: `feat(clip): implement offline clip semantic search for smart albums`.
9. Write handoff report to `c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_m4\handoff.md` and notify parent.
</USER_REQUEST>
