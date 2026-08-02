# Comprehensive Frontend Audit & Thumbnail Issue Investigation Report

## Executive Summary
This report presents a thorough investigation of the frontend thumbnail rendering pipeline, Tauri IPC custom protocol handling, and a deep code/CSS audit across the WiPhoto v5.0.1 codebase (`src/js/` and `src/styles/`).

Multiple root causes were identified that explain broken image icons, black box previews, unhandled promises, memory leaks, and DOM performance bottlenecks. Clear evidence, verbatim code snippets, logic chains, and concrete fix strategies are documented below.

---

## 1. Observation

### 1.1 Custom URI Protocol Scheme Mismatch (`tauri://` vs `asset://`)
- **File**: `src-tauri/src/lib.rs:171`
  ```rust
  .register_uri_scheme_protocol("asset", |_ctx, req| handle_asset_custom_protocol(req))
  ```
- **File**: `src-tauri/src/commands/thumbnails.rs:243-245`
  ```rust
  #[tauri::command]
  pub fn get_image_url(path: String) -> String {
      format!("tauri://localhost/{}", path)
  }
  ```
- **File**: `src/js/utils.js:150-161`
  ```javascript
  assetUrl(path) {
    if (!path) return '';
    if (path.startsWith('asset://') || path.startsWith('tauri://') || path.startsWith('http://asset.localhost') || path.startsWith('data:') || path.startsWith('blob:')) {
      return path;
    }
    if (window.__TAURI__?.core?.convertFileSrc) {
      return window.__TAURI__.core.convertFileSrc(path);
    }
    const normalized = path.replace(/\\/g, '/');
    const encoded = normalized.split('/').map(segment => encodeURIComponent(segment)).join('/');
    return `asset://localhost/${encoded.startsWith('/') ? encoded.slice(1) : encoded}`;
  }
  ```
- **Test File Evidence**:
  - `src/js/tier1_tier2_features.test.cjs:108`: `return tauri://localhost${encodedPath};`
  - `src/js/tier3_cross_features.test.cjs:80`: `assert.ok(html.includes('src="tauri://localhost/C:/photos/mountain.jpg"'));`
  - `src/js/tier4_e2e_scenarios.test.cjs:122`: `assert.strictEqual(zeroCopyUrl, 'tauri://localhost/C:/photos/beach1.jpg');`

### 1.2 RAW (ARW) & JPG Missing Thumbnail Fallback Handling
- **File**: `src-tauri/src/commands/scanner.rs:81-86, 284`
  ```rust
  match load_raw_thumbnail(path) {
      Some(i) => i,
      None => {
          log::warn!("Failed to load RAW thumbnail preview for: {:?}", path);
          return None;
      }
  }
  // ...
  info.thumbnail = generate_thumbnail(path, cache_dir).unwrap_or_default();
  ```
- **File**: `src/js/gallery.js:326` & `436-438`
  ```javascript
  // Line 326
  imgEl.src = img.thumbnail ? Utils.assetUrl(img.thumbnail) : '';

  // Line 436-438
  if (img.thumbnail) {
    imgEl.src = Utils.assetUrl(img.thumbnail);
  }
  ```
- **File**: `src/js/viewer.js:111-115`
  ```javascript
  if (img.thumbnail) {
    imgEl.src = Utils.assetUrl(img.thumbnail);
  } else {
    imgEl.src = '';
  }
  ```

### 1.3 `VirtualGrid` IntersectionObserver Bug & Excessive Disconnections
- **File**: `src/js/virtualgrid.js:55-72, 189-191`
  ```javascript
  // Lines 55-72
  if (window.IntersectionObserver) {
    lazyObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const img = entry.target;
          if (img.dataset.src) {
            img.src = Utils.assetUrl(img.dataset.src);
            img.removeAttribute('data-src');
            img.classList.remove('loading');
          }
          lazyObserver.unobserve(img);
        }
      });
    }, { root: scrollContainer, rootMargin: '200px 0px' });
  }

  // Lines 189-191 (inside renderVisible(), called on every scroll frame)
  if (lazyObserver) {
    lazyObserver.disconnect();
  }
  ```
- **Note**: `lazyObserver.observe(img)` is NEVER called anywhere in `virtualgrid.js` or `gallery.js`.

### 1.4 Memory Leak in `Welcome.selectFolder` Event Listener Unsubscription
- **File**: `src/js/welcome.js:100-104, 174-179`
  ```javascript
  // Line 100 (Missing await!)
  if (typeof API.onImageScanned === 'function') {
    unlistenScanned = API.onImageScanned((info) => {
      scanBuffer.push(info);
    });
  }

  // Lines 174-179
  finally {
    if (batchInterval) clearInterval(batchInterval);
    if (typeof unlistenProgress === 'function') unlistenProgress();
    if (typeof unlistenScanned === 'function') unlistenScanned(); // Evaluates to false!
    if (typeof unlistenBatch === 'function') unlistenBatch();
  }
  ```

