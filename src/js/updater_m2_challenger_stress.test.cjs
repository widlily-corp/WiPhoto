const { describe, it } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

// ═════════════════════════════════════════════════════════════════════════════
// EMPIRICAL CHALLENGER STRESS HARNESS FOR MILESTONE 2 (R1.1, R1.2, R1.3)
// ═════════════════════════════════════════════════════════════════════════════

function createFullMockDOM() {
  const elements = {};
  const listeners = {
    document: {},
    window: {}
  };

  class MockElement {
    constructor(id, tagName = 'DIV') {
      this.id = id;
      this.tagName = tagName.toUpperCase();
      this.textContent = '';
      this.innerHTML = '';
      this.style = {};
      this.disabled = false;
      this.classListSet = new Set();
      this.elementListeners = {};
      this.attributes = {};
    }

    get classList() {
      const self = this;
      return {
        add: (...cls) => cls.forEach(c => c && self.classListSet.add(c)),
        remove: (...cls) => cls.forEach(c => c && self.classListSet.delete(c)),
        contains: (c) => self.classListSet.has(c),
        toggle: (c, force) => {
          if (force === undefined) {
            self.classListSet.has(c) ? self.classListSet.delete(c) : self.classListSet.add(c);
          } else if (force) {
            self.classListSet.add(c);
          } else {
            self.classListSet.delete(c);
          }
        }
      };
    }

    setAttribute(name, val) { this.attributes[name] = String(val); }
    getAttribute(name) { return this.attributes[name] || null; }

    addEventListener(event, handler) {
      if (!this.elementListeners[event]) this.elementListeners[event] = [];
      this.elementListeners[event].push(handler);
    }

    removeEventListener(event, handler) {
      if (this.elementListeners[event]) {
        this.elementListeners[event] = this.elementListeners[event].filter(h => h !== handler);
      }
    }

    dispatchEvent(evt) {
      const type = typeof evt === 'string' ? evt : evt.type;
      const handlers = this.elementListeners[type] || [];
      for (const h of handlers) {
        h(evt);
      }
    }

    click() {
      if (!this.disabled) {
        this.dispatchEvent({ type: 'click', preventDefault: () => {} });
      }
    }
  }

  const getEl = (id, tagName = 'DIV') => {
    if (!elements[id]) {
      elements[id] = new MockElement(id, tagName);
    }
    return elements[id];
  };

  // Build required DOM tree for OTA updater
  const modal = getEl('modal-updater');
  modal.classList.add('hidden');

  getEl('updater-version-tag');
  getEl('updater-release-notes');
  const statusMsg = getEl('updater-status-message');
  statusMsg.classList.add('hidden');

  const errContainer = getEl('updater-error-container');
  errContainer.classList.add('hidden');
  getEl('updater-error-badge');
  getEl('updater-error-title');
  getEl('updater-error-message');

  getEl('btn-updater-install', 'BUTTON');
  getEl('btn-updater-postpone', 'BUTTON');

  const progressContainer = getEl('updater-progress-container');
  progressContainer.classList.add('hidden');
  getEl('updater-progress-bar-fill');
  getEl('updater-progress-percentage');
  getEl('updater-progress-bytes');

  const closeBtn1 = new MockElement('close-btn-1', 'BUTTON');
  closeBtn1.setAttribute('data-close', 'modal-updater');

  const closeBtn2 = new MockElement('close-btn-2', 'SPAN');
  closeBtn2.setAttribute('data-close', 'modal-updater');

  const doc = {
    readyState: 'complete',
    getElementById: (id) => getEl(id),
    querySelectorAll: (sel) => {
      if (sel === '[data-close="modal-updater"]') {
        return [closeBtn1, closeBtn2];
      }
      return [];
    },
    addEventListener: (event, handler) => {
      if (!listeners.document[event]) listeners.document[event] = [];
      listeners.document[event].push(handler);
    },
    removeEventListener: (event, handler) => {
      if (listeners.document[event]) {
        listeners.document[event] = listeners.document[event].filter(h => h !== handler);
      }
    },
    dispatchEvent: (evt) => {
      const type = typeof evt === 'string' ? evt : evt.type;
      const handlers = listeners.document[type] || [];
      for (const h of handlers) {
        h(evt);
      }
    }
  };

  const win = {
    document: doc,
    navigator: { onLine: true },
    addEventListener: (event, handler) => {
      if (!listeners.window[event]) listeners.window[event] = [];
      listeners.window[event].push(handler);
    },
    dispatchEvent: (evt) => {
      const type = typeof evt === 'string' ? evt : evt.type;
      const handlers = listeners.window[type] || [];
      for (const h of handlers) {
        h(evt);
      }
    }
  };

  return { elements, closeBtn1, closeBtn2, doc, win, listeners };
}

