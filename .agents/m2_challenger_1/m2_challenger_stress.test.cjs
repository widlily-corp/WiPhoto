const { describe, it } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

// Load updater.js content from project source
const updaterPath = path.join(__dirname, '..', '..', 'src', 'js', 'updater.js');
const updaterCode = fs.readFileSync(updaterPath, 'utf8');

// Helper to create mock DOM element
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
      const type = typeof event === 'string' ? event : event.type;
      if (listeners[type]) {
        listeners[type].forEach(fn => fn(event));
      }
    },
    querySelector: () => null,
    querySelectorAll: () => []
  };
}

function setupUpdaterContext() {
  const elements = {
    'modal-updater': createMockElement('modal-updater'),
    'updater-version-tag': createMockElement('updater-version-tag'),
    'updater-release-notes': createMockElement('updater-release-notes'),
    'updater-status-message': createMockElement('updater-status-message'),
    'updater-error-container': createMockElement('updater-error-container'),
    'updater-error-badge': createMockElement('updater-error-badge'),
    'updater-error-title': createMockElement('updater-error-title'),
    'updater-error-message': createMockElement('updater-error-message'),
    'btn-updater-install': createMockElement('btn-updater-install', 'button'),
    'btn-updater-postpone': createMockElement('btn-updater-postpone', 'button'),
    'updater-progress-container': createMockElement('updater-progress-container'),
    'updater-progress-bar-fill': createMockElement('updater-progress-bar-fill'),
    'updater-progress-percentage': createMockElement('updater-progress-percentage'),
    'updater-progress-bytes': createMockElement('updater-progress-bytes')
  };

  elements['modal-updater'].classList.add('hidden');
  elements['updater-progress-container'].classList.add('hidden');
  elements['updater-error-container'].classList.add('hidden');

  const closeButtons = [createMockElement('close-btn-1', 'button')];
  const docListeners = {};

  const toastCalls = [];
  const mockUtils = {
    formatSize: (bytes) => `${bytes} B`,
    toast: (msg, type) => {
      toastCalls.push({ msg, type });
    }
  };

  const context = {
    console: { log: () => {}, error: () => {}, warn: () => {} },
    setTimeout: (fn, ms) => setTimeout(fn, ms),
    clearTimeout: (id) => clearTimeout(id),
    Math,
    Number,
    String,
    Boolean,
    Object,
    Array,
    Set,
    Error,
    TypeError,
    Promise,
    navigator: { onLine: true },
    document: {
      readyState: 'complete',
      getElementById: (id) => elements[id] || null,
      querySelectorAll: (selector) => {
        if (selector === '[data-close="modal-updater"]') {
          return closeButtons;
        }
        return [];
      },
      addEventListener: (event, handler) => {
        if (!docListeners[event]) docListeners[event] = [];
        docListeners[event].push(handler);
      },
      removeEventListener: (event, handler) => {
        if (docListeners[event]) {
          docListeners[event] = docListeners[event].filter(h => h !== handler);
        }
      },
      dispatchEvent: (evt) => {
        const type = evt.key ? 'keydown' : (evt.type || evt);
        if (docListeners[type]) {
          docListeners[type].forEach(fn => fn(evt));
        }
      }
    },
    Utils: mockUtils,
    toastCalls,
    elements,
    closeButtons,
    docListeners,
    window: {
      Utils: mockUtils,
      __TAURI__: null
    }
  };

  context.window.document = context.document;
  context.window.navigator = context.navigator;

  vm.createContext(context);
  vm.runInContext(updaterCode, context);

  return context;
}

