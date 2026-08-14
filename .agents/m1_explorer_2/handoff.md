# Handoff Report — Milestone 1: Visual Progress Indicator JS Logic (R2.2, R2.3)

**Author**: M1 Explorer 2 (`teamwork_preview_explorer`)  
**Target Path**: `C:\Users\Widlily\Documents\projects\wiphoto\.agents\m1_explorer_2\handoff.md`  
**Date**: 2026-08-02  

---

## 1. Observation

Direct observations from examining the codebase and configuration:

1. **Existing `src/js/updater.js` (lines 164-182)**:
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
     } catch (err) { ... }
     return false;
   }
   ```
   *Observation*: `installUpdate` currently accepts an `onProgress` parameter, but does not calculate accumulated downloaded bytes, calculate percentages, format bytes using `Utils.formatSize`, or manage state machine transitions for the progress UI.

2. **Existing `src/js/utils.js` (lines 5-12)**:
   ```javascript
   formatSize(bytes) {
     if (!bytes) return '0 B';
     const units = ['B', 'KB', 'MB', 'GB', 'TB'];
     let i = 0;
     let s = bytes;
     while (s >= 1024 && i < units.length - 1) { s /= 1024; i++; }
     return `${s.toFixed(1)} ${units[i]}`;
   }
   ```
   *Observation*: `Utils.formatSize` handles byte conversion up to TB with 1-decimal precision (e.g. `1048576` -> `'1.0 MB'`).

3. **DOM Elements in `src/index.html` (lines 691-712)**:
   `#modal-updater` currently contains `#updater-version-tag`, `#updater-release-notes`, `#updater-status-message`, `#btn-updater-install`, and `#btn-updater-postpone`. Progress elements (`#updater-progress-container`, `#updater-progress-bar-fill`, `#updater-progress-percentage`, `#updater-progress-bytes`) are specified under R2.1 (Milestone 1).

4. **Tauri Updater Progress Event Contract (`PROJECT.md`)**:
   `onProgress(event)` payload structure:
   - `{ event: 'Started', data?: { contentLength?: number } }`
   - `{ event: 'Progress', data?: { chunkLength?: number } }`
   - `{ event: 'Finished' }`

5. **Test Baseline Command Execution**:
   `npm test` executes `node --test src/js/*.test.cjs`. Baseline run executed 46 tests across 22 suites with 0 failures (100% pass).

---

## 2. Logic Chain

1. **Progress Calculation & Byte Accumulation Logic**:
   - When Tauri emits `{ event: 'Started', data: { contentLength } }`, initialize `accumulatedDownloadedBytes = 0` and record `totalUpdateBytes = event.data?.contentLength || 0`.
   - When Tauri emits `{ event: 'Progress', data: { chunkLength } }`, increment `accumulatedDownloadedBytes += Math.max(0, event.data?.chunkLength || 0)`.
   - Calculate percentage: if `totalUpdateBytes > 0`, `percentage = Math.min(100, Math.max(0, Math.floor((accumulatedDownloadedBytes / totalUpdateBytes) * 100)))`. Otherwise, percentage defaults to `0` or indeterminate state.
   - Format byte text: if `totalUpdateBytes > 0`, formatted string is `${formatBytes(accumulatedDownloadedBytes)} / ${formatBytes(totalUpdateBytes)}`. Otherwise `${formatBytes(accumulatedDownloadedBytes)}`.
   - When Tauri emits `{ event: 'Finished' }`, set `accumulatedDownloadedBytes = totalUpdateBytes > 0 ? totalUpdateBytes : accumulatedDownloadedBytes`, set `percentage = 100`, and transition state to `VERIFYING`.

2. **State Machine Transitions**:
   State transitions must govern both internal execution state and DOM UI element attributes:
   - `IDLE`: Initial / default state. Modal hidden, progress UI reset.
   - `CHECKING`: Triggered during update check.
   - `UPDATE_AVAILABLE`: Update info populated, modal visible, buttons enabled, progress UI hidden.
   - `DOWNLOADING`: User clicks install button. `#updater-progress-container` revealed, install/postpone/close buttons disabled, progress bar fill & percentage active.
   - `VERIFYING`: Download completed (`Finished` event). Progress bar fill = `100%`, status text set to `'Проверка целостности пакета...'`.
   - `RESTARTING`: `installUpdate` resolves `true`. Status text set to `'Обновление успешно установлено! Перезапуск приложения...'`, delay timer invoked prior to `relaunchApp()`.
   - `ERROR`: Download or verification fails. Status text updated, buttons re-enabled.

3. **Isolated VM Test Safety**:
   In Node VM test contexts (`updater.test.cjs`), `Utils` may or may not be defined globally. `updater.js` must implement a safe `formatBytes(bytes)` helper:
   ```javascript
   function formatBytes(bytes) {
     if (typeof Utils !== 'undefined' && typeof Utils.formatSize === 'function') {
       return Utils.formatSize(bytes);
     }
     if (!bytes || isNaN(bytes) || bytes <= 0) return '0 B';
     const units = ['B', 'KB', 'MB', 'GB', 'TB'];
     let i = 0;
     let s = bytes;
     while (s >= 1024 && i < units.length - 1) { s /= 1024; i++; }
     return `${s.toFixed(1)} ${units[i]}`;
   }
   ```