function loadUpdaterModule(domObj) {
  const moduleObj = { exports: {} };
  const context = {
    window: domObj.win,
    document: domObj.doc,
    navigator: domObj.win.navigator,
    module: moduleObj,
    exports: moduleObj.exports,
    console: console,
    setTimeout: setTimeout,
    clearTimeout: clearTimeout
  };
  context.self = context.window;

  const updaterPath = path.join(__dirname, 'updater.js');
  const updaterCode = fs.readFileSync(updaterPath, 'utf8');
  vm.runInNewContext(updaterCode, context);

  return {
    context,
    exports: moduleObj.exports || context.window
  };
}

describe('Empirical Challenger: Milestone 2 Stress & Boundary Harness', () => {

  describe('Verification Task 1: Modal Dismissal, Recovery Reset, & ESC Key Listener Behavior', () => {

    it('1.1: ESC keydown during ERROR state hides modal and resets state to IDLE', () => {
      // Arrange
      const dom = createFullMockDOM();
      const { exports } = loadUpdaterModule(dom);
      exports.initUpdaterUI();

      exports.showUpdateModal({ version: '5.1.0', body: 'Notes' });
      exports.setUpdaterState(exports.UPDATER_STATES.ERROR, { message: 'Network Timeout' });

      assert.strictEqual(exports.getUpdaterState(), 'ERROR');
      assert.strictEqual(dom.elements['modal-updater'].classList.contains('hidden'), false);
      assert.strictEqual(dom.elements['updater-error-container'].classList.contains('hidden'), false);
      assert.strictEqual(dom.elements['btn-updater-install'].textContent, 'Повторить');
      assert.strictEqual(dom.elements['btn-updater-install'].classList.contains('btn-retry'), true);

      // Act: Press ESC
      dom.doc.dispatchEvent({ type: 'keydown', key: 'Escape' });

      // Assert
      assert.strictEqual(dom.elements['modal-updater'].classList.contains('hidden'), true, 'Modal should be hidden after ESC');
      assert.strictEqual(exports.getUpdaterState(), 'IDLE', 'State should be reset to IDLE');
      assert.strictEqual(dom.elements['updater-error-container'].classList.contains('hidden'), true, 'Error container should be hidden');
      assert.strictEqual(dom.elements['updater-error-message'].textContent, '', 'Error message text should be cleared');
      assert.strictEqual(dom.elements['updater-status-message'].textContent, '', 'Status message text should be cleared');
      assert.strictEqual(dom.elements['btn-updater-install'].textContent, 'Обновить сейчас', 'Install button text reset');
      assert.strictEqual(dom.elements['btn-updater-install'].classList.contains('btn-retry'), false, '.btn-retry removed');
      assert.strictEqual(dom.elements['btn-updater-install'].disabled, false, 'Install button enabled');
      assert.strictEqual(dom.elements['btn-updater-postpone'].disabled, false, 'Postpone button enabled');
    });

    it('1.2: ESC keydown during DOWNLOADING state is IGNORED (modal remains open)', () => {
      // Arrange
      const dom = createFullMockDOM();
      const { exports } = loadUpdaterModule(dom);
      exports.initUpdaterUI();

      exports.showUpdateModal({ version: '5.1.0', body: 'Notes' });
      exports.setUpdaterState(exports.UPDATER_STATES.DOWNLOADING);

      assert.strictEqual(exports.getUpdaterState(), 'DOWNLOADING');
      assert.strictEqual(dom.elements['modal-updater'].classList.contains('hidden'), false);

      // Act: Press ESC while downloading
      dom.doc.dispatchEvent({ type: 'keydown', key: 'Escape' });

      // Assert
      assert.strictEqual(dom.elements['modal-updater'].classList.contains('hidden'), false, 'Modal MUST remain open during download');
      assert.strictEqual(exports.getUpdaterState(), 'DOWNLOADING', 'State MUST remain DOWNLOADING');
    });

    it('1.3: ESC keydown during VERIFYING state is IGNORED (modal remains open)', () => {
      // Arrange
      const dom = createFullMockDOM();
      const { exports } = loadUpdaterModule(dom);
      exports.initUpdaterUI();

      exports.showUpdateModal({ version: '5.1.0', body: 'Notes' });
      exports.setUpdaterState(exports.UPDATER_STATES.VERIFYING);

      assert.strictEqual(exports.getUpdaterState(), 'VERIFYING');

      // Act: Press ESC while verifying checksum
      dom.doc.dispatchEvent({ type: 'keydown', key: 'Escape' });

      // Assert
      assert.strictEqual(dom.elements['modal-updater'].classList.contains('hidden'), false, 'Modal MUST remain open during verifying');
      assert.strictEqual(exports.getUpdaterState(), 'VERIFYING', 'State MUST remain VERIFYING');
    });

    it('1.4: Postpone button click during ERROR state hides modal and resets state to IDLE', () => {
      // Arrange
      const dom = createFullMockDOM();
      const { exports } = loadUpdaterModule(dom);
      exports.initUpdaterUI();

      exports.showUpdateModal({ version: '5.1.0', body: 'Notes' });
      exports.setUpdaterState(exports.UPDATER_STATES.ERROR, { message: 'Checksum failed' });

      // Act: Click postpone button
      dom.elements['btn-updater-postpone'].click();

      // Assert
      assert.strictEqual(dom.elements['modal-updater'].classList.contains('hidden'), true);
      assert.strictEqual(exports.getUpdaterState(), 'IDLE');
      assert.strictEqual(dom.elements['btn-updater-install'].textContent, 'Обновить сейчас');
    });

    it('1.5: Close button (data-close="modal-updater") click during ERROR state hides modal and resets state to IDLE', () => {
      // Arrange
      const dom = createFullMockDOM();
      const { exports } = loadUpdaterModule(dom);
      exports.initUpdaterUI();

      exports.showUpdateModal({ version: '5.1.0', body: 'Notes' });
      exports.setUpdaterState(exports.UPDATER_STATES.ERROR, { message: 'Server 500 Error' });

      // Act: Click first close button
      dom.closeBtn1.click();

      // Assert
      assert.strictEqual(dom.elements['modal-updater'].classList.contains('hidden'), true);
      assert.strictEqual(exports.getUpdaterState(), 'IDLE');

      // Re-trigger error and click second close button
      exports.showUpdateModal({ version: '5.1.0' });
      exports.setUpdaterState(exports.UPDATER_STATES.ERROR, { message: 'Server 502 Error' });
      dom.closeBtn2.click();

      assert.strictEqual(dom.elements['modal-updater'].classList.contains('hidden'), true);
      assert.strictEqual(exports.getUpdaterState(), 'IDLE');
    });

    it('1.6: Buttons (install, postpone, close) state verification during DOWNLOADING vs ERROR vs IDLE', () => {
      // Arrange
      const dom = createFullMockDOM();
      const { exports } = loadUpdaterModule(dom);
      exports.initUpdaterUI();

      // Phase 1: DOWNLOADING -> buttons disabled
      exports.setUpdaterState(exports.UPDATER_STATES.DOWNLOADING);
      assert.strictEqual(dom.elements['btn-updater-install'].disabled, true, 'Install button disabled during download');
      assert.strictEqual(dom.elements['btn-updater-postpone'].disabled, true, 'Postpone button disabled during download');
      assert.strictEqual(dom.closeBtn1.disabled, true, 'Close button disabled during download');

      // Phase 2: ERROR -> buttons re-enabled
      exports.setUpdaterState(exports.UPDATER_STATES.ERROR, { message: 'Disconnect' });
      assert.strictEqual(dom.elements['btn-updater-install'].disabled, false, 'Install/Retry button enabled during error');
      assert.strictEqual(dom.elements['btn-updater-postpone'].disabled, false, 'Postpone button re-enabled during error');
      assert.strictEqual(dom.closeBtn1.disabled, false, 'Close button re-enabled during error');

      // Phase 3: IDLE -> buttons enabled
      exports.hideUpdateModal();
      assert.strictEqual(dom.elements['btn-updater-install'].disabled, false);
      assert.strictEqual(dom.elements['btn-updater-postpone'].disabled, false);
      assert.strictEqual(dom.closeBtn1.disabled, false);
    });
  });

  describe('Verification Task 2: 500-Cycle Open/Error/Close Stress & Memory Cleanup Test', () => {

    it('2.1: 500 rapid open -> error -> ESC/postpone/close cycles maintain strict state invariants without pollution', () => {
      // Arrange
      const dom = createFullMockDOM();
      const { exports } = loadUpdaterModule(dom);
      exports.initUpdaterUI();

      const dismissMethods = ['ESC', 'POSTPONE', 'CLOSE1', 'CLOSE2', 'HIDE_API'];

      // Act: Execute 500 cycles
      for (let i = 1; i <= 500; i++) {
        // Step 1: Open modal
        exports.showUpdateModal({
          version: `5.${i}.0`,
          body: `Release note content for cycle ${i}`
        });
        assert.strictEqual(dom.elements['modal-updater'].classList.contains('hidden'), false);
        assert.strictEqual(exports.getUpdaterState(), 'UPDATE_AVAILABLE');

        // Step 2: Trigger error
        const errType = (i % 4 === 0) ? 'OFFLINE' : (i % 4 === 1) ? 'TIMEOUT' : (i % 4 === 2) ? 'SERVER_ERROR' : 'SIGNATURE_ERROR';
        const classified = exports.classifyError(errType.toLowerCase());
        exports.setUpdaterState(exports.UPDATER_STATES.ERROR, { classified });

        assert.strictEqual(exports.getUpdaterState(), 'ERROR');
        assert.strictEqual(dom.elements['updater-error-container'].classList.contains('hidden'), false);
        assert.strictEqual(dom.elements['btn-updater-install'].textContent, 'Повторить');
        assert.strictEqual(dom.elements['btn-updater-install'].classList.contains('btn-retry'), true);

        // Step 3: Dismiss using rotating method
        const method = dismissMethods[i % dismissMethods.length];
        switch (method) {
          case 'ESC':
            dom.doc.dispatchEvent({ type: 'keydown', key: 'Escape' });
            break;
          case 'POSTPONE':
            dom.elements['btn-updater-postpone'].click();
            break;
          case 'CLOSE1':
            dom.closeBtn1.click();
            break;
          case 'CLOSE2':
            dom.closeBtn2.click();
            break;
          case 'HIDE_API':
            exports.hideUpdateModal();
            break;
        }

        // Assert Step 4: Full reset verified after every single iteration
        assert.strictEqual(dom.elements['modal-updater'].classList.contains('hidden'), true, `Modal should be hidden after cycle ${i}`);
        assert.strictEqual(exports.getUpdaterState(), 'IDLE', `State should be IDLE after cycle ${i}`);
        assert.strictEqual(dom.elements['updater-error-container'].classList.contains('hidden'), true, `Error container hidden after cycle ${i}`);
        assert.strictEqual(dom.elements['updater-error-message'].textContent, '', `Error message empty after cycle ${i}`);
        assert.strictEqual(dom.elements['updater-status-message'].textContent, '', `Status message empty after cycle ${i}`);
        assert.strictEqual(dom.elements['updater-status-message'].classList.contains('updater-status-error'), false, `Error CSS class removed after cycle ${i}`);
        assert.strictEqual(dom.elements['btn-updater-install'].textContent, 'Обновить сейчас', `Button text reset after cycle ${i}`);
        assert.strictEqual(dom.elements['btn-updater-install'].classList.contains('btn-retry'), false, `Retry class removed after cycle ${i}`);
        assert.strictEqual(dom.elements['btn-updater-install'].disabled, false);
        assert.strictEqual(dom.elements['btn-updater-postpone'].disabled, false);
        assert.strictEqual(dom.closeBtn1.disabled, false);
      }
    });

    it('2.2: Interleaved error retry -> download failure -> recovery dismissal flow', async () => {
      // Arrange
      const dom = createFullMockDOM();
      const { exports } = loadUpdaterModule(dom);
      exports.initUpdaterUI();

      let attempts = 0;
      const failingUpdateObj = {
        downloadAndInstall: async () => {
          attempts++;
          throw new Error('Connection reset by peer');
        }
      };

      // Open modal
      exports.showUpdateModal({ version: '5.2.0' });

      // Click install -> fails
      await exports.UpdaterAPI.installUpdate(failingUpdateObj);
      assert.strictEqual(attempts, 1);
      assert.strictEqual(exports.getUpdaterState(), 'ERROR');
      assert.strictEqual(dom.elements['btn-updater-install'].textContent, 'Повторить');

      // Click retry ("Повторить") -> fails again
      await exports.UpdaterAPI.installUpdate(failingUpdateObj);
      assert.strictEqual(attempts, 2);
      assert.strictEqual(exports.getUpdaterState(), 'ERROR');

      // Decide to postpone -> ESC key
      dom.doc.dispatchEvent({ type: 'keydown', key: 'Escape' });

      // Assert
      assert.strictEqual(dom.elements['modal-updater'].classList.contains('hidden'), true);
      assert.strictEqual(exports.getUpdaterState(), 'IDLE');
    });

  });

});
