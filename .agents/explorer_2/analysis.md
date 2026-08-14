# Deep Analysis: Graceful Error Handling for OTA Updates (Requirement R1)

## Executive Summary

WiPhoto currently relies on a lightweight OTA update wrapper (`src/js/updater.js`) backed by `tauri-plugin-updater` (Tauri v2). While basic `try...catch` blocks exist around `window.__TAURI__.updater.check()` and `targetObj.downloadAndInstall()`, the current implementation suffers from **silent failure modes**, **incomplete UI error states**, **lack of retry options**, and **vulnerability to hanging network requests**.

This analysis provides a comprehensive blueprint to transform WiPhoto's OTA updater into a robust, fault-tolerant system that handles offline states, server errors, signature failures, and interrupted downloads gracefully without freezing, crashing, or locking the user out of the application.

---

## 1. Investigation of Current Error Handling Behavior

### 1.1 `checkForUpdates` Flow (`src/js/updater.js:128-156`)
```javascript
checkForUpdates: async () => {
  try {
    if (window.__TAURI__?.updater?.check) {
      const update = await window.__TAURI__.updater.check();
      if (update && update.available) {
        activeUpdateObject = update;
        return { available: true, version: update.version, date: update.date || '', body: update.body || '...' };
      }
    } else if (window.__TAURI__?.core?.invoke) {
      const updateInfo = await window.__TAURI__.core.invoke('plugin:updater|check');
      if (updateInfo && updateInfo.available) { ... }
    }
  } catch (err) {
    if (typeof Logger !== 'undefined') Logger.error('Updater', 'Failed to check for updates', err);
    else console.error('Failed to check for updates:', err);
  }
  return null;
}
```
* **Current Behavior on Failure**: If DNS lookup fails, network is offline, or GitHub returns HTTP 404/500, the catch block catches the error, logs it via `Logger.error`, and returns `null`.
* **Deficiencies**:
  * **Silent Failure on Manual Check**: When a user explicitly triggers "Check for Updates" via Command Palette or Settings, returning `null` provides no feedback to the user. The user is left wondering if an update check occurred or if network failed.
  * **No Network Timeout**: `window.__TAURI__.updater.check()` relies on underlying HTTP client timeout defaults. If a network socket hangs without closing, the call remains pending indefinitely, freezing manual update checks.

### 1.2 `installUpdate` Flow (`src/js/updater.js:164-182`)
```javascript
installUpdate: async (updateObj, onProgress) => {
  const targetObj = updateObj || activeUpdateObject;
  try {
    if (targetObj && typeof targetObj.downloadAndInstall === 'function') {
      await targetObj.downloadAndInstall(onProgress);
      return true;
    } else if (window.__TAURI__?.core?.invoke) {
      await window.__TAURI__.core.invoke('plugin:updater|download_and_install');
      return true;
    }
  } catch (err) {
    if (typeof Logger !== 'undefined') Logger.error('Updater', 'Failed to download and install update', err);
    else console.error('Failed to download and install update:', err);
  }
  return false;
}
```
* **Current Behavior on Download Failure**: If WiFi drops mid-download, or checksum/signature verification fails, `downloadAndInstall()` throws an error. `installUpdate` logs the error and returns `false`.
* **Deficiencies**:
  * **Error Message Loss**: The caught `err` object (which contains crucial context like `Failed to fetch`, `Signature verification failed`, or `Connection reset`) is discarded and not passed to the UI layer.

### 1.3 `initUpdaterUI` UI Response (`src/js/updater.js:260-288`)
```javascript
const success = await UpdaterAPI.installUpdate(activeUpdateObject);
if (success) {
  statusMsg.textContent = 'Обновление успешно установлено! Перезапуск приложения...';
  ...
} else {
  if (statusMsg) {
    statusMsg.textContent = 'Ошибка при установке обновления. Попробуйте позже.';
  }
  btnInstall.disabled = false;
  if (btnPostpone) btnPostpone.disabled = false;
}
```
* **Current UI Behavior**: On failure, `statusMsg.textContent` is set to generic string `'Ошибка при установке обновления. Попробуйте позже.'`. `btnInstall` and `btnPostpone` are re-enabled.
* **Deficiencies**:
  * **Generic Error Messaging**: The user does not know *why* the update failed (e.g. offline vs server down vs invalid signature).
  * **Lack of Error Visual Styling**: `#updater-status-message` is a generic `div.progress-text.hidden`. It lacks error styling (no red accent background, danger border, or error icon), making it look like a regular progress note.
  * **No Dedicated Retry Button**: The user only sees "Обновить сейчас" (Update Now) and "Отложить" (Postpone), which can cause confusion after an error.

