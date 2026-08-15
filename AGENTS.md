# WiPhoto Engineering Rules & Architectural Invariants

## 1. Tauri v2 Protocol & Asset Handling
- **Never hijack reserved Tauri schemes:** Do NOT register custom URI schemes for `"tauri"`, `"http"`, or `"https"` via `.register_uri_scheme_protocol()`. In Tauri v2, overriding `"tauri"` intercepts `tauri://localhost` and breaks the webview asset bundle, resulting in 404 "Not Found" on startup.
- **Dedicated Custom Protocol:** For zero-copy local filesystem media streaming, always register a dedicated unique scheme (e.g. `asset://localhost/...` via `.register_uri_scheme_protocol("asset", ...)`).

## 2. Windows File System Atomic Operations
- **Target Collision Handling:** On Windows, `std::fs::rename(from, to)` fails with OS Error 183 (`ERROR_ALREADY_EXISTS`) if `to` exists.
- **Resilient Atomic Save Pattern:**
  1. Remove target file if it already exists before calling `std::fs::rename`.
  2. Implement fallback to `std::fs::copy(temp, target)` + `std::fs::remove_file(temp)` in case of cross-device links or filesystem lock retries.

## 3. Media Pipeline & Thumbnail Resilience
- **Multi-tiered Thumbnail Loading:**
  1. **Tier 1 (Cached Thumbnail):** Use `Utils.assetUrl(img.thumbnail)` if path is valid.
  2. **Tier 2 (Zero-Copy Fallback):** For standard image formats (JPEG, PNG, WebP, AVIF, TIFF, BMP, JXL), instantly fallback to `Utils.assetUrl(img.path)` if thumbnail is absent or failing.
  3. **Tier 3 (On-Demand Asynchronous Fetch):** For RAW images and videos without cached thumbnails, show a type-specific placeholder and trigger `API.getThumbnail(img.path)` asynchronously to generate and inject the thumbnail without blocking UI.
  4. **Tier 4 (Self-Healing Storage):** When reading cached records from SQLite during folder scan, verify physical existence of `.jpg` thumbnail files on disk and automatically regenerate missing thumbnails.

## 4. OTA Updater Integration & Linter Invariants
- **UI Exposure:** Always expose manual update triggers in Settings, About modal, and Command Palette (`Ctrl+K`).
- **Silent Background Checks:** Run non-blocking update checks shortly after startup to proactively notify users of new releases.
- **Global Definitions:** Keep `eslint.config.js` globals in sync whenever exposing window-level APIs (`UpdaterAPI`, `showUpdateModal`, `initUpdaterUI`).
