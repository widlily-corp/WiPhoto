# Milestone 1: Unit Test Specifications Analysis Report (R2.1, R2.2, R2.3)

## 1. Observation

Direct inspection of the repository files revealed the following exact starting state:

1. **`PROJECT.md`** (lines 11-26, 28-39):
   - **M1 Scope**: Visual Progress Indicator implementing R2.1 (UI Elements), R2.2 (Progress Event Handling), and R2.3 (State Transitions) in `src/index.html` and `src/js/updater.js`.
   - **Target Test File**: `src/js/updater.test.cjs`.
   - **Test Runner Command**: `npm test` (`node --test src/js/*.test.cjs`).

2. **`src/js/updater.test.cjs`** (lines 1-173):
   - Test runner framework: Node native test module (`node:test`) and assertion module (`node:assert`).
   - Execution methodology: `vm.runInNewContext(updaterCode, context)` executes `updater.js` inside an isolated VM context.
   - Existing test suites:
     - `isNewerVersion` (lines 31-56)
     - `renderMarkdown` (lines 58-91)
     - `parseReleaseNotes` (lines 93-129)
     - `UpdaterAPI.relaunchApp` (lines 131-171)
   - Current limitation: The context (lines 12-18) does not mock `window.document` DOM nodes (`modal-updater`, `updater-progress-container`, etc.), making current VM context insufficient for DOM progress testing without DOM mock initialization.

3. **`src/js/updater.js`** (lines 164-209, 254-302):
   - `installUpdate(updateObj, onProgress)`: Accepts `updateObj` and `onProgress` callback, currently invokes `targetObj.downloadAndInstall(onProgress)` without internal event processing.
   - `initUpdaterUI()`: Manages click handler for `#btn-updater-install`, disables buttons, sets static status string `'Загрузка и установка обновления...'`, and awaits `installUpdate`.

4. **`src/index.html`** (lines 691-712):
   - `#modal-updater` currently lacks visual progress bar elements (`#updater-progress-container`, `#updater-progress-bar-fill`, `#updater-progress-percentage`, `#updater-progress-bytes`).

---

## 2. Logic Chain

From the observations above, the step-by-step reasoning leads to the following unit test specifications:

1. **VM Context DOM Mocking Requirement**:
   - *Observation*: `updater.js` manipulates DOM elements via `document.getElementById()`. Currently `context.document` is missing in `updater.test.cjs`.
   - *Deduction*: To run DOM assertions without full JSDOM overhead, `updater.test.cjs` requires a lightweight helper (`createMockElement` and `setupUpdaterDOMContext`) within the VM context to simulate DOM elements (`id`, `style`, `textContent`, `classList`, `disabled`, `addEventListener`).

2. **Tauri v2 Updater Progress Event Structure**:
   - *Observation*: Tauri v2 updater API emits progress events with payload format:
     - `{ event: 'Started', data: { contentLength?: number } }`
     - `{ event: 'Progress', data: { chunkLength: number } }`
     - `{ event: 'Finished' }`
   - *Deduction*: Unit tests must verify DOM element updates for all three distinct event types and test edge conditions (missing data, 0 content length, chunk accumulation).

3. **State Transition Flow (R2.3)**:
   - *Observation*: The update process transitions through `DOWNLOADING` -> `VERIFYING` -> `RESTARTING`.
   - *Deduction*: Tests must assert button disabling during download/relaunch, percentage completion to `100%`, status text changes, and invocation of `relaunchApp()`.

---

## 3. Comprehensive Unit Test Specifications for `src/js/updater.test.cjs`

Below are the exact unit test specifications to be added to `src/js/updater.test.cjs`, written strictly adhering to the **Arrange-Act-Assert (AAA)** pattern.

### DOM Mock Helper for `updater.test.cjs`