---

## 2. Required UI Additions for Error Presentation and Dismissal

To meet Acceptance Criteria:
1. **User-visible Error Message**: Interrupted or failed update download displays clear, contextual error UI.
2. **Error Dismissal & App Continuity**: User can dismiss error and continue using WiPhoto normally without UI locks or app restarts.

### 2.1 Update Modal Enhancements (`src/index.html`)

```html
<!-- Enhanced status & error section in #modal-updater -->
<div id="updater-status-container" class="updater-status-container hidden">
  <div id="updater-status-badge" class="updater-status-badge"></div>
  <div id="updater-status-message" class="updater-status-message"></div>
  <div id="updater-error-details" class="updater-error-details hidden"></div>
</div>
```

### 2.2 Error Categorization & Human-Readable Messaging

| Failure Scenario | Technical Cause | User-Facing Message (Russian) |
|---|---|---|
| **Offline State** | `navigator.onLine === false` or `ENOTFOUND` | **Нет подключения к сети.** Проверьте интернет-соединение и повторите попытку. |
| **Server Error** | HTTP 404 / 500 / 503 from endpoint | **Сервер обновлений недоступен.** Код ошибки сервера: {code}. Попробуйте позже. |
| **Interrupted Download** | Socket reset / network timeout / partial fetch | **Загрузка прервана.** Подключение было разорвано во время скачивания. |
| **Signature Error** | Minisign public key verification mismatch | **Ошибка безопасности.** Не удалось проверить подпись файла обновления. |
| **Generic Error** | Unhandled exception | **Ошибка обновления.** {errorMessage} |

### 2.3 Modal Dismissal & Recovery Design
* **Dismissal via "Отложить" / Close ("✕") / ESC Key**:
  * Calls `hideUpdateModal()`.
  * Resets modal state: clears error containers, resets progress bar, resets `btnInstall.disabled = false`, `btnInstall.textContent = 'Обновить сейчас'`.
  * Removes modal backdrop and returns keyboard focus to the triggering element (via `previousFocusedElement.focus()`).
* **Retry Action ("Повторить попытку")**:
  * When an error is active, `btnInstall` label changes to **"Повторить"** (Retry). Clicking it clears the previous error state and re-invokes `installUpdate(activeUpdateObject, onProgress)`.

### 2.4 Toast Notifications for Manual Checks (`Utils.toast`)
For manual checks triggered via Command Palette or Settings:
* **Network Error on Check**:
  `Utils.toast('Ошибка проверки обновлений: нет подключения к сети', 'error', 5000)`
* **No Updates Available**:
  `Utils.toast('У вас установлена самая свежая версия WiPhoto (v5.0.9)', 'info', 3000)`

---

## 3. Robust Error Handling Architecture in Rust / JS / TS

### 3.1 JavaScript Async Exception Safety & Timeout Protection

To prevent UI freezes when network requests stall indefinitely:

```javascript
/**
 * Wraps a promise with a hard timeout limit.
 * @param {Promise} promise 
 * @param {number} ms 
 * @param {string} timeoutMsg 
 */
function withTimeout(promise, ms = 30000, timeoutMsg = 'Таймаут сетевого запроса') {
  let timer;
  const timeoutPromise = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(timeoutMsg)), ms);
  });
  return Promise.race([promise, timeoutPromise]).finally(() => clearTimeout(timer));
}
```

### 3.2 Robust `installUpdate` Implementation Pattern

