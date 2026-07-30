# Handoff Report: Frontend VirtualGrid Performance & Static Analysis Audit

## 1. Observation

### 1.1 VirtualGrid Scroll & Viewport Handling (`src/js/virtualgrid.js`)
- **Scroll Throttling without `requestAnimationFrame`**:
  - `virtualgrid.js:67`: `scrollContainer.addEventListener('scroll', Utils.throttle(onScroll, 16));`
  - `utils.js:24-30`:
    ```javascript
    throttle(fn, ms = 100) {
      let last = 0;
      return (...args) => {
        const now = Date.now();
        if (now - last >= ms) { last = now; fn(...args); }
      };
    }
    ```
  - `onScroll` runs `renderVisible()` directly inside the scroll event callback thread without scheduling DOM updates via `requestAnimationFrame` (rAF).

- **DOM Creation & Destruction without Recycling/Pooling**:
  - `virtualgrid.js:166-174`:
    ```javascript
    const fragment = document.createDocumentFragment();
    for (let i = startIdx; i < endIdx; i++) {
      const card = cardRenderer(items[i], i);
      fragment.appendChild(card);
    }
    contentArea.innerHTML = '';
    contentArea.appendChild(fragment);
    ```
  - `virtualgrid.js:188-191`: `contentArea.removeChild(contentArea.firstChild);`
  - `virtualgrid.js:197-200`: `contentArea.removeChild(contentArea.lastChild);`
  - `virtualgrid.js:205-207`: `const card = cardRenderer(items[i], i); contentArea.insertBefore(card, contentArea.firstChild);`
  - `virtualgrid.js:212-214`: `const card = cardRenderer(items[i], i); contentArea.appendChild(card);`
  - Unused DOM elements are detached and left for Garbage Collection. Newly visible cards are instantiated from scratch via `createThumbCard` (`gallery.js:294-369`).
  - `virtualgrid.js:16`: `let renderedCards = new Map(); // row -> DOM elements` is declared and cleared (`lines 93, 251`), but never populated or read.

- **IntersectionObserver Invalidation on Scroll**:
  - `virtualgrid.js:156-158`: `if (lazyObserver) { lazyObserver.disconnect(); }` disconnects lazy observer on every visible window shift. However, `createThumbCard` sets `imgEl.src = Utils.assetUrl(img.thumbnail)` directly on card creation (`gallery.js:311`), bypassing IntersectionObserver lazy loading.

### 1.2 Layout Thrashing & Forced Synchronous Reflows (`src/js/gallery.js`, `src/js/viewer.js`)
- **Forced Reflow in `updateStatusBar()` (`src/js/gallery.js:496-501`)**:
  - `gallery.js:496-501`:
    ```javascript
    const logEl = (name, el) => {
      if (!el) return `${name}=null`;
      const cs = window.getComputedStyle(el);
      return `${name}: clientH=${el.clientHeight}, compH=${cs.height}, display=${cs.display}, position=${cs.position}, flex=${cs.flex}`;
    };
    Logger.debug('Layout', `${logEl('main-app', mainApp)} | ${logEl('main-content', mainContent)} | ${logEl('center-area', centerArea)} | ${logEl('view-gallery', viewGallery)}`);
    ```
  - `updateStatusBar()` is called inside `renderGrid()` (`gallery.js:280, 291`) immediately after modifying grid layout/spacers, forcing the browser to synchronously recalculate layout across 4 container hierarchy nodes on every grid update.

- **DOM Selection Search Overhead (`src/js/gallery.js`)**:
  - `gallery.js:415`: `const card = grid().querySelector(\`[data-index="${index}"]\`);`
  - `gallery.js:439`: `grid().querySelectorAll('.thumb-card.selected').forEach(...)`
  - `gallery.js:453-455`: `selectAll()` iterates over `filteredImages` and calls `selectIndex(i)` for all items in the array (e.g. 10,000 items), executing 10,000 `querySelector` calls on the DOM tree even though only ~30 items are mounted.

- **Viewer Reflow Trigger (`src/js/viewer.js:64`)**:
  - `void imgEl.offsetWidth; // force reflow` forced layout flush to restart CSS animation transition.

