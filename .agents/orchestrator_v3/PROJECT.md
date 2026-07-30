# Project: WiPhoto Performance & Error Elimination (v5.0 Optimization)

## Architecture
- **Frontend**: Vanilla JS (ES Modules) + HTML5 + CSS3 (Refined Minimal design system). Core views: Gallery, Timeline, VirtualGrid, Geo-Map (Leaflet), Command Palette.
- **Backend**: Tauri v2 (Rust). High-performance async & parallel image processing, folder scanning, thumbnail caching, XMP sidecar sync, local CLIP embeddings.
- **IPC**: Zero-copy custom protocol (`tauri://`).

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1: Exploration & Codebase Audit | Investigate VirtualGrid DOM thrashing, Rust multi-threading/rayon/tokio scanning/caching bottlenecks, existing JS/Rust bugs, and current eslint/clippy status | None | DONE |
| 2 | M2: Frontend UI Performance | Refine `VirtualGrid` (rAF scroll lock, DOM card recycling pool, O(1) active cards, eliminate forced reflows, fix IPC listener, ESLint v9 setup) | M1 | IN_PROGRESS |
| 3 | M3: Backend Performance & Multi-Threading | Rust backend async thumbnail `spawn_blocking`, in-memory thumbnail cache, decouple ONNX scan, fix non-recursive orphan deletion, DB connection reuse | M1 | IN_PROGRESS |
| 4 | M4: Error Elimination & Stability | Fix selection state indices -> path Set, search data loss bug, duplicate hashing fallback, unhandled panics/unwrap, GPS NaN protection | M1, M2, M3 | PLANNED |
| 5 | M5: Verification & Quality Gate | Run ESLint (0 errors), `cargo check` & `cargo clippy -- -D warnings` (0 warnings), `npm run tauri -- build` (clean build), stress test, and Forensic Audit | M2, M3, M4 | PLANNED |

## Interface Contracts
- **VirtualGrid**: Efficient viewport calculation based on `scrollTop`, `clientHeight`, `itemHeight`, `bufferSize`. Batch DOM updates using `requestAnimationFrame`.
- **Tauri Commands**: All heavy I/O and compute (scanning, thumbnails, caching) executed on thread pools (Rayon/tokio spawn_blocking), sending non-blocking events or async responses to JS.

## Code Layout
- `src/`: Frontend modules (`js/`, `css/`, `index.html`)
- `src-tauri/`: Tauri Rust backend (`src/main.rs`, `src/lib.rs`, `src/commands/`, `src/cache/`, `src/scanner/`)
