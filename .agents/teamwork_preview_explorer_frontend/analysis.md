# Frontend UI & Architecture Survey Report: WiPhoto

**Author**: Frontend Architecture Explorer  
**Target Project**: WiPhoto (`C:\Users\Widlily\Documents\projects\WiPhoto`)  
**Date**: 2026-08-03  
**Status**: Comprehensive Survey Completed  

---

## 1. Existing Frontend UI Structure & Component Layout

### 1.1 Technology Stack & Architectural Paradigm
- **Framework**: Tauri v2 (`tauri` crate ^2.0, `@tauri-apps/cli` ^2) with pure **Vanilla HTML5 + ES6 JavaScript**.
- **Module Architecture**: Modular **IIFE (Immediately Invoked Function Expression)** design. No frontend bundler (Vite/Webpack) is used. Script files are loaded sequentially via `<script>` tags at the bottom of `src/index.html`.
- **Global Namespace Export**: Modules expose singleton objects on `window` (e.g., `window.App`, `window.Gallery`, `window.VirtualGrid`, `window.Editor`, `window.Viewer`, `window.Sidebar`, `window.Utils`, `window.API`).
- **Styling Architecture**: Custom CSS under `src/styles/` following the *Refined Minimal* design paradigm (`variables.css`, `main.css`, `components.css`, `sidebar.css`, `gallery.css`, `editor.css`, `crop.css`, `commandpalette.css`, `map.css`).

### 1.2 Layout & DOM Tree Mapping (`src/index.html`)
The application interface consists of screens, a 3-column main view, action overlays, and modals:

1. **`#welcome-screen` (`.screen.active`)**: Initial folder selection screen with recursive scanning checkbox, logo SVG, and scan progress bar.
2. **`#main-app` (`.screen`)**:
   - **`#toolbar` (`.toolbar`)**:
     - View mode toggle buttons (`.view-modes`): `gallery`, `map`, `timeline`.
     - Search input (`#search-input`), sort selector (`#sort-select`), zoom slider (`#zoom-slider`), slideshow button (`#btn-slideshow`), settings button (`#btn-settings`).
   - **`#main-content` (`.main-content`)**: 3-column flex container:
     - **`#left-sidebar` (`.sidebar.left-sidebar`)**: Filter buttons (`all`, `best`, `duplicates`, `picked`, `rejected`), Folder tree (`#folder-tree`), Smart collections (`#smart-collections`), Global tags (`#global-tags-list`), Statistics (`#stats-content`).
     - **`#center-area` (`.center-area`)**: View switcher targets:
       - `#view-gallery`: Grid container `#gallery-grid` managed by `VirtualGrid` + `#gallery-empty`.
       - `#view-map`: Leaflet map container (`#map-container`).
       - `#view-timeline`: Grouped timeline view (`#timeline-container`).
       - `#view-editor`: Canvas area `#editor-canvas` (image, crop overlay box) + adjustment controls sidebar `#editor-controls` (sliders for light, color, detail, effects, preset buttons, history list).
       - `#fullscreen-viewer`: Fullscreen Loupe viewer (`#viewer-image`, `#viewer-video`, zoom controls, `#viewer-info-overlay` containing `#viewer-exif` and `#viewer-histogram`).
     - **`#right-sidebar` (`.sidebar.right-sidebar`)**: `#preview-area` (selected photo preview), `#histogram-canvas` (280x100 2D canvas), `#color-palette`, `#metadata-table`, `#ai-info`, `#image-tags-list`.
   - **`#contextual-bar` (`.contextual-bar.hidden`)**: Selection bar showing count, action buttons (`btn-keep-best`, `btn-compare`, `btn-copy`, `btn-move`, `btn-delete`).
   - **`#statusbar` (`.statusbar`)**: Status text indicator at screen bottom.
3. **Modals**: `#modal-settings`, `#modal-about`, `#modal-duplicates`, `#modal-batch-rename`, `#modal-batch-export`, `#modal-trash`, `#modal-updater`, `#command-palette`, `#context-menu`, `#slideshow-overlay`.

---

## 2. Requirements Audit & Gap Analysis

### 2.1 Requirement R2: Pro Workflow UI