---

## 3. Caveats

- **Scope Separation**: Error handling details (structured error messages, error badges, "Повторить" retry buttons, toast fallbacks) belong to Milestone 2 (R1.1-R1.3). Milestone 1 handles progress visualization, byte accumulation, and state machine transitions.
- **Indeterminate Total Bytes**: If a server returns an update payload without `contentLength` (`contentLength === 0` or `undefined`), percentage defaults to zero and bytes counter displays total downloaded bytes without total capacity denominator.

---

## 4. Conclusion & Worker Logic Specification

### Detailed JS Specification for `src/js/updater.js`

The Worker implementer should update `src/js/updater.js` with the following structure:

```javascript
// 1. State Machine Definition
const UPDATER_STATES = Object.freeze({
  IDLE: 'IDLE',
  CHECKING: 'CHECKING',
  UPDATE_AVAILABLE: 'UPDATE_AVAILABLE',
  DOWNLOADING: 'DOWNLOADING',
  VERIFYING: 'VERIFYING',
  RESTARTING: 'RESTARTING',
  ERROR: 'ERROR'
});

let currentUpdaterState = UPDATER_STATES.IDLE;
let accumulatedDownloadedBytes = 0;
let totalUpdateBytes = 0;

/**
 * Returns current updater state.
 */
function getUpdaterState() {
  return currentUpdaterState;
}

/**
 * Updates internal state and synchronizes UI element visibility & button attributes.
 * @param {string} newState 
 * @param {Object} [details] 
 */
function setUpdaterState(newState, details = {}) {
  currentUpdaterState = newState;
  
  if (typeof Logger !== 'undefined') {
    Logger.info('Updater', `State transition -> ${newState}`, details);
  }

  const btnInstall = document.getElementById('btn-updater-install');
  const btnPostpone = document.getElementById('btn-updater-postpone');
  const closeBtns = document.querySelectorAll('[data-close="modal-updater"]');
  const progressContainer = document.getElementById('updater-progress-container');
  const statusMsg = document.getElementById('updater-status-message');

  switch (newState) {
    case UPDATER_STATES.DOWNLOADING:
    case UPDATER_STATES.VERIFYING:
      if (btnInstall) btnInstall.disabled = true;
      if (btnPostpone) btnPostpone.disabled = true;
      closeBtns.forEach(btn => { btn.disabled = true; });
      if (progressContainer) progressContainer.classList.remove('hidden');
      break;

    case UPDATER_STATES.RESTARTING:
      if (btnInstall) btnInstall.disabled = true;
      if (btnPostpone) btnPostpone.disabled = true;
      closeBtns.forEach(btn => { btn.disabled = true; });
      if (statusMsg) {
        statusMsg.classList.remove('hidden');
        statusMsg.textContent = 'Обновление успешно установлено! Перезапуск приложения...';
      }
      break;

    case UPDATER_STATES.ERROR:
      if (btnInstall) btnInstall.disabled = false;
      if (btnPostpone) btnPostpone.disabled = false;
      closeBtns.forEach(btn => { btn.disabled = false; });
      break;

    case UPDATER_STATES.IDLE:
    case UPDATER_STATES.UPDATE_AVAILABLE:
      if (btnInstall) btnInstall.disabled = false;
      if (btnPostpone) btnPostpone.disabled = false;
      closeBtns.forEach(btn => { btn.disabled = false; });
      resetProgressUI();
      break;
  }
}

/**
 * Safe byte formatter with Utils.formatSize fallback.
 */
function formatBytes(bytes) {
  if (typeof Utils !== 'undefined' && typeof Utils.formatSize === 'function') {
    return Utils.formatSize(bytes);
  }
  if (!bytes || isNaN(bytes) || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  let s = bytes;
  while (s >= 1024 && i < units.length - 1) { s /= 1024; i++; }
  return `${s.toFixed(1)} ${units[i]}`;
}

/**
 * Resets progress UI state elements.
 */
function resetProgressUI() {
  accumulatedDownloadedBytes = 0;
  totalUpdateBytes = 0;
  const progressContainer = document.getElementById('updater-progress-container');
  const barFill = document.getElementById('updater-progress-bar-fill');
  const percentEl = document.getElementById('updater-progress-percentage');
  const bytesEl = document.getElementById('updater-progress-bytes');

  if (progressContainer) progressContainer.classList.add('hidden');
  if (barFill) barFill.style.width = '0%';
  if (percentEl) percentEl.textContent = '0%';
  if (bytesEl) bytesEl.textContent = '0 B';
}

/**
 * Updates progress UI elements based on event data.
 */
function updateProgressUI(progressData) {
  const barFill = document.getElementById('updater-progress-bar-fill');
  const percentEl = document.getElementById('updater-progress-percentage');
  const bytesEl = document.getElementById('updater-progress-bytes');

  if (barFill) {
    barFill.style.width = `${progressData.percentage}%`;
  }
  if (percentEl) {
    percentEl.textContent = `${progressData.percentage}%`;
  }
  if (bytesEl) {
    bytesEl.textContent = progressData.totalBytes > 0
      ? `${progressData.formattedDownloaded} / ${progressData.formattedTotal}`
      : progressData.formattedDownloaded;
  }
}

// 2. Updated UpdaterAPI.installUpdate implementation
UpdaterAPI.installUpdate = async (updateObj, onProgress) => {
  const targetObj = updateObj || activeUpdateObject;
  setUpdaterState(UPDATER_STATES.DOWNLOADING);

  const progressWrapper = (event) => {
    if (!event || typeof event !== 'object') return;

    const evtType = event.event;
    if (evtType === 'Started') {
      accumulatedDownloadedBytes = 0;
      totalUpdateBytes = Number(event.data?.contentLength) || 0;
    } else if (evtType === 'Progress') {
      const chunk = Number(event.data?.chunkLength) || 0;
      accumulatedDownloadedBytes += Math.max(0, chunk);
    } else if (evtType === 'Finished') {
      if (totalUpdateBytes > 0) {
        accumulatedDownloadedBytes = totalUpdateBytes;
      }
      setUpdaterState(UPDATER_STATES.VERIFYING);
    }

    const percentage = totalUpdateBytes > 0
      ? Math.min(100, Math.max(0, Math.floor((accumulatedDownloadedBytes / totalUpdateBytes) * 100)))
      : 0;

    const progressData = {
      event: evtType,
      downloadedBytes: accumulatedDownloadedBytes,
      totalBytes: totalUpdateBytes,
      percentage: percentage,
      formattedDownloaded: formatBytes(accumulatedDownloadedBytes),
      formattedTotal: formatBytes(totalUpdateBytes)
    };

    updateProgressUI(progressData);

    if (typeof onProgress === 'function') {
      onProgress(event, progressData);
    }
  };

  try {
    if (targetObj && typeof targetObj.downloadAndInstall === 'function') {
      await targetObj.downloadAndInstall(progressWrapper);
      setUpdaterState(UPDATER_STATES.RESTARTING);
      return true;
    } else if (window.__TAURI__?.core?.invoke) {
      await window.__TAURI__.core.invoke('plugin:updater|download_and_install');
      setUpdaterState(UPDATER_STATES.RESTARTING);
      return true;
    }
  } catch (err) {
    setUpdaterState(UPDATER_STATES.ERROR, { error: err });
    if (typeof Logger !== 'undefined') {
      Logger.error('Updater', 'Failed to download and install update', err);
    } else {
      console.error('Failed to download and install update:', err);
    }
  }
  return false;
};
```