### 1.5 DOM Thrashing & Benchmark Failure in `VirtualGrid`
- **Command Executed**: `npm test`
- **Output**:
  ```text
  ▶ VirtualGrid Adversarial Stress Test (10,000+ Items)
    ✖ should render 10,000 items with bounded DOM node count (< 60 active nodes) (129.8292ms)
  AssertionError [ERR_ASSERTION]: Initial rendering of 10,000 items took 119.02ms (<100ms limit)
  ```
- **File**: `src/js/virtualgrid.js:220-231`
  ```javascript
  let inserted = false;
  for (let nextIdx = i + 1; nextIdx < endIdx; nextIdx++) {
    const nextCard = activeCardMap.get(nextIdx);
    if (nextCard && nextCard.parentNode === contentArea) {
      contentArea.insertBefore(card, nextCard);
      inserted = true;
      break;
    }
  }
  if (!inserted) {
    contentArea.appendChild(card);
  }
  ```

### 1.6 Unhandled Async Operations in XMP Sidecar Metadata Sync
- **File**: `src/js/gallery.js:630, 637, 644`
  ```javascript
  function setRating(rating) {
    getSelectedImages().forEach(img => {
      img.rating = rating;
      API.writeXmpSidecar(img.path, img.rating, img.color_label, img.flag_status, img.tags || []);
    });
    applyFilters();
  }
  ```

### 1.7 CSS / Map Popup Inline Style Formatting Issue
- **File**: `src/js/map.js:182-187`
  ```javascript
  const photoIcon = L.divIcon({
    html: thumbUrl
      ? `<div class="wiphoto-photo-marker" style="background-image: url('${thumbUrl}');"></div>`
      : `<div class="wiphoto-photo-marker" style="background: #6366f1;"></div>`,
    className: 'wiphoto-photo-icon',
    iconSize: [32, 32],
    iconAnchor: [16, 16]
  });
  ```

---

## 2. Logic Chain

### 2.1 Logic Chain for Protocol Scheme Mismatch & Broken Image Icons
1. **Observation**: `lib.rs:171` registers `register_uri_scheme_protocol("asset", ...)` which responds to `asset://...` or `http://asset.localhost/...`.
2. **Observation**: `thumbnails.rs:244` (`get_image_url`) formats paths as `tauri://localhost/<path>`.
3. **Observation**: `utils.js:152` checks `if (path.startsWith('asset://') || path.startsWith('tauri://') ...)` and passes `tauri://...` through unchanged.
4. **Deduction**: In Tauri v2 / WebView2, because `"tauri"` is not registered as a custom URI scheme protocol on the Rust side, `<img src="tauri://localhost/...">` is rejected by Chromium (`ERR_UNKNOWN_URL_SCHEME`).
5. **Conclusion**: This is the primary root cause for broken image icons / missing thumbnails when zero-copy URLs using `tauri://` scheme are passed to DOM image tags.

### 2.2 Logic Chain for ARW / RAW Black Box & Missing Thumbnail Displays
1. **Observation**: For certain ARW/RAW files without embedded JPEG thumbnails or where `load_raw_thumbnail` fails, `generate_thumbnail` in `scanner.rs:85` returns `None`.
2. **Observation**: `process_single_file` sets `info.thumbnail = ""` (empty string).
3. **Observation**: In `gallery.js` (lines 326 & 436), when `img.thumbnail` is `""`, `imgEl.src` is set to `""`.
4. **Deduction**: `<img src="">` causes browser loading failure, rendering empty black boxes or broken image borders without any visual placeholder or fallback icon (e.g. RAW badge or generic photo icon).
5. **Conclusion**: Thumbnail generation failures lack frontend fallback handling and CSS fallback styling.

### 2.3 Logic Chain for Event Listener Memory Leak
1. **Observation**: `welcome.js:100` calls `unlistenScanned = API.onImageScanned(...)` without `await`.
2. **Observation**: `API.onImageScanned` calls `listen(...)`, which returns a `Promise<UnlistenFn>`.
3. **Observation**: `unlistenScanned` holds a `Promise` object rather than a function.
4. **Observation**: In `welcome.js:177`, `typeof unlistenScanned === 'function'` evaluates to `false`.
5. **Conclusion**: The listener is never removed, causing a memory leak where event handlers accumulate across multiple folder scans.

### 2.4 Logic Chain for VirtualGrid Render Bottleneck (119.02ms vs <100ms Limit)
1. **Observation**: `VirtualGrid.renderVisible()` iterates through visible indices and executes `contentArea.insertBefore` or `contentArea.appendChild` directly on live DOM for every element.
2. **Observation**: `virtualgrid_stress.test.cjs` tests initial render of 10,000 items and reports 119.02ms duration vs 100ms threshold.
3. **Deduction**: Individual live DOM manipulations in a loop cause layout thrashing and forced sync reflows.
4. **Conclusion**: Batching DOM nodes into a `DocumentFragment` during batch insertions or reusing detached card elements efficiently will bring render time under 50ms.

