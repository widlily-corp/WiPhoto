# Requirement R2: Visual Progress Indicator — Technical Analysis & Implementation Blueprint

## Executive Summary
This document presents the detailed architectural and technical investigation for **Requirement R2 (Visual Progress Indicator)** in WiPhoto's OTA update system. 

WiPhoto utilizes Tauri v2 with `tauri-plugin-updater` and `tauri-plugin-process`. While `UpdaterAPI.installUpdate` accepts an `onProgress` callback parameter, the current UI implementation in `src/js/updater.js` and `src/index.html` does not pass progress callbacks or render visual progress indicators (progress bar, percentage, downloaded byte counts). 

This report provides the complete event structure specification for Tauri v2 updater download progress, an update lifecycle state machine, proposed UI DOM elements adhering to Refined Minimal / Swiss aesthetics, proposed JS logic modifications, and comprehensive verification scenarios.

---

## 1. Codebase Inventory & Current Implementation Analysis

### 1.1 Backend Configuration & Plugin Registration
- **`src-tauri/Cargo.toml`**: Includes `tauri-plugin-updater = "2"` and `tauri-plugin-process = "2"`.
- **`src-tauri/src/lib.rs`**: Registers `tauri_plugin_updater::Builder::new().build()` and `tauri_plugin_process::init()`.
- **`src-tauri/tauri.conf.json`**:
  - `bundle.createUpdaterArtifacts`: `true`
  - `plugins.updater.endpoints`: `["https://github.com/widlily-corp/WiPhoto/releases/latest/download/latest.json"]`
  - `plugins.updater.pubkey`: Valid Minisign public key string configured.

### 1.2 Frontend Implementation (`src/js/updater.js`)
- `UpdaterAPI.checkForUpdates()`: Calls `window.__TAURI__.updater.check()` or IPC `plugin:updater|check`.
- `UpdaterAPI.installUpdate(updateObj, onProgress)` (Lines 164–182):
  ```js
  if (targetObj && typeof targetObj.downloadAndInstall === 'function') {
    await targetObj.downloadAndInstall(onProgress);
    return true;
  }
  ```
- **Identified Deficiencies**:
  1. **Missing Progress Callback Invocation**: `initUpdaterUI()` (Lines 261–288) calls `UpdaterAPI.installUpdate(activeUpdateObject)` without passing an `onProgress` callback handler.
  2. **Missing Progress DOM Elements**: `src/index.html` only provides `<div id="updater-status-message" class="progress-text hidden"></div>`. It lacks a progress bar element (`.progress-bar`, `.progress-bar-fill`), percentage label, and downloaded byte counter.
  3. **Lack of Explicit State Machine**: Update progress is tracked as a static message ("Загрузка и установка обновления...") without intermediate progress states (`DOWNLOADING`, `VERIFYING`, `RESTARTING`, `ERROR`).

---

## 2. Tauri v2 Updater Progress Event Structure Specification

When `Update.prototype.downloadAndInstall(onEvent)` is executed in Tauri v2 (`@tauri-apps/plugin-updater`), `onEvent` receives progress event objects of the following schema:

### 2.1 Event Schema Definition
```typescript
type DownloadEvent =
  | { event: 'Started'; data: { contentLength?: number } }
  | { event: 'Progress'; data: { chunkLength: number } }
  | { event: 'Finished' };
```

### 2.2 Event Lifecycles & Field Definitions

| Event Name (`event.event`) | Field | Type | Description |
|---|---|---|---|
| `'Started'` | `data.contentLength` | `number \| undefined` | Total byte size of the update payload (from HTTP `Content-Length`). May be `undefined` if server uses chunked encoding. |
| `'Progress'` | `data.chunkLength` | `number` | Byte size of the newly received data chunk. Must be accumulated (`downloadedBytes += chunkLength`). |
| `'Finished'` | — | — | Download completed. Verification (Minisign public key check) and file extraction initiated. |

### 2.3 Progress Metrics Calculation Logic
- **Downloaded Bytes Accumulation**: `downloadedBytes += chunkLength`
- **Percentage Calculation**:
  $$\text{Percentage} = \begin{cases} \min\left(100, \left\lfloor \frac{\text{downloadedBytes}}{\text{totalBytes}} \times 100 \right\rfloor\right) & \text{if } \text{totalBytes} > 0 \\ 100 & \text{if Finished} \\ 0 & \text{otherwise} \end{cases}$$
- **Byte Formatter**: Utilize `Utils.formatSize(bytes)` (e.g. `4.2 MB / 15.4 MB (27%)`).

---

## 3. Update Lifecycle State Machine

