# WiPhoto OTA Auto-Updater & Architecture Analysis Report

## Executive Summary

This report presents a thorough investigation of the **WiPhoto v5.0.9** codebase (`C:\Users\Widlily\Documents\projects\wiphoto`). The application is a high-performance desktop photo manager built with **Tauri 2** (Rust backend + Vanilla HTML5/JS frontend). The goal of this investigation is to analyze the existing OTA (Over-The-Air) updater infrastructure, UI framework, event model, and test runners, and provide concrete technical recommendations for implementing **R1: Graceful Error Handling** and **R2: Visual Progress Indicator** during OTA updates.

---

## 1. Tech Stack Overview

| Category | Component / Library | Version / Details | File Reference |
|---|---|---|---|
| **App Framework** | Tauri Desktop Core | `v2.0` (`@tauri-apps/cli ^2`, `tauri 2.0`) | `package.json`, `src-tauri/Cargo.toml` |
| **Backend Core** | Rust (Edition 2021) | `wiphoto_lib` staticlib / cdylib | `src-tauri/Cargo.toml`, `src-tauri/src/lib.rs` |
| **Plugins** | Tauri Plugins | `tauri-plugin-updater 2`, `tauri-plugin-process 2`, `tauri-plugin-fs 2`, `tauri-plugin-dialog 2`, `tauri-plugin-shell 2`, `tauri-plugin-opener 2` | `src-tauri/Cargo.toml:17-22`, `src-tauri/src/lib.rs:283-288` |
| **Frontend Framework** | Plain HTML5 & Modern ES JavaScript | No Webpack/Vite bundler needed (`npm run dev` serves `src/` on `localhost:1420`). `withGlobalTauri: true`. | `package.json:8-9`, `src-tauri/tauri.conf.json:7-12` |
| **UI Styling** | Custom CSS3 System | Refined Minimal aesthetic (`variables.css`, `main.css`, `components.css`). | `src/styles/` |
| **State & Events** | Module Pattern & DOM Custom Events | `App` state controller, `Gallery`, `Editor`, `Settings`, `UpdaterAPI`. `window.__TAURI__.event` & IPC. | `src/js/app.js`, `src/js/updater.js` |
| **JS Test Runner** | Node.js Test Runner | `node --test src/js/*.test.cjs` executing tests in Node VM contexts with AAA pattern. | `package.json:11`, `src/js/*.test.cjs` |
| **Rust Test Runner** | Cargo Test | `cargo test --manifest-path src-tauri/Cargo.toml` (20 unit tests + 4 integration tests). | `TEST_READY.md`, `src-tauri/src/lib.rs:345` |

---

## 2. Existing OTA Updater Implementation

### 2.1 Configuration
- **Updater Endpoint**: `https://github.com/widlily-corp/WiPhoto/releases/latest/download/latest.json`
- **Minisign Public Key**: `dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IENCM0M3NzA1RDhCOTA4MDYKUldRR0NMbllCWGM4eTZxMzZrekcrdnJWbDkvQUViWFkwL2tCY2xnckdXemlUZDZkamNnVVcySUcK`
- **Tauri Plugin Registration**: `lib.rs:288` (`.plugin(tauri_plugin_updater::Builder::new().build())`) and `lib.rs:287` (`.plugin(tauri_plugin_process::init())`).

### 2.2 JavaScript OTA Module (`src/js/updater.js`)
- `isNewerVersion(currentVersion, targetVersion)` (`updater.js:9-22`): Semver comparison supporting `v` prefixes.
- `renderMarkdown(markdown)` (`updater.js:30-102`): Sanitizing markdown renderer for release notes (HTML entity escaping prevents XSS).
- `parseReleaseNotes(payload)` (`updater.js:109-119`): Normalizes raw updater payload into `{ available, version, date, body }`.
- `UpdaterAPI` (`updater.js:123-209`):
  - `checkForUpdates()`: Calls `window.__TAURI__.updater.check()` or fallback IPC `plugin:updater|check`.
  - `installUpdate(updateObj, onProgress)`: Calls `targetObj.downloadAndInstall(onProgress)` or fallback IPC `plugin:updater|download_and_install`.
  - `relaunchApp()`: Calls `window.__TAURI__.process.relaunch()` or fallback IPC `plugin:process|relaunch`.
- `showUpdateModal(updateInfo)` (`updater.js:215-239`) & `hideUpdateModal()` (`updater.js:244-249`).
- `initUpdaterUI()` (`updater.js:254-302`): Initializes click listeners on `#btn-updater-install` ("Обновить сейчас") and `#btn-updater-postpone` ("Отложить").