```javascript
installUpdate: async (updateObj, onProgress) => {
  const targetObj = updateObj || activeUpdateObject;
  if (!navigator.onLine) {
    return { success: false, error: 'OFFLINE', message: 'Отсутствует подключение к сети.' };
  }

  try {
    if (targetObj && typeof targetObj.downloadAndInstall === 'function') {
      await withTimeout(targetObj.downloadAndInstall(onProgress), 120000, 'Превышено время ожидания скачивания');
      return { success: true };
    } else if (window.__TAURI__?.core?.invoke) {
      await withTimeout(window.__TAURI__.core.invoke('plugin:updater|download_and_install'), 120000, 'Превышено время ожидания скачивания');
      return { success: true };
    }
    return { success: false, error: 'NO_UPDATER', message: 'Модуль обновления недоступен.' };
  } catch (err) {
    const errorStr = String(err?.message || err);
    let classified = 'UNKNOWN';
    let userMsg = `Не удалось установить обновление: ${errorStr}`;

    if (errorStr.includes('signature') || errorStr.includes('pubkey')) {
      classified = 'SIGNATURE';
      userMsg = 'Ошибка проверки цифровой подписи обновления.';
    } else if (errorStr.includes('network') || errorStr.includes('fetch') || errorStr.includes('connect')) {
      classified = 'NETWORK';
      userMsg = 'Сетевая ошибка при скачивании файла обновления.';
    } else if (errorStr.includes('Таймаут')) {
      classified = 'TIMEOUT';
      userMsg = 'Превышено время ожидания загрузки обновления.';
    }

    if (typeof Logger !== 'undefined') {
      Logger.error('Updater', `Update installation failed [${classified}]`, err);
    }
    return { success: false, error: classified, message: userMsg, rawError: errorStr };
  }
}
```

### 3.3 Rust Backend Fault Isolation
* In Tauri v2, `tauri-plugin-updater` executes network I/O in Tokio async background threads.
* Network exceptions (e.g. reqwest connection errors, DNS failure, 404 response body, invalid signature header) are wrapped into Rust `tauri_plugin_updater::Error` enums and converted to JS Promise rejections via serde.
* Rust backend will not crash or panic when `plugin:updater|check` or `plugin:updater|download_and_install` fails.
* Front-end `try...catch` guarantees zero unhandled promise rejections.

---

## 4. Test Scenarios for Network Error Handling

### 4.1 Test Matrix (AAA Pattern)

| Test ID | Test Name | Target Module | Condition | Expected Result |
|---|---|---|---|---|
| **TC-ERR-01** | `checkForUpdates` offline handling | `UpdaterAPI.checkForUpdates` | `navigator.onLine = false` or `updater.check` rejects | Returns `{ available: false, error: 'OFFLINE' }`, logs error without throwing |
| **TC-ERR-02** | `installUpdate` download error | `UpdaterAPI.installUpdate` | `downloadAndInstall` rejects with `NetworkError` | Returns `{ success: false, error: 'NETWORK' }`, passes descriptive error message |
| **TC-ERR-03** | UI error presentation & state recovery | `initUpdaterUI` | `installUpdate` fails | Status element receives `.error` class, error text rendered, buttons re-enabled |
| **TC-ERR-04** | Error dismissal & modal close | `hideUpdateModal` | Modal closed after error | Modal hidden (`.hidden` added), error message cleared, app remains fully operational |
| **TC-ERR-05** | Network timeout protection | `withTimeout` | Promise hangs > timeout duration | Promise rejects with timeout error after specified duration |

### 4.2 Edge Case Coverage
1. **Mid-Download Network Disconnect**: WiFi drops at 50% download progress.
   * *Verification*: Progress bar halts, progress listener receives error, UI switches to error view with Retry option.
2. **Repeated Clicks during Active Download**: User clicks "Обновить сейчас" multiple times rapidly.
   * *Verification*: `btnInstall.disabled = true` prevents duplicate IPC calls.
3. **Modal Dismissal During Download Error**: User clicks backdrop or presses ESC while error is displayed.
   * *Verification*: Modal closes instantly, pending states are cleared, next modal launch starts clean.