describe('M2 Challenger Empirical Stress & Edge Case Test Suite', () => {

  describe('1. Error Classification Matrix & Offline State Priority', () => {

    it('should classify timeout errors correctly', () => {
      const ctx = setupUpdaterContext();
      const timeouts = [
        'request timed out',
        'Connection timed out after 30000ms',
        'ETIMEDOUT',
        new Error('HTTP timeout during fetch')
      ];

      for (const err of timeouts) {
        const res = ctx.window.classifyError(err);
        assert.strictEqual(res.code, 'TIMEOUT');
        assert.strictEqual(res.message, 'Превышено время ожидания ответа от сервера обновлений.');
      }
    });

    it('should classify server 5xx errors correctly', () => {
      const ctx = setupUpdaterContext();
      const serverErrs = [
        'HTTP 500 Internal Server Error',
        '502 Bad Gateway',
        '503 Service Unavailable',
        new Error('Remote server error 500')
      ];

      for (const err of serverErrs) {
        const res = ctx.window.classifyError(err);
        assert.strictEqual(res.code, 'SERVER_ERROR');
        assert.strictEqual(res.message, 'Ошибка сервера обновлений (5xx). Попробуйте позже.');
      }
    });

    it('should classify 504 Gateway Timeout into TIMEOUT or SERVER_ERROR gracefully', () => {
      const ctx = setupUpdaterContext();
      const res = ctx.window.classifyError('504 Gateway Timeout');
      assert.ok(res.code === 'TIMEOUT' || res.code === 'SERVER_ERROR');
      assert.ok(res.message.length > 0);
    });

    it('should classify signature & checksum verification errors correctly', () => {
      const ctx = setupUpdaterContext();
      const sigErrs = [
        'signature verification failed',
        'invalid package checksum',
        'hash mismatch on update bundle',
        new Error('Failed to verify digital signature')
      ];

      for (const err of sigErrs) {
        const res = ctx.window.classifyError(err);
        assert.strictEqual(res.code, 'SIGNATURE_ERROR');
        assert.strictEqual(res.message, 'Ошибка проверки подлинности или целостности пакета обновления.');
      }
    });

    it('should classify network & connection drop errors correctly', () => {
      const ctx = setupUpdaterContext();
      const netErrs = [
        'Failed to fetch',
        'cannot connect to server',
        'network error',
        'no internet connection',
        new Error('Socket connection offline')
      ];

      for (const err of netErrs) {
        const res = ctx.window.classifyError(err);
        assert.strictEqual(res.code, 'OFFLINE');
        assert.strictEqual(res.message, 'Сбой сети при скачивании обновления. Проверьте подключение к интернету.');
      }
    });

    it('should prioritize navigator.onLine === false over all error strings', () => {
      const ctx = setupUpdaterContext();
      ctx.navigator.onLine = false;

      const errors = [
        'HTTP 500 Internal Server Error',
        'signature verification failed',
        'timed out',
        null,
        undefined,
        12345
      ];

      for (const err of errors) {
        const res = ctx.window.classifyError(err);
        assert.strictEqual(res.code, 'OFFLINE');
        assert.strictEqual(res.message, 'Отсутствует подключение к интернету. Проверьте сетевое соединение.');
      }
    });

    it('should handle unclassified or malformed error objects safely', () => {
      const ctx = setupUpdaterContext();
      
      const unk1 = ctx.window.classifyError('something completely unexpected');
      assert.strictEqual(unk1.code, 'UNKNOWN');
      assert.strictEqual(unk1.message, 'something completely unexpected');

      const unk2 = ctx.window.classifyError(null);
      assert.strictEqual(unk2.code, 'UNKNOWN');
      assert.strictEqual(unk2.message, 'Произошла ошибка при работе с автообновлением.');

      const unk3 = ctx.window.classifyError({ custom: 'object' });
      assert.strictEqual(unk3.code, 'UNKNOWN');
      assert.strictEqual(unk3.message, 'Произошла ошибка при работе с автообновлением.');
    });
  });

  describe('2. Toast Notification Fallbacks & Resilience', () => {

    it('should invoke Utils.toast on manual update check failure', async () => {
      const ctx = setupUpdaterContext();
      ctx.window.__TAURI__ = {
        updater: {
          check: async () => { throw new Error('Failed to fetch update manifest'); }
        }
      };

      const result = await ctx.window.UpdaterAPI.checkForUpdates({ isManual: true });
      assert.strictEqual(result.success, false);
      assert.strictEqual(result.error, 'OFFLINE');
      assert.strictEqual(ctx.toastCalls.length, 1);
      assert.strictEqual(ctx.toastCalls[0].type, 'error');
      assert.strictEqual(ctx.toastCalls[0].msg, 'Сбой сети при скачивании обновления. Проверьте подключение к интернету.');
    });

    it('should NOT invoke Utils.toast on automatic background update check failure', async () => {
      const ctx = setupUpdaterContext();
      ctx.window.__TAURI__ = {
        updater: {
          check: async () => { throw new Error('ETIMEDOUT'); }
        }
      };

      const result = await ctx.window.UpdaterAPI.checkForUpdates({ isManual: false });
      assert.strictEqual(result.success, false);
      assert.strictEqual(result.error, 'TIMEOUT');
      assert.strictEqual(ctx.toastCalls.length, 0);
    });

    it('should gracefully handle missing Utils or missing Utils.toast without throwing', async () => {
      const ctx = setupUpdaterContext();
      delete ctx.Utils;
      delete ctx.window.Utils;

      ctx.window.__TAURI__ = {
        updater: {
          check: async () => { throw new Error('500 Internal Server Error'); }
        }
      };

      let threw = false;
      try {
        const result = await ctx.window.UpdaterAPI.checkForUpdates({ isManual: true });
        assert.strictEqual(result.success, false);
        assert.strictEqual(result.error, 'SERVER_ERROR');
      } catch (e) {
        threw = true;
      }
      assert.strictEqual(threw, false, 'Should not throw when Utils.toast is missing');
    });
  });

  describe('3. Retry Mechanics & State Transitions (R1.1)', () => {

    it('should transition to ERROR state, present error container, and set primary button to "Повторить" with .btn-retry class', async () => {
      const ctx = setupUpdaterContext();
      const mockUpdate = {
        downloadAndInstall: async () => {
          throw new Error('signature verification failed');
        }
      };

      const installRes = await ctx.window.UpdaterAPI.installUpdate(mockUpdate);
      assert.strictEqual(installRes.success, false);
      assert.strictEqual(installRes.error, 'SIGNATURE_ERROR');
      assert.strictEqual(ctx.window.getUpdaterState(), ctx.window.UPDATER_STATES.ERROR);

      // Check UI updates
      assert.strictEqual(ctx.elements['updater-error-container'].classList.contains('hidden'), false);
      assert.strictEqual(ctx.elements['updater-error-message'].textContent, 'Ошибка проверки подлинности или целостности пакета обновления.');
      assert.strictEqual(ctx.elements['btn-updater-install'].textContent, 'Повторить');
      assert.strictEqual(ctx.elements['btn-updater-install'].classList.contains('btn-retry'), true);
      assert.strictEqual(ctx.elements['btn-updater-install'].disabled, false);
      assert.strictEqual(ctx.elements['btn-updater-postpone'].disabled, false);
      assert.strictEqual(ctx.closeButtons[0].disabled, false);
    });

    it('should successfully retry installation when clicking "Повторить" after error', async () => {
      const ctx = setupUpdaterContext();
      let attempt = 0;
      const mockUpdate = {
        downloadAndInstall: async (onProgress) => {
          attempt++;
          if (attempt === 1) {
            throw new Error('ETIMEDOUT');
          }
          if (onProgress) {
            onProgress({ event: 'Started', data: { contentLength: 1000 } });
            onProgress({ event: 'Finished' });
          }
          return true;
        }
      };

      // 1st attempt fails
      const res1 = await ctx.window.UpdaterAPI.installUpdate(mockUpdate);
      assert.strictEqual(res1.success, false);
      assert.strictEqual(ctx.window.getUpdaterState(), ctx.window.UPDATER_STATES.ERROR);

      // 2nd attempt succeeds
      const res2 = await ctx.window.UpdaterAPI.installUpdate(mockUpdate);
      assert.strictEqual(res2.success, true);
      assert.strictEqual(ctx.window.getUpdaterState(), ctx.window.UPDATER_STATES.RESTARTING);
    });
  });

  describe('4. Modal Dismissal & Recovery Mechanics (R1.2)', () => {

    it('should clean up error UI and state when clicking "Отложить"', async () => {
      const ctx = setupUpdaterContext();
      ctx.window.initUpdaterUI();

      // Trigger error state
      await ctx.window.UpdaterAPI.installUpdate({ downloadAndInstall: async () => { throw new Error('500 Server Error'); } });
      assert.strictEqual(ctx.window.getUpdaterState(), ctx.window.UPDATER_STATES.ERROR);

      // Click postpone
      ctx.elements['btn-updater-postpone'].click();

      // Check state reset
      assert.strictEqual(ctx.window.getUpdaterState(), ctx.window.UPDATER_STATES.IDLE);
      assert.strictEqual(ctx.elements['modal-updater'].classList.contains('hidden'), true);
      assert.strictEqual(ctx.elements['updater-error-container'].classList.contains('hidden'), true);
      assert.strictEqual(ctx.elements['updater-error-message'].textContent, '');
      assert.strictEqual(ctx.elements['btn-updater-install'].textContent, 'Обновить сейчас');
      assert.strictEqual(ctx.elements['btn-updater-install'].classList.contains('btn-retry'), false);
    });

    it('should clean up error UI and state when clicking Close button (✕)', async () => {
      const ctx = setupUpdaterContext();
      ctx.window.initUpdaterUI();

      await ctx.window.UpdaterAPI.installUpdate({ downloadAndInstall: async () => { throw new Error('Offline'); } });
      assert.strictEqual(ctx.window.getUpdaterState(), ctx.window.UPDATER_STATES.ERROR);

      ctx.closeButtons[0].click();

      assert.strictEqual(ctx.window.getUpdaterState(), ctx.window.UPDATER_STATES.IDLE);
      assert.strictEqual(ctx.elements['modal-updater'].classList.contains('hidden'), true);
      assert.strictEqual(ctx.elements['btn-updater-install'].textContent, 'Обновить сейчас');
    });

    it('should hide modal on ESC key press when in ERROR state', () => {
      const ctx = setupUpdaterContext();
      ctx.window.initUpdaterUI();

      ctx.elements['modal-updater'].classList.remove('hidden');
      ctx.window.setUpdaterState(ctx.window.UPDATER_STATES.ERROR, { message: 'Some error' });

      // Dispatch ESC key event
      ctx.document.dispatchEvent({ key: 'Escape', code: 'Escape' });

      assert.strictEqual(ctx.window.getUpdaterState(), ctx.window.UPDATER_STATES.IDLE);
      assert.strictEqual(ctx.elements['modal-updater'].classList.contains('hidden'), true);
    });

    it('should NOT hide modal on ESC key press when in DOWNLOADING or VERIFYING state', () => {
      const ctx = setupUpdaterContext();
      ctx.window.initUpdaterUI();

      ctx.elements['modal-updater'].classList.remove('hidden');
      ctx.window.setUpdaterState(ctx.window.UPDATER_STATES.DOWNLOADING);

      ctx.document.dispatchEvent({ key: 'Escape', code: 'Escape' });

      assert.strictEqual(ctx.window.getUpdaterState(), ctx.window.UPDATER_STATES.DOWNLOADING);
      assert.strictEqual(ctx.elements['modal-updater'].classList.contains('hidden'), false);

      ctx.window.setUpdaterState(ctx.window.UPDATER_STATES.VERIFYING);
      ctx.document.dispatchEvent({ key: 'Escape', code: 'Escape' });

      assert.strictEqual(ctx.window.getUpdaterState(), ctx.window.UPDATER_STATES.VERIFYING);
      assert.strictEqual(ctx.elements['modal-updater'].classList.contains('hidden'), false);
    });
  });

  describe('5. Rapid Parallel Clicks & Stress Scenarios', () => {

    it('should handle 20 rapid concurrent manual update checks cleanly', async () => {
      const ctx = setupUpdaterContext();
      ctx.window.__TAURI__ = {
        updater: {
          check: async () => {
            await new Promise(r => setTimeout(r, 10));
            throw new Error('ETIMEDOUT');
          }
        }
      };

      const promises = [];
      for (let i = 0; i < 20; i++) {
        promises.push(ctx.window.UpdaterAPI.checkForUpdates({ isManual: true }));
      }

      const results = await Promise.all(promises);
      assert.strictEqual(results.length, 20);
      for (const res of results) {
        assert.strictEqual(res.success, false);
        assert.strictEqual(res.error, 'TIMEOUT');
      }
      assert.strictEqual(ctx.toastCalls.length, 20);
    });
  });
});