| Component / Sub-feature | Existing Status in Codebase | Implementation Gaps & Missing Elements |
|---|---|---|
| **Split View / Compare Mode** | Missing (`#btn-compare` currently opens `#modal-duplicates`). | - No `#view-compare` or split pane view in `#center-area`.<br>- No `SplitView` state manager module (`src/js/compare.js` or `src/js/splitview.js`).<br>- No dual canvas container with side-by-side or top-bottom photo layout, synchronized pan/zoom controls, or slider boundary divider. |
| **Filmstrip View in Loupe Mode** | Missing (Fullscreen Viewer & Editor display single images with previous/next arrow buttons). | - No horizontal filmstrip UI (`.filmstrip-container`) in `#fullscreen-viewer` or `#view-editor`.<br>- No thumbnail sequence renderer with active item highlighting, scroll-into-view behavior, and click handlers to instantly change active photo in Loupe mode. |
| **Live RGB & Luminance Histograms** | Partial / Delayed (Sidebar `#histogram-canvas` & Viewer `#viewer-histogram` use 150ms debounced 2D canvas drawing). | - No real-time histogram calculation during WebGPU adjustment slider movements.<br>- No dedicated channel selector (RGB, R, G, B, Luminance overlay) with smooth 60fps update loop. |

### 2.2 Requirement R3: WebGPU & Web Workers

| Component / Sub-feature | Existing Status in Codebase | Implementation Gaps & Missing Elements |
|---|---|---|
| **WebGPU Renderer for Adjustments** | Missing (`editor.js` currently relies on Rust backend `API.applyEdit()` round-trips for every slider change). | - No WebGPU pipeline file (`src/js/webgpu_renderer.js`).<br>- No WGSL shader code (`src/js/shaders/adjustments.wgsl` or inline WGSL string) for non-destructive exposure, contrast, and HSL adjustments.<br>- No WebGPU canvas fallback for environments lacking WebGPU support. |
| **Web Worker Offloading for Virtual Grid & Sorting** | Missing (All sorting, filtering, and VirtualGrid row calculations run synchronously on the main UI thread). | - No Web Worker script file (`src/js/workers/grid_worker.js`).<br>- No message protocol (`SET_DATA`, `SORT_AND_FILTER`, `CALCULATE_VIRTUAL_RANGE`).<br>- Main thread scroll performance currently fails stress limits (586ms render for 10k items, 25.98ms scroll frame time). |

---

## 3. Recommended File Locations & Architecture Contracts

To maintain alignment with `PROJECT.md` conventions and the existing IIFE module structure, the following file structure and contract designs are recommended:

### 3.1 Proposed New Source Files
```
src/
├── js/
│   ├── splitview.js         # Split View / Compare Mode state manager & UI controller
│   ├── filmstrip.js         # Horizontal thumbnail filmstrip component for Loupe/Editor
│   ├── histogram.js         # Unified Live RGB & Luminance histogram renderer
│   ├── webgpu_renderer.js   # WebGPU non-destructive image adjustment pipeline
│   ├── workers/
│   │   └── grid_worker.js   # Web Worker for catalog sorting, filtering, and VirtualGrid math
│   ├── splitview.test.cjs   # Unit & Integration tests for Split View state manager
│   └── grid_worker.test.cjs # Unit & Integration tests for Web Worker message protocol
└── styles/
    ├── compare.css          # Styling for Split View / Compare Mode interface
    ├── filmstrip.css        # Styling for Filmstrip container & thumbnails
    └── webgpu.css           # Canvas overlay styling for WebGPU editor view
```

### 3.2 Key Contracts & Module APIs

#### `SplitView` (`src/js/splitview.js`)
```javascript
const SplitView = (() => {
  function init() { ... }
  function open(imageA, imageB) { ... }
  function close() { ... }
  function setMode(mode) { /* 'side-by-side' | 'slider-compare' | 'top-bottom' */ }
  function syncPanZoom(panX, panY, zoomScale) { ... }
  function getSelectedPair() { return { left: imageA, right: imageB }; }
  return { init, open, close, setMode, syncPanZoom, getSelectedPair };
})();
```

#### `WebGPURenderer` (`src/js/webgpu_renderer.js`)
```javascript
const WebGPURenderer = (() => {
  async function isSupported() { return !!navigator.gpu; }
  async function init(canvasElement) { ... }
  async function loadImage(imageSource) { ... }
  function render(adjustments) { /* adjustments: { exposure, contrast, hue, saturation, lightness, ... } */ }
  function getHistogramData() { /* returns Uint32Array arrays for R, G, B, Luminance */ }
  return { isSupported, init, loadImage, render, getHistogramData };
})();
```