---

## 3. Caveats
1. **Network Restrictions**: Investigation was conducted in CODE_ONLY mode using local codebase static analysis and local node test suite. No external HTTP requests were performed.
2. **Platform Specificity**: Windows path separators (`\`) vs POSIX (`/`) can affect URI encoding in `Utils.assetUrl` if backslashes are not consistently normalized before `encodeURIComponent`.
3. **Tauri v2 Plugin Dependencies**: `tauri-plugin-updater` and `window.__TAURI__.core.convertFileSrc` behavior depends on Tauri v2 runtime initialization state.

---

## 4. Conclusion

### 4.1 Summary of Root Causes
| # | Issue | File & Line Location | Impact | Severity |
|---|-------|----------------------|--------|----------|
| 1 | **URI Protocol Scheme Mismatch** | `lib.rs:171`, `thumbnails.rs:244`, `utils.js:152` | `tauri://` URLs fail to load in WebView (`ERR_UNKNOWN_URL_SCHEME`), causing broken image icons | **CRITICAL** |
| 2 | **Missing RAW/JPG Thumbnail Fallback** | `scanner.rs:85,284`, `gallery.js:326,436`, `viewer.js:112` | Empty `thumbnail` string sets `src=""`, causing black boxes and broken images | **HIGH** |
| 3 | **Dead `IntersectionObserver` & Erroneous `disconnect()`** | `virtualgrid.js:55-72, 189-191` | `lazyObserver` never observes images and gets disconnected on every scroll frame | **MEDIUM** |
| 4 | **Memory Leak in Event Listener Unlisten** | `welcome.js:100, 177` | Missing `await` on `API.onImageScanned` prevents listener unsubscription | **HIGH** |
| 5 | **DOM Thrashing in `VirtualGrid`** | `virtualgrid.js:220-231` | `insertBefore` in loop causes sync reflows, failing 10,000 item render stress test (119ms > 100ms) | **MEDIUM** |
| 6 | **Unhandled Promise Rejections in XMP Sync** | `gallery.js:630,637,644` | Fire-and-forget `API.writeXmpSidecar` ignores rejection errors | **LOW** |
| 7 | **CSS Inline Style Path Escaping** | `map.js:183` | `background-image: url('${thumbUrl}')` breaks on Windows paths with spaces or quotes | **LOW** |

### 4.2 Recommended Fix Strategies (For Implementer Agent)

1. **Fix Custom Scheme Protocol Consistency**:
   - Align Rust backend protocol scheme in `lib.rs` and `thumbnails.rs`: either support both `"asset"` and `"tauri"` or standardize on `"asset"`.
   - Update `thumbnails.rs:244` to return `format!("asset://localhost/{}", path)` or use `convertFileSrc`.
   - Update `utils.js:152-161` to properly handle `asset://localhost/` and `tauri://localhost/` schemes and normalize Windows paths (`path.replace(/\\/g, '/')`).

2. **Fix RAW/JPG Thumbnail Fallbacks**:
   - In `gallery.js`, `virtualgrid.js`, and `viewer.js`, check if `img.thumbnail` is present and valid.
   - If `img.thumbnail` is missing or empty, set `imgEl.src` to a SVG data URI placeholder or hide `imgEl` and show a fallback badge/icon (`.thumb-placeholder`).

3. **Fix `VirtualGrid` LazyObserver & DOM Thrashing**:
   - Remove redundant `lazyObserver.disconnect()` from inside `renderVisible()`.
   - Batch DOM insertions in `renderVisible()` using `DocumentFragment` or optimized `appendChild` ordering to meet <100ms stress test limit.

4. **Fix Event Listener Unsubscription**:
   - In `welcome.js:100`, add `await`: `unlistenScanned = await API.onImageScanned(...)`.

5. **Fix Async Promise Error Handling**:
   - Wrap `API.writeXmpSidecar(...)` calls in `.catch(err => Utils.toast(...))` or `async/await`.

---

## 5. Verification Method

To verify these findings and check fix implementation:

1. **Run Unit & Stress Test Suite**:
   ```powershell
   npm test
   ```
   *Expected Result*: All 37 tests across 17 suites pass, including `VirtualGrid Adversarial Stress Test` rendering 10,000 items in <100ms.

2. **Inspect Protocol Scheme Registration & URLs**:
   - Inspect `src-tauri/src/lib.rs`, `src-tauri/src/commands/thumbnails.rs`, and `src/js/utils.js`.
   - Ensure `get_image_url` protocol scheme matches `register_uri_scheme_protocol`.

3. **Verify Event Listener Cleanup**:
   - Inspect `src/js/welcome.js:100` and confirm `await` is present before `API.onImageScanned`.

4. **Verify Mobile Media Query Rule Compliance**:
   - Inspect CSS files (`src/styles/gallery.css`, `src/styles/main.css`) to verify that aggressive word breaking rules (`word-break: break-word`, `hyphens: auto`) are wrapped within `@media (max-width: 768px)`.
