# WiPhoto Optimization Plan

## Phase 1: Exploration & Diagnostics (M1)
- Dispatch 3 parallel Explorers:
  1. `explorer_frontend`: Analyze `VirtualGrid`, DOM update bottlenecks, layout thrashing, scroll event handling, and current frontend lints/errors.
  2. `explorer_backend`: Analyze Rust backend codebase (`src-tauri`), folder scanning performance, thumbnail generation, caching, thread pool usage, rayon/tokio integration, clippy/cargo status.
  3. `explorer_stability`: Identify silent errors, uncaught promises, race conditions, memory leaks, and edge-case crash scenarios during startup/scan/view.

## Phase 2: Frontend & Backend Implementation (M2 & M3)
- Dispatch Workers to refactor `VirtualGrid` (visible item rendering + buffer, recycling/virtualization without layout thrashing).
- Dispatch Workers to optimize Rust backend (Rayon parallel directory traversal, async thumbnail generation, lock-free or low-contention caching).

## Phase 3: Error Elimination & Refactoring (M4)
- Fix all identified bugs, race conditions, silent errors.
- Clean up any linting/clippy errors to ensure ESLint 0 errors and Cargo Clippy 0 warnings.

## Phase 4: Verification, Building & Audit (M5)
- Run ESLint, Cargo Clippy, and Tauri build via Reviewers / Workers.
- Run Challengers to stress test scrolling and rapid folder scanning.
- Run Forensic Auditor to perform integrity audit.
- Synthesize results and report completion to user.