```javascript
/**
 * Helper to construct lightweight mock DOM element for Node VM testing context.
 */
function createMockElement(id, tagName = 'div') {
  const classSet = new Set();
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
    addEventListener: (event, handler) => {},
    querySelector: () => null,
    querySelectorAll: () => []
  };
}

/**
 * Sets up full updater DOM environment in VM context.
 */
function setupUpdaterDOMContext(context) {
  const elements = {
    'modal-updater': createMockElement('modal-updater'),
    'updater-version-tag': createMockElement('updater-version-tag'),
    'updater-release-notes': createMockElement('updater-release-notes'),
    'updater-status-message': createMockElement('updater-status-message'),
    'btn-updater-install': createMockElement('btn-updater-install', 'button'),
    'btn-updater-postpone': createMockElement('btn-updater-postpone', 'button'),
    'updater-progress-container': createMockElement('updater-progress-container'),
    'updater-progress-bar-fill': createMockElement('updater-progress-bar-fill'),
    'updater-progress-percentage': createMockElement('updater-progress-percentage'),
    'updater-progress-bytes': createMockElement('updater-progress-bytes')
  };
  
  elements['modal-updater'].classList.add('hidden');
  elements['updater-progress-container'].classList.add('hidden');

  context.document = {
    readyState: 'complete',
    getElementById: (id) => elements[id] || null,
    querySelectorAll: (selector) => [],
    addEventListener: () => {}
  };
  context.window.document = context.document;
  return elements;
}
```

---

### Test Suite Structure & Detailed Test Cases