### 2.3 Existing Gaps & Weaknesses
1. **Lack of Visual Progress Feedback**:
   - `initUpdaterUI()` (`updater.js:270`) currently calls `UpdaterAPI.installUpdate(activeUpdateObject)` **without** passing an `onProgress` callback.
   - HTML markup (`src/index.html:705`) only contains a single text element `<div id="updater-status-message" class="progress-text hidden"></div>`.
   - The user sees static text ("Загрузка и установка обновления...") without any indication of download percentage, transferred bytes, or progress bar fill.
2. **Incomplete Error Handling**:
   - If `installUpdate` fails (e.g. network interruption, 404/500 HTTP status, signature mismatch), the code sets `statusMsg.textContent = 'Ошибка при установке обновления. Попробуйте позже.'`.
   - No granular error details are presented to the user.
   - If `downloadAndInstall` throws an exception during streaming, there is no explicit progress bar teardown or retry state formatting.

---

## 3. Key Source Files & File Structure

```
wiphoto/
├── package.json                         # npm scripts ("test": "node --test src/js/*.test.cjs")
├── src-tauri/
│   ├── Cargo.toml                       # Dependencies: tauri-plugin-updater, tauri-plugin-process
│   ├── tauri.conf.json                  # Updater endpoint & pubkey config
│   └── src/
│       └── lib.rs                       # Rust app entry & plugin initialization
└── src/
    ├── index.html                       # Lines 692-712: #modal-updater structure
    ├── styles/
    │   ├── main.css                     # Lines 153-174: .progress-bar, .progress-bar-fill, .progress-text
    │   └── components.css               # Modal overlays and dialog styling
    └── js/
        ├── app.js                       # Main frontend controller & module initialization
        ├── updater.js                   # OTA Updater API & UI binding logic
        ├── updater.test.cjs             # VM-based unit tests for updater
        └── tier1_tier2_features.test.cjs # R6 OTA update tests
```

---

## 4. Implementation Recommendations for R1 and R2

### 4.1 UI Markup & Styling Enhancements (`src/index.html` & `src/styles/components.css`)
Update `#modal-updater` in `src/index.html` to include a progress container:
```html
<div id="updater-progress-container" class="updater-progress-container hidden">
  <div class="progress-bar">
    <div id="updater-progress-bar-fill" class="progress-bar-fill" style="width: 0%;"></div>
  </div>
  <div class="updater-progress-details-row">
    <span id="updater-progress-percentage" class="progress-percentage">0%</span>
    <span id="updater-progress-bytes" class="progress-bytes">0 MB / 0 MB</span>
  </div>
</div>
```

### 4.2 Progress Event Adapter in `src/js/updater.js`
In Tauri v2 `tauri-plugin-updater`, `update.downloadAndInstall(onProgress)` emits event objects to `onProgress`:
- `{ event: 'Started', data: { contentLength: number } }`
- `{ event: 'Progress', data: { chunkLength: number } }`
- `{ event: 'Finished' }`

Implementation structure for `UpdaterAPI.installUpdate`:
```javascript
installUpdate: async (updateObj, onProgress) => {
  const targetObj = updateObj || activeUpdateObject;
  let downloadedBytes = 0;
  let totalBytes = 0;

  const progressHandler = (event) => {
    if (!event) return;
    if (event.event === 'Started') {
      totalBytes = event.data?.contentLength || 0;
      downloadedBytes = 0;
    } else if (event.event === 'Progress') {
      downloadedBytes += (event.data?.chunkLength || 0);
    }
    const percent = totalBytes > 0 ? Math.min(100, Math.round((downloadedBytes / totalBytes) * 100)) : 0;
    if (typeof onProgress === 'function') {
      onProgress({
        event: event.event,
        downloadedBytes,
        totalBytes,
        percent
      });
    }
  };

  if (targetObj && typeof targetObj.downloadAndInstall === 'function') {
    await targetObj.downloadAndInstall(progressHandler);
    return true;
  }
  // Fallback...
}
```

### 4.3 Graceful Error Handling Logic
In `initUpdaterUI()`, handle installation errors with retry capabilities:
1. Show progress container upon starting download.
2. Catch errors during `installUpdate` call.
3. On error:
   - Hide progress bar or display error fill state.
   - Format user-friendly message: `"Ошибка при загрузке обновления: [details]. Пожалуйста, проверьте подключение к сети."`.
   - Change `#btn-updater-install` text to `"Повторить"`.
   - Re-enable `#btn-updater-install` and `#btn-updater-postpone` buttons.
   - Allow user to dismiss modal via `"Отложить"` or `✕` close button without crashing or freezing.

### 4.4 Test Plan Enhancement (`src/js/updater.test.cjs`)
Add unit tests using Node.js test runner covering:
1. **Progress Event Calculations**: Verify correct percent calculation and byte formatting when receiving `'Started'`, `'Progress'`, and `'Finished'` events.
2. **Error Recovery**: Mock a failing `downloadAndInstall` promise, execute `installUpdate`, and assert that the error is handled gracefully, UI buttons are restored, and status message indicates error without unhandled rejections.