### 1.3 ESLint & Static Analysis Status
- **Command Output (`npx --yes eslint src/`)**:
  ```text
  ESLint couldn't find an eslint.config.(js|mjs|cjs) file.
  From ESLint v9.0.0, the default configuration file is now eslint.config.js.
  ```
  - `package.json` contains no `"eslint"` package in `devDependencies` and no `"lint"` script in `"scripts"`.
  - No `eslint.config.js` or `.eslintrc.*` exists in the codebase.

- **Static Analysis Issues in JS Files**:
  - `utils.js:119`: In `Utils.toast()`, action button `onClick` closure references `toast.remove()`, referencing `const toast` declared on line 132 (TDZ / hoisting constraint).
  - `viewer.js:69-70`: Global document mouse listeners (`mousemove`, `mouseup`) registered permanently during `init()`, firing callbacks on every mouse movement across window.
  - `gallery.js:69-70`: Double-click handler accesses `VirtualGrid.getItemAtIndex(idx)` which returns item, but indexing uses `card.dataset.index`.
  - Radix parameter missing in multiple `parseInt(val)` calls throughout `gallery.js` and `virtualgrid.js`.

---

## 2. Logic Chain

1. **Scroll Jitter & Frame Drops**:
   - `VirtualGrid` binds scroll events via `Utils.throttle(onScroll, 16)`.
   - `Utils.throttle` checks `Date.now() - last >= 16ms`. System clock timers have a 4-15ms resolution on Windows and do not align with display refresh cycles (60Hz / 120Hz / 144Hz V-Sync).
   - `renderVisible()` performs DOM manipulations (`insertBefore`, `appendChild`, `removeChild`, updating spacer heights) synchronously during the scroll event callback without using `requestAnimationFrame`.
   - Result: Scroll updates block main thread, missing V-Sync frame boundaries and causing visible frame stuttering.

2. **Garbage Collection Jitter (Lack of DOM Recycling)**:
   - When scrolling through large galleries (10,000+ items), items entering/leaving the viewport continuously destroy old `.thumb-card` DOM nodes and instantiate new DOM subtrees with ~10 child elements (`img`, `div`, `span`s) per card via `createThumbCard`.
   - The unused state variable `renderedCards = new Map()` proves DOM pooling was intended but never implemented.
   - Result: Continuous memory allocation and element disposal trigger heavy Garbage Collection pauses during fast scrolling.

3. **Layout Thrashing (Forced Reflows)**:
   - In `renderVisible()`, `VirtualGrid` updates DOM elements and changes `spacerTop.style.height` and `spacerBottom.style.height`.
   - Right after `VirtualGrid.setItems` or `renderVisible`, `Gallery.updateStatusBar()` calls `logEl()` which queries `window.getComputedStyle(el)` and `el.clientHeight` on `main-app`, `main-content`, `center-area`, and `view-gallery`.
   - Reading layout metrics immediately after layout-invalidating DOM mutations causes forced synchronous reflows on the main thread.

4. **Selection Bottleneck (`selectAll`)**:
   - `selectAll()` iterates over `filteredImages` and calls `selectIndex(index)` for every item.
   - `selectIndex` runs `grid().querySelector('[data-index="${index}"]')`.
   - For a 10,000-image dataset, `selectAll` executes 10,000 DOM query searches, 9,970 of which fail because only ~30 cards exist in the DOM.

---

## 3. Caveats

- **GPU Capabilities**: Tests were analyzed statically; actual frame rates depend on display refresh rates and hardware GPU rasterization in Tauri webview (Edge WebView2 on Windows).
- **Dataset Size**: Bottlenecks like `selectAll` scale linearly $O(N)$ with dataset size $N$; performance impact is moderate at $N=100$ but critical at $N=10,000+$.
- **Backend I/O**: Thumbnail loading speed over `asset://` custom protocol is handled by Tauri backend; frontend scroll smoothness requires zero main-thread blockage regardless of image resolution.

---

## 4. Conclusion

