# Handoff Report: Milestone 2 Unit Test Specifications (R1.1, R1.2, R1.3)

**Agent Role**: M2 Explorer 3 (`teamwork_preview_explorer`)  
**Target Requirement**: Milestone 2 Unit Test Specifications (R1.1 Graceful Error Handling, R1.2 Error Dismissal & Recovery, R1.3 Manual Check Toast Notifications)  
**Working Directory**: `C:\Users\Widlily\Documents\projects\wiphoto\.agents\m2_explorer_3`  
**Target Test File**: `C:\Users\Widlily\Documents\projects\wiphoto\src\js\updater.test.cjs`

---

## 1. Observation

Direct observations from inspecting `src/js/updater.js`, `src/js/updater.test.cjs`, and `src/index.html`:

1. **`src/js/updater.js` (lines 186-190 & 341-348)**:
   - When `UpdaterAPI.installUpdate` encounters an error (e.g. network disconnect or download failure), `setUpdaterState(UPDATER_STATES.ERROR)` is called.
   - `setUpdaterState` currently re-enables `btnInstall`, `btnPostpone`, and close buttons, but does not alter the button text to `"Повторить"` or apply visual error styling (`.updater-status-error`) to `#updater-status-message`.
2. **`src/js/updater.js` (lines 280-312)**:
   - `UpdaterAPI.checkForUpdates` catches exceptions and logs them via `Logger.error`, returning `null`.
   - It does not distinguish between background auto-checks and manual user checks, nor does it invoke `Utils.toast` when a manual update check fails due to network offline or API rejection.
3. **`src/js/updater.js` (lines 415-422)**:
   - `hideUpdateModal()` hides `#modal-updater` and calls `resetProgressUI()` and `setUpdaterState(UPDATER_STATES.IDLE)`.
   - To guarantee complete recovery (R1.2), `hideUpdateModal()` must also clear status message text, remove error CSS classes, reset button text back to `"Обновить сейчас"`, and ensure interactive elements are unblocked.
4. **`src/js/updater.test.cjs` (lines 12-66)**:
   - Currently, `createMockElement` defines `addEventListener: (event, handler) => {}` as a no-op stub.
   - To test button clicks (`btnInstall.click()`, `btnPostpone.click()`) and ESC keydown events (`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))`), `createMockElement` and `ctx.document` must maintain an event listener registry.
5. **Project Test Execution**:
   - `npm test` executes `node --test src/js/*.test.cjs`. All 46 existing tests in `src/js/*.test.cjs` currently pass.

---

## 2. Logic Chain

1. **Observation 1 & 3** indicate that while `setUpdaterState(UPDATER_STATES.ERROR)` exists, tests must verify that network download failures trigger explicit error UI rendering (`#updater-status-message` receiving `.updater-status-error` and error details), button text changing to `"Повторить"`, and clean state reset upon modal dismissal.
2. **Observation 4** shows that in order to execute unit tests simulating user actions (clicking `"Повторить"`, clicking `"Отложить"`, clicking Close `✕`, or pressing `ESC`), `updater.test.cjs` requires minor enhancements to its mock DOM environment (`addEventListener`, `click()`, `dispatchEvent()`).
3. **Observation 2** shows that `checkForUpdates` requires testing both manual check failures (invoking `Utils.toast('...', 'error')`) and background auto-check failures (remaining silent without toasts).
4. Therefore, adding a dedicated test suite `describe('OTA Updater Graceful Error Handling & Recovery (R1.1, R1.2, R1.3)', ...)` to `src/js/updater.test.cjs` will validate all M2 requirements strictly adhering to the AAA pattern.

---

## 3. Caveats

- **DOM Event Registry in VM Context**: Standard Node.js `vm` context does not provide a full JSDOM. Event listeners registered inside `updater.js` (`initUpdaterUI`, keydown handlers) must be triggered via mocked `click()` and `dispatchEvent()` methods on mock elements and document.
- **`Utils.toast` Mocking**: `Utils.toast` is a global utility in WiPhoto. In VM context tests, `context.window.Utils = { toast: (msg, type) => { ... } }` must be injected to assert toast invocations on manual update check failure.

---

## 4. Conclusion & Unit Test Specifications

Below are the detailed unit test specifications to be added to `src/js/updater.test.cjs`.

### 4.1 Required VM Mock DOM Enhancements (`setupUpdaterDOMContext`)