To enforce deterministic UI transitions and graceful recovery, update operations are modeled as a Finite State Machine (FSM):

```
       [IDLE / UNCHECKED]
               │
               ▼ (checkForUpdates)
          [CHECKING]
               │
      ┌────────┴────────┐
      ▼                 ▼
[UP_TO_DATE]    [UPDATE_AVAILABLE]
                        │ (User clicks "Обновить сейчас")
                        ▼
                  [DOWNLOADING] (Receives Started/Progress events)
                        │
                        ▼ (Receives Finished event)
                   [VERIFYING]
                        │
                        ▼ (downloadAndInstall completes)
                  [RESTARTING] ──► Relaunches app
                        │
                        ▼ (on Exception/Network Drop)
                     [ERROR] ──► Re-enables Retry/Dismiss
```

### State Machine Transition Table

| Current State | Event / Trigger | Target State | UI Component Behavior |
|---|---|---|---|
| `IDLE` | Trigger update check | `CHECKING` | Show checking indicator in settings / welcome screen |
| `CHECKING` | Update object returned | `UPDATE_AVAILABLE` | Display `#modal-updater` with version tag & rendered release notes |
| `UPDATE_AVAILABLE` | Click `#btn-updater-install` | `DOWNLOADING` | Disable action buttons; show `#updater-progress-container`; set progress fill to 0% |
| `DOWNLOADING` | `Started` / `Progress` events | `DOWNLOADING` | Update progress bar width; display accumulated downloaded bytes and calculated percentage |
| `DOWNLOADING` | `Finished` event | `VERIFYING` | Set progress fill to 100%; update status text: "Проверка подписи и установка..." |
| `VERIFYING` | `installUpdate` resolves `true` | `RESTARTING` | Status: "Обновление установлено! Перезапуск..."; delay 1.5s; call `UpdaterAPI.relaunchApp()` |
| `DOWNLOADING` / `VERIFYING` | Exception / Network error | `ERROR` | Hide progress bar or apply error styling; display error message; re-enable "Обновить сейчас" & "Отложить" |

---

## 4. UI Design & Implementation Blueprint

### 4.1 HTML Markup Structure (`src/index.html`)
Inside `#modal-updater .modal-body` (below `.updater-info`):

```html
<!-- OTA Updater Modal -->
<div id="modal-updater" class="modal hidden">
  <div class="modal-overlay"></div>
  <div class="modal-content modal-updater">
    <div class="modal-header">
      <h2>Доступно обновление WiPhoto</h2>
      <button class="modal-close" data-close="modal-updater">✕</button>
    </div>
    <div class="modal-body">
      <div class="updater-info">
        <span class="updater-version-tag" id="updater-version-tag">Новая версия: v5.1.0</span>
        <div class="updater-notes-label">Список изменений:</div>
        <div id="updater-release-notes" class="updater-release-notes"></div>
      </div>
      
      <!-- Requirement R2 Visual Progress Bar & Details -->
      <div id="updater-progress-container" class="scan-progress updater-progress-container hidden">
        <div class="progress-bar">
          <div id="updater-progress-fill" class="progress-bar-fill" style="width: 0%"></div>
        </div>
        <div class="updater-progress-details">
          <span id="updater-progress-text" class="progress-text">Инициализация загрузки...</span>
          <span id="updater-progress-bytes" class="progress-bytes">0 B / 0 B (0%)</span>
        </div>
      </div>

      <div id="updater-status-message" class="progress-text hidden"></div>
      
      <div class="setting-actions">
        <button class="btn btn-secondary" id="btn-updater-postpone">Отложить</button>
        <button class="btn btn-primary" id="btn-updater-install">Обновить сейчас</button>
      </div>
    </div>
  </div>
</div>
```

### 4.2 Proposed CSS Rules (`src/styles/components.css`)
```css
.updater-progress-container {
  margin-top: 16px;
  margin-bottom: 12px;
}

.updater-progress-details {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 6px;
  font-size: 0.85rem;
  color: var(--text-muted, #94a3b8);
  font-variant-numeric: tabular-nums;
}

.progress-bytes {
  font-family: var(--font-mono, monospace);
  font-weight: 500;
}
```

### 4.3 Proposed JS Modifications (`src/js/updater.js`)