---

## 5. Verification Method

### AAA Unit & Integration Tests to add in `src/js/updater.test.cjs`:

```javascript
describe('Progress Event & State Transitions (R2.2, R2.3)', () => {
  it('should track downloaded bytes, calculate percentage, and invoke onProgress callback', async () => {
    // Arrange
    let reportedEvents = [];
    const mockUpdateObj = {
      downloadAndInstall: async (callback) => {
        callback({ event: 'Started', data: { contentLength: 10485760 } }); // 10 MB
        callback({ event: 'Progress', data: { chunkLength: 2621440 } }); // 2.5 MB (25%)
        callback({ event: 'Progress', data: { chunkLength: 2621440 } }); // 5.0 MB (50%)
        callback({ event: 'Finished' });
      }
    };

    // Act
    const result = await context.window.UpdaterAPI.installUpdate(mockUpdateObj, (evt, progress) => {
      reportedEvents.push(progress);
    });

    // Assert
    assert.strictEqual(result, true);
    assert.strictEqual(reportedEvents.length, 4);
    assert.strictEqual(reportedEvents[0].percentage, 0);
    assert.strictEqual(reportedEvents[1].percentage, 25);
    assert.strictEqual(reportedEvents[2].percentage, 50);
    assert.strictEqual(reportedEvents[3].percentage, 100);
    assert.strictEqual(reportedEvents[2].formattedDownloaded, '5.0 MB');
    assert.strictEqual(reportedEvents[2].formattedTotal, '10.0 MB');
  });

  it('should transition through state machine sequence: IDLE -> DOWNLOADING -> VERIFYING -> RESTARTING', async () => {
    // Arrange
    const stateSequence = [];
    const mockUpdateObj = {
      downloadAndInstall: async (callback) => {
        stateSequence.push(context.window.getUpdaterState());
        callback({ event: 'Started', data: { contentLength: 1000 } });
        callback({ event: 'Finished' });
        stateSequence.push(context.window.getUpdaterState());
      }
    };

    // Act
    await context.window.UpdaterAPI.installUpdate(mockUpdateObj);
    stateSequence.push(context.window.getUpdaterState());

    // Assert
    assert.deepStrictEqual(stateSequence, ['DOWNLOADING', 'VERIFYING', 'RESTARTING']);
  });
});
```

### Command Verification:
Run test command to verify test execution and zero regression:
```powershell
npm test
```
All tests must output `pass` with code `0`.
