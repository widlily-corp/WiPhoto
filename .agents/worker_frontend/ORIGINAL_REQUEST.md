## 2026-07-30T14:34:38Z
You are worker_frontend (teamwork_preview_worker).
Your working directory is: c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_frontend
Project root: c:\Users\Widlily\Documents\projects\wiphoto
Project spec: c:\Users\Widlily\Documents\projects\wiphoto\.agents\orchestrator_v3\PROJECT.md
Frontend handoff report: c:\Users\Widlily\Documents\projects\wiphoto\.agents\explorer_frontend\handoff.md
Stability handoff report: c:\Users\Widlily\Documents\projects\wiphoto\.agents\explorer_stability\handoff.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Tasks:
1. Initialize your working directory `.agents/worker_frontend` with `BRIEFING.md` and `progress.md`.
2. Refactor `VirtualGrid` (`src/js/virtualgrid.js`):
   - Replace `Utils.throttle(onScroll, 16)` with a `requestAnimationFrame` frame lock & passive listener:
     `scrollContainer.addEventListener('scroll', onScroll, { passive: true });`
   - Implement DOM Card Recycling Pool (`cardPool: []`) and active cards Map (`activeCardMap: Map<index, card>`) so `.thumb-card` DOM nodes are recycled instead of continuously created and destroyed during scroll.
   - Cache container dimensions (`scrollContainer.clientWidth`, `clientHeight`) during `ResizeObserver` callbacks rather than measuring layout properties during `onScroll`.
3. Refactor `Gallery` (`src/js/gallery.js`):
   - Remove forced synchronous reflows / layout reads (`window.getComputedStyle`, `el.clientHeight`) from `updateStatusBar()` (lines 496-501).
   - Change selection tracking from numeric array indices (`selectedIndices = new Set()`) to file paths (`selectedPaths = new Set()`) so sorting/filtering does not corrupt selection state.
   - Do NOT clear selection (`selectedPaths.clear()`) during `addImageBatch` background scan updates.
   - Use direct map lookup for active cards instead of `grid().querySelector('[data-index="..."]')`.
4. Refactor `Search` (`src/js/search.js`):
   - Fix search clear data loss: ensure CLIP search results do NOT overwrite `Gallery.allImages`.
5. Fix IPC Event listener (`src/js/api.js` & `src/js/welcome.js`):
   - Update `API.onImageScanned` to listen for `"image-scanned-batch"` array payload and handle progressive loading properly.
6. Setup ESLint v9 Flat Config & Package:
   - Create `eslint.config.js` in root for browser ES modules (`env: browser, es2022`).
   - Add `"eslint": "^9.0.0"` to `package.json` devDependencies and `"lint": "npx eslint src/"` to `"scripts"`.
7. Verification:
   - Run `npx eslint src/` (must return 0 errors).
   - Run `npm test` (all unit tests must pass).
8. Create handoff report `c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_frontend\handoff.md` documenting code changes, build/test results, and send completion message to parent.