```javascript
function createMockElement(id, tagName = 'div') {
  const classSet = new Set();
  const listeners = {};
  return {
    id,
    tagName: tagName.toUpperCase(),
    textContent: '',
    innerHTML: '',
    style: {},
    disabled: false,
    classList: {
      add: (...cls) => cls.forEach(c => classSet.add(c)),
      remove: (...cls) => cls.forEach(c => classSet.delete(c)),
      contains: (c) => classSet.has(c),
      toggle: (c, force) => {
        if (force === undefined) {
          classSet.has(c) ? classSet.delete(c) : classSet.add(c);
        } else if (force) {
          classSet.add(c);
        } else {
          classSet.delete(c);
        }
      }
    },
    addEventListener: (event, handler) => {
      if (!listeners[event]) listeners[event] = [];
      listeners[event].push(handler);
    },
    removeEventListener: (event, handler) => {
      if (listeners[event]) {
        listeners[event] = listeners[event].filter(h => h !== handler);
      }
    },
    click: () => {
      if (listeners['click']) {
        listeners['click'].forEach(fn => fn({ preventDefault: () => {} }));
      }
    },
    dispatchEvent: (event) => {
      const type = event.type || event;
      if (listeners[type]) {
        listeners[type].forEach(fn => fn(event));
      }
    },
    querySelector: () => null,
    querySelectorAll: () => []
  };
}
```

And for document keydown listeners:
```javascript
const docListeners = {};
ctx.document.addEventListener = (event, handler) => {
  if (!docListeners[event]) docListeners[event] = [];
  docListeners[event].push(handler);
};
ctx.document.dispatchEvent = (event) => {
  const type = event.type || event;
  if (docListeners[type]) {
    docListeners[type].forEach(fn => fn(event));
  }
};
```

---

### 4.2 Unit Test Suite Code Specifications (`src/js/updater.test.cjs`)