#### `GridWorkerProtocol` (`src/js/workers/grid_worker.js`)
```javascript
// Message types passed via self.postMessage / self.onmessage
// 1. { type: 'SET_CATALOG', payload: { images: [...] } }
// 2. { type: 'SORT_AND_FILTER', payload: { filter, sort, query, folder, tag } } -> Response: { type: 'FILTERED_INDICES', indices: [...] }
// 3. { type: 'COMPUTE_VIRTUAL_LAYOUT', payload: { scrollTop, viewportHeight, thumbSize, totalItems } } -> Response: { type: 'LAYOUT_BOUNDS', startRow, endRow, startIndex, endIndex }
```

---

## 4. Testing Setup & Harness Survey (`npm run test`)

### 4.1 Test Infrastructure Overview
- **Test Command**: `npm run test` executes `node --test src/js/*.test.cjs`.
- **Harness Mechanism**: Tests use Node's native `node:test` runner, `node:assert`, and `node:vm` context execution to instantiate browser module code without requiring heavy DOM frameworks.
- **Current Test Files**:
  - `src/js/utils.test.cjs`: Core utility unit tests.
  - `src/js/updater.test.cjs` & `src/js/updater_e2e.test.cjs`: OTA updater logic and state machine.
  - `src/js/tier1_tier2_features.test.cjs`, `tier3_cross_features.test.cjs`, `tier4_e2e_scenarios.test.cjs`: Feature & scenario tests.
  - `src/js/virtualgrid_stress.test.cjs`: VirtualGrid stress benchmark.
  - `src/js/spatial_stress.test.cjs`: Map clustering stress benchmark.

### 4.2 Benchmark Baseline Results
Running `npm test` yields:
- **Total Tests**: 109 tests across 46 suites.
- **Passed**: 106 tests.
- **Failed**: 3 stress benchmark tests:
  1. `spatial_stress.test.cjs`: 10,000 points load took 4183.41ms (>3500ms limit).
  2. `virtualgrid_stress.test.cjs`: Initial render of 10,000 items took 586.03ms (>200ms limit).
  3. `virtualgrid_stress.test.cjs`: Scroll frame duration took 25.98ms (>16.6ms budget).

*Conclusion*: Offloading VirtualGrid calculations and array sorting to `src/js/workers/grid_worker.js` (R3 requirement) is essential to resolving the VirtualGrid main thread bottlenecks and achieving 60fps performance.

### 4.3 Proposed Test Suites for Requirements R2 & R3
To satisfy the project Acceptance Criteria ("Node.js tests `npm run test` must verify the logic of the Web Worker message passing and the Split View state manager"):
1. **`src/js/splitview.test.cjs`**:
   - Verify selection of dual photos for comparison.
   - Verify view mode switching (`side-by-side`, `top-bottom`, `slider-compare`).
   - Verify zoom/pan synchronization state calculations.
   - Verify clean reset upon closing compare view.
2. **`src/js/grid_worker.test.cjs`**:
   - Verify catalog array serialization and message handling.
   - Verify worker-side multi-criteria sorting (by name, date, size, camera, rating).
   - Verify filtering logic (picked, rejected, RAW, video, tags, folders).
   - Verify virtual grid row/column index slicing.

---

## 5. Sequential Implementation Roadmap Recommendations

1. **Phase 1: Web Worker Offloading for Virtual Grid & Sorting (R3)**
   - Create `src/js/workers/grid_worker.js`.
   - Update `src/js/virtualgrid.js` and `src/js/gallery.js` to dispatch sorting and layout calculations to the worker.
   - Create `src/js/grid_worker.test.cjs` and verify main thread scroll benchmark improvements.

2. **Phase 2: Pro Workflow UI — Split View & Filmstrip (R2)**
   - Add `#view-compare` and `.filmstrip-container` HTML structures to `src/index.html`.
   - Create `src/js/splitview.js`, `src/js/filmstrip.js`, `src/styles/compare.css`, and `src/styles/filmstrip.css`.
   - Wire `#btn-compare` in contextual bar and toolbar to launch Split View mode.
   - Attach filmstrip to Fullscreen Viewer (`viewer.js`) and Editor (`editor.js`).
   - Write unit tests in `src/js/splitview.test.cjs`.

3. **Phase 3: WebGPU Renderer & Live Histograms (R3 & R2)**
   - Create `src/js/webgpu_renderer.js` and `src/js/histogram.js`.
   - Implement WGSL shaders for exposure, contrast, and HSL adjustments with Canvas2D fallback.
   - Connect slider inputs in `editor.js` to real-time WebGPU canvas rendering and live histogram calculation.

4. **Phase 4: Full Suite Verification**
   - Run `npm test` to ensure 100% test passage across unit, integration, and worker test harnesses.