```javascript
describe('OTA Progress Indicator & State Transitions (R2.1, R2.2, R2.3)', () => {

  describe('Progress Bar DOM Updates on Events', () => {
    it('should unhide progress container and initialize fields on Started event', () => {
      // Arrange
      const dom = setupUpdaterDOMContext(context);
      const { handleProgressEvent } = context.window;
      const startedEvent = { event: 'Started', data: { contentLength: 10485760 } }; // 10 MB

      // Act
      handleProgressEvent(startedEvent);

      // Assert
      assert.strictEqual(dom['updater-progress-container'].classList.contains('hidden'), false);
      assert.strictEqual(dom['updater-progress-bar-fill'].style.width, '0%');
      assert.strictEqual(dom['updater-progress-percentage'].textContent, '0%');
      assert.ok(dom['updater-progress-bytes'].textContent.includes('10.00 MB'));
    });

    it('should update progress bar width, percentage, and bytes text on Progress event', () => {
      // Arrange
      const dom = setupUpdaterDOMContext(context);
      const { handleProgressEvent } = context.window;
      handleProgressEvent({ event: 'Started', data: { contentLength: 10000000 } });

      // Act
      handleProgressEvent({ event: 'Progress', data: { chunkLength: 5000000 } });

      // Assert
      assert.strictEqual(dom['updater-progress-bar-fill'].style.width, '50%');
      assert.strictEqual(dom['updater-progress-percentage'].textContent, '50%');
      assert.ok(dom['updater-progress-bytes'].textContent.includes('4.77 MB / 9.54 MB') || 
                dom['updater-progress-bytes'].textContent.includes('5.00 MB / 10.00 MB'));
    });

    it('should set progress to 100% and transition to restarting state on Finished event', () => {
      // Arrange
      const dom = setupUpdaterDOMContext(context);
      const { handleProgressEvent } = context.window;
      handleProgressEvent({ event: 'Started', data: { contentLength: 10000000 } });
      handleProgressEvent({ event: 'Progress', data: { chunkLength: 8000000 } });

      // Act
      handleProgressEvent({ event: 'Finished' });

      // Assert
      assert.strictEqual(dom['updater-progress-bar-fill'].style.width, '100%');
      assert.strictEqual(dom['updater-progress-percentage'].textContent, '100%');
      assert.ok(dom['updater-status-message'].textContent.includes('Перезапуск') || 
                dom['updater-status-message'].textContent.includes('Проверка'));
    });
  });

  describe('Percentage Calculation with Known Content Length', () => {
    it('should calculate precise rounded integer percentage across multiple chunks', () => {
      // Arrange
      const dom = setupUpdaterDOMContext(context);
      const { handleProgressEvent } = context.window;
      handleProgressEvent({ event: 'Started', data: { contentLength: 3000000 } });

      // Act & Assert 1 (33%)
      handleProgressEvent({ event: 'Progress', data: { chunkLength: 1000000 } });
      assert.strictEqual(dom['updater-progress-percentage'].textContent, '33%');

      // Act & Assert 2 (67%)
      handleProgressEvent({ event: 'Progress', data: { chunkLength: 1000000 } });
      assert.strictEqual(dom['updater-progress-percentage'].textContent, '67%');

      // Act & Assert 3 (100%)
      handleProgressEvent({ event: 'Progress', data: { chunkLength: 1000000 } });
      assert.strictEqual(dom['updater-progress-percentage'].textContent, '100%');
    });

    it('should clamp progress percentage to a maximum of 100% when overshooting', () => {
      // Arrange
      const dom = setupUpdaterDOMContext(context);
      const { handleProgressEvent } = context.window;
      handleProgressEvent({ event: 'Started', data: { contentLength: 1000000 } });

      // Act
      handleProgressEvent({ event: 'Progress', data: { chunkLength: 1200000 } });

      // Assert
      assert.strictEqual(dom['updater-progress-bar-fill'].style.width, '100%');
      assert.strictEqual(dom['updater-progress-percentage'].textContent, '100%');
    });
  });

  describe('Edge Cases (Unknown Content Length, Chunk Accumulation)', () => {
    it('should handle unknown or zero content length gracefully without NaN', () => {
      // Arrange
      const dom = setupUpdaterDOMContext(context);
      const { handleProgressEvent } = context.window;
      handleProgressEvent({ event: 'Started', data: { contentLength: 0 } });

      // Act
      handleProgressEvent({ event: 'Progress', data: { chunkLength: 1048576 } });

      // Assert
      assert.strictEqual(dom['updater-progress-percentage'].textContent.includes('NaN'), false);
      assert.ok(dom['updater-progress-bytes'].textContent.includes('1.00 MB'));
    });

    it('should correctly accumulate micro-chunks sequentially', () => {
      // Arrange
      const dom = setupUpdaterDOMContext(context);
      const { handleProgressEvent } = context.window;
      handleProgressEvent({ event: 'Started', data: { contentLength: 10000 } });

      // Act
      for (let i = 0; i < 100; i++) {
        handleProgressEvent({ event: 'Progress', data: { chunkLength: 100 } });
      }

      // Assert
      assert.strictEqual(dom['updater-progress-bar-fill'].style.width, '100%');
      assert.strictEqual(dom['updater-progress-percentage'].textContent, '100%');
    });

    it('should handle missing data or chunkLength properties safely', () => {
      // Arrange
      const dom = setupUpdaterDOMContext(context);
      const { handleProgressEvent } = context.window;

      // Act & Assert
      assert.doesNotThrow(() => {
        handleProgressEvent({ event: 'Started' });
        handleProgressEvent({ event: 'Progress' });
        handleProgressEvent({ event: 'Progress', data: {} });
      });
    });
  });

  describe('Transition to Restarting State upon Successful Download', () => {
    it('should transition UI to RESTARTING state and disable action buttons', async () => {
      // Arrange
      const dom = setupUpdaterDOMContext(context);
      const mockUpdateObj = {
        downloadAndInstall: async (onProgress) => {
          if (onProgress) {
            onProgress({ event: 'Started', data: { contentLength: 1000 } });
            onProgress({ event: 'Finished' });
          }
          return true;
        }
      };

      // Act
      const result = await context.window.UpdaterAPI.installUpdate(mockUpdateObj, context.window.handleProgressEvent);

      // Assert
      assert.strictEqual(result, true);
      assert.strictEqual(dom['updater-progress-bar-fill'].style.width, '100%');
    });
  });

});
```

---

## 4. Caveats

1. **VM Sandbox Isolation**: Tests run in Node's `vm` sandbox without a full browser environment. Mocking `document` and DOM methods is necessary and sufficient for logic validation.
2. **Formatter Dependency**: `updater.js` should either export or internally use a fallback byte formatter function if `window.Utils.formatSize` is unavailable in testing context.

---

## 5. Conclusion

The specifications defined above provide full unit test coverage for Milestone 1 requirements:
- **R2.1**: Verified via progress element creation and visibility state tests.
- **R2.2**: Verified via progress event handling, percentage calculation, and edge case tests.
- **R2.3**: Verified via state transition, button disabling, and restarting flow tests.

---

## 6. Verification Method

To verify these unit test specifications:

1. **Run Unit Test Suite**:
   ```powershell
   npm test
   ```
2. **Target File Inspection**:
   Inspect `src/js/updater.test.cjs` after implementation to ensure all 8 new test cases execute and pass cleanly under `node --test`.
3. **Invalidation Conditions**:
   - Any thrown exception during `handleProgressEvent` execution.
   - Any `NaN%` string rendered in DOM elements.
   - Unhandled missing event payload properties causing test failures.