```js
// Progress tracking state
let updateState = {
  status: 'IDLE',
  downloadedBytes: 0,
  totalBytes: 0
};

/**
 * Handles Tauri updater download progress events.
 * @param {Object} event { event: 'Started'|'Progress'|'Finished', data?: { contentLength?: number, chunkLength?: number } }
 */
function handleDownloadProgress(event) {
  const container = document.getElementById('updater-progress-container');
  const fill = document.getElementById('updater-progress-fill');
  const textEl = document.getElementById('updater-progress-text');
  const bytesEl = document.getElementById('updater-progress-bytes');

  if (container) container.classList.remove('hidden');
  if (!event) return;

  if (event.event === 'Started') {
    updateState.status = 'DOWNLOADING';
    updateState.totalBytes = event.data?.contentLength || 0;
    updateState.downloadedBytes = 0;
    if (textEl) textEl.textContent = 'Загрузка обновления...';
    if (fill) fill.style.width = '0%';
    if (bytesEl) {
      const totStr = updateState.totalBytes && typeof Utils !== 'undefined' ? Utils.formatSize(updateState.totalBytes) : '...';
      bytesEl.textContent = `0 B / ${totStr} (0%)`;
    }
  } else if (event.event === 'Progress') {
    updateState.status = 'DOWNLOADING';
    updateState.downloadedBytes += (event.data?.chunkLength || 0);
    const downloaded = updateState.downloadedBytes;
    const total = updateState.totalBytes;

    if (total > 0) {
      const pct = Math.min(100, Math.round((downloaded / total) * 100));
      if (fill) fill.style.width = `${pct}%`;
      const dlStr = typeof Utils !== 'undefined' ? Utils.formatSize(downloaded) : `${downloaded} B`;
      const totStr = typeof Utils !== 'undefined' ? Utils.formatSize(total) : `${total} B`;
      if (bytesEl) bytesEl.textContent = `${dlStr} / ${totStr} (${pct}%)`;
    } else {
      if (fill) fill.style.width = '100%';
      const dlStr = typeof Utils !== 'undefined' ? Utils.formatSize(downloaded) : `${downloaded} B`;
      if (bytesEl) bytesEl.textContent = dlStr;
    }
  } else if (event.event === 'Finished') {
    updateState.status = 'VERIFYING';
    if (fill) fill.style.width = '100%';
    if (textEl) textEl.textContent = 'Проверка и распаковка пакета...';
    if (bytesEl && updateState.totalBytes > 0) {
      const totStr = typeof Utils !== 'undefined' ? Utils.formatSize(updateState.totalBytes) : `${updateState.totalBytes} B`;
      bytesEl.textContent = `${totStr} / ${totStr} (100%)`;
    }
  }
}
```

In `initUpdaterUI()`:
```js
  if (btnInstall) {
    btnInstall.addEventListener('click', async () => {
      btnInstall.disabled = true;
      if (btnPostpone) btnPostpone.disabled = true;

      const progressContainer = document.getElementById('updater-progress-container');
      if (progressContainer) progressContainer.classList.remove('hidden');

      if (statusMsg) {
        statusMsg.classList.remove('hidden');
        statusMsg.textContent = 'Инициализация загрузки...';
      }

      const success = await UpdaterAPI.installUpdate(activeUpdateObject, handleDownloadProgress);
      if (success) {
        updateState.status = 'RESTARTING';
        if (statusMsg) {
          statusMsg.textContent = 'Обновление успешно установлено! Перезапуск приложения...';
        }
        setTimeout(async () => {
          const relaunched = await UpdaterAPI.relaunchApp();
          if (!relaunched) {
            hideUpdateModal();
          }
        }, 1500);
      } else {
        updateState.status = 'ERROR';
        if (statusMsg) {
          statusMsg.textContent = 'Ошибка при установке обновления. Попробуйте позже.';
        }
        if (progressContainer) progressContainer.classList.add('hidden');
        btnInstall.disabled = false;
        if (btnPostpone) btnPostpone.disabled = false;
      }
    });
  }
```

---

## 5. Verification & Test Scenarios

### 5.1 Unit Tests (`src/js/updater.test.cjs`)
1. **Progress Callback Processing Test**:
   - Mock progress events: `Started({ contentLength: 10485760 })`, `Progress({ chunkLength: 5242880 })`, `Finished()`.
   - Assert `handleDownloadProgress` correctly updates `updateState` and progress element text/width (`50%`, `5.0 MB / 10.0 MB (50%)`).
2. **`UpdaterAPI.installUpdate` Callback Delegation Test**:
   - Mock `downloadAndInstall` method on target update object.
   - Invoke `UpdaterAPI.installUpdate(mockObj, progressCb)`.
   - Assert `mockObj.downloadAndInstall` was called with `progressCb`.

### 5.2 Command Verification
Run test suite:
```bash
npm test
```
Or directly:
```bash
node --test src/js/updater.test.cjs
```