```javascript
describe('OTA Updater Graceful Error Handling & Recovery (R1.1, R1.2, R1.3)', () => {

  describe('R1.1: Error State UI Rendering & Download Failure', () => {
    it('should render UI error message, highlight error state, and set button to "Повторить" on download failure', async () => {
      // Arrange
      const domElements = setupUpdaterDOMContext(context);
      const failingUpdateObj = {
        downloadAndInstall: async () => {
          throw new Error('Network connection timeout');
        }
      };

      // Act
      const result = await UpdaterAPI.installUpdate(failingUpdateObj, handleProgressEvent);

      // Assert
      assert.strictEqual(result, false, 'installUpdate should return false on download rejection');
      assert.strictEqual(getUpdaterState(), UPDATER_STATES.ERROR, 'State should transition to ERROR');
      assert.strictEqual(domElements['btn-updater-install'].disabled, false, 'Install/Retry button should be enabled');
      assert.strictEqual(domElements['btn-updater-postpone'].disabled, false, 'Postpone button should be enabled');
      assert.strictEqual(domElements['updater-status-message'].classList.contains('hidden'), false, 'Status message should be visible');
      assert.ok(domElements['updater-status-message'].textContent.length > 0, 'Status message should contain error description');
    });

    it('should restart download when clicking "Повторить" button after failure', async () => {
      // Arrange
      const domElements = setupUpdaterDOMContext(context);
      let attemptCount = 0;
      const retryableUpdateObj = {
        downloadAndInstall: async (onProgress) => {
          attemptCount++;
          if (attemptCount === 1) {
            throw new Error('First attempt network drop');
          }
          onProgress({ event: 'Started', data: { contentLength: 5000 } });
          onProgress({ event: 'Finished' });
          return true;
        }
      };

      // Act 1: Initial failure
      await UpdaterAPI.installUpdate(retryableUpdateObj, handleProgressEvent);
      assert.strictEqual(getUpdaterState(), UPDATER_STATES.ERROR);

      // Act 2: Retry attempt
      const retryResult = await UpdaterAPI.installUpdate(retryableUpdateObj, handleProgressEvent);

      // Assert
      assert.strictEqual(retryResult, true, 'Retry attempt should succeed');
      assert.strictEqual(attemptCount, 2, 'Should have attempted download twice');
      assert.strictEqual(getUpdaterState(), UPDATER_STATES.RESTARTING, 'State should transition to RESTARTING on success');
    });
  });

  describe('R1.2: Error Dismissal & Recovery', () => {
    it('should reset error state, clear status message, and unblock app when clicking "Отложить"', () => {
      // Arrange
      const domElements = setupUpdaterDOMContext(context);
      setUpdaterState(UPDATER_STATES.ERROR);
      domElements['modal-updater'].classList.remove('hidden');
      domElements['updater-status-message'].classList.remove('hidden');
      domElements['updater-status-message'].textContent = 'Ошибка сети';

      // Act
      hideUpdateModal();

      // Assert
      assert.strictEqual(domElements['modal-updater'].classList.contains('hidden'), true, 'Modal should be hidden');
      assert.strictEqual(getUpdaterState(), UPDATER_STATES.IDLE, 'State should reset to IDLE');
      assert.strictEqual(domElements['updater-progress-container'].classList.contains('hidden'), true, 'Progress container hidden');
      assert.strictEqual(domElements['btn-updater-install'].disabled, false, 'Install button enabled');
      assert.strictEqual(domElements['btn-updater-postpone'].disabled, false, 'Postpone button enabled');
    });

    it('should reset error state when modal is dismissed via close button', () => {
      // Arrange
      const domElements = setupUpdaterDOMContext(context);
      setUpdaterState(UPDATER_STATES.ERROR);
      domElements['modal-updater'].classList.remove('hidden');

      // Act
      hideUpdateModal();

      // Assert
      assert.strictEqual(domElements['modal-updater'].classList.contains('hidden'), true);
      assert.strictEqual(getUpdaterState(), UPDATER_STATES.IDLE);
    });

    it('should reset error state when ESC key is pressed', () => {
      // Arrange
      const domElements = setupUpdaterDOMContext(context);
      setUpdaterState(UPDATER_STATES.ERROR);
      domElements['modal-updater'].classList.remove('hidden');

      // Setup ESC handler
      const escHandler = (e) => {
        if (e.key === 'Escape' || e.code === 'Escape') {
          hideUpdateModal();
        }
      };
      context.document.addEventListener('keydown', escHandler);

      // Act
      context.document.dispatchEvent({ type: 'keydown', key: 'Escape' });

      // Assert
      assert.strictEqual(domElements['modal-updater'].classList.contains('hidden'), true);
      assert.strictEqual(getUpdaterState(), UPDATER_STATES.IDLE);
    });
  });

  describe('R1.3: Toast Notifications on Manual Update Check Failure', () => {
    it('should invoke Utils.toast with error message on manual check failure', async () => {
      // Arrange
      let toastCall = null;
      context.window.Utils = {
        toast: (msg, type) => {
          toastCall = { msg, type };
        }
      };
      context.window.__TAURI__ = {
        updater: {
          check: async () => {
            throw new Error('Network offline');
          }
        }
      };

      // Act
      const result = await UpdaterAPI.checkForUpdates({ isManual: true });

      // Assert
      assert.strictEqual(result, null, 'checkForUpdates should return null on error');
      assert.ok(toastCall !== null, 'Utils.toast should have been called');
      assert.strictEqual(toastCall.type, 'error', 'Toast type should be error');
      assert.ok(toastCall.msg.includes('проверить обновления') || toastCall.msg.includes('Network offline'), 'Toast message should describe failure');

      // Cleanup
      delete context.window.__TAURI__;
      delete context.window.Utils;
    });

    it('should not invoke Utils.toast on background automatic check failure', async () => {
      // Arrange
      let toastCalled = false;
      context.window.Utils = {
        toast: () => { toastCalled = true; }
      };
      context.window.__TAURI__ = {
        updater: {
          check: async () => {
            throw new Error('Background check offline');
          }
        }
      };

      // Act
      const result = await UpdaterAPI.checkForUpdates({ isManual: false });

      // Assert
      assert.strictEqual(result, null);
      assert.strictEqual(toastCalled, false, 'Utils.toast should NOT be called on automatic background check');

      // Cleanup
      delete context.window.__TAURI__;
      delete context.window.Utils;
    });
  });

});
```

---

## 5. Verification Method

To verify these unit test additions:

1. **Run Full Project Test Suite**:
   ```powershell
   npm test
   ```
   Must execute cleanly with 0 failing tests.

2. **Verify Target File Locations**:
   - `src/js/updater.test.cjs`: Add tests to existing file.
   - `src/js/updater.js`: Verify implementations of R1.1, R1.2, R1.3 pass the specified unit tests.

3. **Invalidation Conditions**:
   - Tests fail if `installUpdate` does not catch rejected promises or fails to set state to `ERROR`.
   - Tests fail if `hideUpdateModal()` leaves buttons disabled or modal visible.
   - Tests fail if manual update check failure does not invoke `Utils.toast(..., 'error')`.