The current `VirtualGrid` implementation successfully calculates visible item ranges, but suffers from three primary performance bottlenecks:
1. Synchronous, un-batched DOM mutations inside `Date.now()` throttled scroll handlers.
2. Complete absence of DOM element recycling (creating/destroying DOM trees on every row step).
3. Forced synchronous reflows (Layout Thrashing) in status bar debug logging and un-indexed DOM selection queries ($O(N)$ `querySelector`).

Removing debug layout reads, decoupling scroll reads from DOM writes via `requestAnimationFrame`, introducing a DOM Node Recycling Pool for `.thumb-card` elements, and maintaining an $O(1)$ index map for active DOM cards will achieve locked 60fps scrolling and instant multi-item selection.

---

## 5. Verification Method

### 5.1 Static Verification Commands
- Check ESLint configuration and run linter:
  ```powershell
  npx eslint src/
  ```
  *(Invalidation condition: output fails with "ESLint couldn't find an eslint.config file")*

- Run existing JS unit test suite:
  ```powershell
  npm test
  ```

### 5.2 Performance & Inspection Audit
1. **Scroll Handler Inspection**:
   - Inspect `src/js/virtualgrid.js` around line 67 to verify `requestAnimationFrame` wrap and scroll debouncing/throttling lock.
2. **Layout Thrashing Inspection**:
   - Inspect `src/js/gallery.js:496-501` to ensure `window.getComputedStyle` and `el.clientHeight` layout logging during status updates has been removed.
3. **DOM Node Pool Inspection**:
   - Verify `VirtualGrid` maintains an active pool / cache of `.thumb-card` elements and reuses detached cards via property updates instead of calling `document.createElement` inside scroll loops.
4. **Selection O(1) Lookup Inspection**:
   - Inspect `selectIndex` and `selectAll` in `src/js/gallery.js` to verify cards are updated via direct Map reference (`renderedCardsMap.get(index)`) without calling `grid().querySelector`.

---

## 6. Actionable Implementation Plan for Implementer

### Step 1: Fix ESLint Setup & Linter Configuration
- Create `eslint.config.js` in project root using ESLint v9+ flat config syntax for browser ES modules (`env: browser, es2022`).
- Add `"eslint": "^9.0.0"` to `package.json` devDependencies and add `"lint": "eslint src/"` to `scripts`.

### Step 2: Implement rAF-Synchronized Scroll Engine in `VirtualGrid`
- Modify `src/js/virtualgrid.js`:
  - Replace `Utils.throttle(onScroll, 16)` with a `requestAnimationFrame` frame lock:
    ```javascript
    let ticking = false;
    function onScroll() {
      if (!ticking && isActive) {
        requestAnimationFrame(() => {
          renderVisible();
          ticking = false;
        });
        ticking = true;
      }
    }
    scrollContainer.addEventListener('scroll', onScroll, { passive: true });
    ```

### Step 3: Eliminate Layout Thrashing & Debug Reflows
- In `src/js/gallery.js`:
  - Remove layout measurements (`getComputedStyle`, `clientHeight`) from `updateStatusBar()` (`lines 496-501`).
- In `src/js/virtualgrid.js`:
  - Cache container dimensions (`scrollContainer.clientWidth`, `clientHeight`) during `ResizeObserver` callbacks rather than measuring layout properties inside `onScroll` / `renderVisible`.

### Step 4: Implement DOM Card Recycling Pool & O(1) Selection
- In `src/js/virtualgrid.js`:
  - Maintain a pool of unused `.thumb-card` DOM nodes (`cardPool: HTMLElement[]`).
  - Maintain a map of active rendered nodes (`activeCardMap: Map<index, HTMLElement>`).
  - When a card scrolls out of view: detach it from `contentArea` and push it to `cardPool`.
  - When a card scrolls into view: pop a card from `cardPool` (or create one if pool is empty) and update its attributes (`data-path`, `data-index`, `img.src`, badges) via an `updateThumbCard(card, item, index)` helper function.
- In `src/js/gallery.js`:
  - Update `selectIndex(index)` to query `VirtualGrid.getRenderedCard(index)` in $O(1)$ instead of calling `grid().querySelector('[data-index="..."]')`.
  - Update `selectAll()` to mark selection state in `selectedIndices` Set and update only visible cards currently rendered in the DOM.
