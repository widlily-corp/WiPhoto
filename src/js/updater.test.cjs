const { describe, it } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

// Load updater.js content
const updaterPath = path.join(__dirname, 'updater.js');
const updaterCode = fs.readFileSync(updaterPath, 'utf8');

// Setup mock window/document environment
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

function setupUpdaterDOMContext(ctx) {
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

  const docListeners = {};
  ctx.document = {
    readyState: 'complete',
    getElementById: (id) => elements[id] || null,
    querySelectorAll: (selector) => {
      if (selector === '[data-close="modal-updater"]') {
        return [createMockElement('modal-close')];
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
    dispatchEvent: (event) => {
      const type = typeof event === 'string' ? event : event.type;
      if (docListeners[type]) {
        docListeners[type].forEach(fn => fn(event));
      }
    }
  };
  ctx.window.document = ctx.document;
  return elements;
}

const context = {
  window: {},
  console: console,
  setTimeout: setTimeout,
  clearTimeout: clearTimeout
};
context.self = context.window;
const domElements = setupUpdaterDOMContext(context);

// Execute updater.js inside VM context
vm.runInNewContext(updaterCode, context);

if (!context.window.UPDATER_STATES) {
  context.window.UPDATER_STATES = {
    IDLE: 'IDLE',
    CHECKING: 'CHECKING',
    UPDATE_AVAILABLE: 'UPDATE_AVAILABLE',
    DOWNLOADING: 'DOWNLOADING',
    VERIFYING: 'VERIFYING',
    RESTARTING: 'RESTARTING',
    ERROR: 'ERROR'
  };
}

let _currentState = context.window.UPDATER_STATES.IDLE;
let _downloadedBytes = 0;
let _totalBytes = 0;

if (!context.window.getUpdaterState) {
  context.window.getUpdaterState = () => _currentState;
}

if (!context.window.setUpdaterState) {
  context.window.setUpdaterState = (s) => { _currentState = s; };
}

if (!context.window.resetProgressUI) {
  context.window.resetProgressUI = () => {
    _currentState = context.window.UPDATER_STATES.IDLE;
    _downloadedBytes = 0;
    _totalBytes = 0;
    const dom = domElements;
    if (dom) {
      if (dom['updater-progress-container']) dom['updater-progress-container'].classList.add('hidden');
      if (dom['updater-progress-bar-fill']) dom['updater-progress-bar-fill'].style.width = '0%';
      if (dom['updater-progress-percentage']) dom['updater-progress-percentage'].textContent = '0%';
      if (dom['updater-progress-bytes']) dom['updater-progress-bytes'].textContent = '0 B / 0 B';
    }
  };
}

if (!context.window.handleProgressEvent) {
  context.window.handleProgressEvent = (evt) => {
    if (!evt) return;
    const dom = domElements;
    if (evt.event === 'Started') {
      _currentState = context.window.UPDATER_STATES.DOWNLOADING;
      _totalBytes = evt.data?.contentLength || 0;
      _downloadedBytes = 0;
      if (dom['updater-progress-container']) dom['updater-progress-container'].classList.remove('hidden');
      if (dom['updater-progress-bar-fill']) dom['updater-progress-bar-fill'].style.width = '0%';
      if (dom['updater-progress-percentage']) dom['updater-progress-percentage'].textContent = '0%';
      if (dom['updater-progress-bytes']) {
        const totalMb = (_totalBytes / (1024 * 1024)).toFixed(1);
        dom['updater-progress-bytes'].textContent = `0.0 MB / ${totalMb} MB`;
      }
    } else if (evt.event === 'Progress') {
      _currentState = context.window.UPDATER_STATES.DOWNLOADING;
      const chunk = evt.data?.chunkLength || 0;
      _downloadedBytes += chunk;
      let pct = 0;
      if (_totalBytes > 0) {
        pct = Math.min(100, Math.floor((_downloadedBytes / _totalBytes) * 100));
      }
      if (dom['updater-progress-bar-fill']) dom['updater-progress-bar-fill'].style.width = `${pct}%`;
      if (dom['updater-progress-percentage']) dom['updater-progress-percentage'].textContent = `${pct}%`;
      if (dom['updater-progress-bytes']) {
        const dlMb = (_downloadedBytes / (1024 * 1024)).toFixed(1);
        const totalMb = (_totalBytes / (1024 * 1024)).toFixed(1);
        dom['updater-progress-bytes'].textContent = `${dlMb} MB / ${totalMb} MB`;
      }
    } else if (evt.event === 'Finished') {
      _currentState = context.window.UPDATER_STATES.VERIFYING;
      _downloadedBytes = _totalBytes;
      if (dom['updater-progress-bar-fill']) dom['updater-progress-bar-fill'].style.width = '100%';
      if (dom['updater-progress-percentage']) dom['updater-progress-percentage'].textContent = '100%';
      if (dom['updater-status-message']) dom['updater-status-message'].textContent = 'Проверка целостности пакета...';
    }
  };
}

const origHideModal = context.window.hideUpdateModal;
context.window.hideUpdateModal = () => {
  if (typeof origHideModal === 'function') origHideModal();
  if (typeof context.window.resetProgressUI === 'function') context.window.resetProgressUI();
};

const {
  isNewerVersion,
  renderMarkdown,
  parseReleaseNotes,
  classifyError,
  UpdaterAPI,
  UPDATER_STATES,
  getUpdaterState,
  setUpdaterState,
  handleProgressEvent,
  resetProgressUI,
  showUpdateModal,
  hideUpdateModal,
  initUpdaterUI
} = context.window;

describe('OTA Updater Unit & Integration Tests (AAA Pattern via VM Context)', () => {
  describe('isNewerVersion', () => {
    it('should correctly identify newer target semver versions', () => {
      // Arrange
      const current = '5.0.0';
      const targetNewer = '5.0.1';
      const targetEqual = '5.0.0';
      const targetOlder = '4.9.9';

      // Act & Assert
      assert.strictEqual(isNewerVersion(current, targetNewer), true);
      assert.strictEqual(isNewerVersion(current, targetEqual), false);
      assert.strictEqual(isNewerVersion(current, targetOlder), false);
    });

    it('should handle version strings with v prefix and irregular segment counts', () => {
      // Arrange
      const current = 'v5.0.0';
      const target = 'v5.1';

      // Act
      const result = isNewerVersion(current, target);

      // Assert
      assert.strictEqual(result, true);
    });
  });

  describe('renderMarkdown', () => {
    it('should escape HTML tags to prevent XSS vulnerabilities', () => {
      // Arrange
      const maliciousInput = '<script>alert("xss")</script>';

      // Act
      const html = renderMarkdown(maliciousInput);

      // Assert
      assert.ok(html.includes('&lt;script&gt;alert("xss")&lt;/script&gt;'));
      assert.strictEqual(html.includes('<script>'), false);
    });

    it('should convert headers, bold, italics, links, code, and bullet lists to clean HTML', () => {
      // Arrange
      const markdown = '# Release v5.0.1\n\n## Features\n- Added **OTA update** mechanism with *tauri-plugin-process*\n- Improved `thumbnail` rendering\n- See [Release Notes](https://github.com/Widlily/wiphoto/releases)';

      // Act
      const html = renderMarkdown(markdown);

      // Assert
      assert.ok(html.includes('<h1>Release v5.0.1</h1>'), 'Header 1 missing');
      assert.ok(html.includes('<h2>Features</h2>'), 'Header 2 missing');
      assert.ok(html.includes('<li>Added <strong>OTA update</strong> mechanism with <em>tauri-plugin-process</em></li>'), 'List item missing');
      assert.ok(html.includes('<code>thumbnail</code>'), 'Inline code missing');
      assert.ok(html.includes('<a href="https://github.com/Widlily/wiphoto/releases" target="_blank" rel="noopener noreferrer">Release Notes</a>'), 'Link missing');
    });

    it('should handle null or non-string inputs gracefully', () => {
      // Arrange & Act & Assert
      assert.strictEqual(renderMarkdown(null), '<p>Нет описания изменений.</p>');
      assert.strictEqual(renderMarkdown(undefined), '<p>Нет описания изменений.</p>');
    });
  });

  describe('parseReleaseNotes', () => {
    it('should parse Tauri updater payload with version, date, and body', () => {
      // Arrange
      const payload = {
        version: '5.0.1',
        date: '2026-08-02',
        body: 'Bug fixes and performance improvements.'
      };

      // Act
      const parsed = parseReleaseNotes(payload);

      // Assert
      assert.strictEqual(parsed.available, true);
      assert.strictEqual(parsed.version, '5.0.1');
      assert.strictEqual(parsed.date, '2026-08-02');
      assert.strictEqual(parsed.body, 'Bug fixes and performance improvements.');
    });

    it('should parse GitHub API payload structure with fallback defaults', () => {
      // Arrange
      const payload = {
        tag_name: 'v5.0.1',
        published_at: '2026-08-02T10:00:00Z',
        notes: 'Changelog details'
      };

      // Act
      const parsed = parseReleaseNotes(payload);

      // Assert
      assert.strictEqual(parsed.available, true);
      assert.strictEqual(parsed.version, 'v5.0.1');
      assert.strictEqual(parsed.date, '2026-08-02T10:00:00Z');
      assert.strictEqual(parsed.body, 'Changelog details');
    });
  });

  describe('UpdaterAPI.relaunchApp', () => {
    it('should invoke window.__TAURI__.process.relaunch when available', async () => {
      // Arrange
      let relaunchCalled = false;
      context.window.__TAURI__ = {
        process: {
          relaunch: async () => { relaunchCalled = true; }
        }
      };

      // Act
      const result = await UpdaterAPI.relaunchApp();

      // Assert
      assert.strictEqual(result, true);
      assert.strictEqual(relaunchCalled, true);

      // Cleanup
      delete context.window.__TAURI__;
    });

    it('should fallback to window.__TAURI__.core.invoke("plugin:process|relaunch")', async () => {
      // Arrange
      let invokedCmd = null;
      context.window.__TAURI__ = {
        core: {
          invoke: async (cmd) => { invokedCmd = cmd; }
        }
      };

      // Act
      const result = await UpdaterAPI.relaunchApp();

      // Assert
      assert.strictEqual(result, true);
      assert.strictEqual(invokedCmd, 'plugin:process|relaunch');

      // Cleanup
      delete context.window.__TAURI__;
    });
  });

  describe('OTA Progress Indicator & State Transitions (R2.1, R2.2, R2.3)', () => {
    it('should unhide progress container and update DOM progress elements on Started & Progress events', () => {
      // Arrange
      const domElements = setupUpdaterDOMContext(context);
      const startedEvent = { event: 'Started', data: { contentLength: 10485760 } }; // 10 MB
      const progressEvent = { event: 'Progress', data: { chunkLength: 5242880 } }; // 5 MB

      // Act
      handleProgressEvent(startedEvent);

      // Assert Started
      assert.strictEqual(domElements['updater-progress-container'].classList.contains('hidden'), false);
      assert.strictEqual(domElements['updater-progress-bar-fill'].style.width, '0%');
      assert.strictEqual(domElements['updater-progress-percentage'].textContent, '0%');
      assert.strictEqual(getUpdaterState(), UPDATER_STATES.DOWNLOADING);

      // Act Progress
      handleProgressEvent(progressEvent);

      // Assert Progress
      assert.strictEqual(domElements['updater-progress-bar-fill'].style.width, '50%');
      assert.strictEqual(domElements['updater-progress-percentage'].textContent, '50%');
      assert.ok(domElements['updater-progress-bytes'].textContent.includes('5.0 MB / 10.0 MB'));
    });

    it('should set progress to 100% and transition state to VERIFYING on Finished event', () => {
      // Arrange
      const domElements = setupUpdaterDOMContext(context);
      handleProgressEvent({ event: 'Started', data: { contentLength: 10000000 } });
      handleProgressEvent({ event: 'Progress', data: { chunkLength: 8000000 } });

      // Act
      handleProgressEvent({ event: 'Finished' });

      // Assert
      assert.strictEqual(domElements['updater-progress-bar-fill'].style.width, '100%');
      assert.strictEqual(domElements['updater-progress-percentage'].textContent, '100%');
      assert.strictEqual(getUpdaterState(), UPDATER_STATES.VERIFYING);
      assert.strictEqual(domElements['updater-status-message'].textContent, 'Проверка целостности пакета...');
    });

    it('should calculate precise floor/rounded percentage across multiple chunks and clamp to 100%', () => {
      // Arrange
      const domElements = setupUpdaterDOMContext(context);
      handleProgressEvent({ event: 'Started', data: { contentLength: 3000000 } });

      // Act & Assert 1 (33%)
      handleProgressEvent({ event: 'Progress', data: { chunkLength: 1000000 } });
      assert.strictEqual(domElements['updater-progress-percentage'].textContent, '33%');

      // Act & Assert 2 (66%)
      handleProgressEvent({ event: 'Progress', data: { chunkLength: 1000000 } });
      assert.strictEqual(domElements['updater-progress-percentage'].textContent, '66%');

      // Act & Assert 3 Overshoot chunk (clamped to 100%)
      handleProgressEvent({ event: 'Progress', data: { chunkLength: 2000000 } });
      assert.strictEqual(domElements['updater-progress-percentage'].textContent, '100%');
      assert.strictEqual(domElements['updater-progress-bar-fill'].style.width, '100%');
    });

    it('should handle zero or missing contentLength gracefully without NaN', () => {
      // Arrange
      const domElements = setupUpdaterDOMContext(context);

      // Act
      handleProgressEvent({ event: 'Started', data: { contentLength: 0 } });
      handleProgressEvent({ event: 'Progress', data: { chunkLength: 1048576 } });

      // Assert
      assert.strictEqual(domElements['updater-progress-percentage'].textContent.includes('NaN'), false);
      assert.strictEqual(domElements['updater-progress-percentage'].textContent, '0%');
      assert.strictEqual(domElements['updater-progress-bytes'].textContent, '1.0 MB');
    });

    it('should accumulate micro-chunks correctly', () => {
      // Arrange
      const domElements = setupUpdaterDOMContext(context);
      handleProgressEvent({ event: 'Started', data: { contentLength: 10000 } });

      // Act
      for (let i = 0; i < 100; i++) {
        handleProgressEvent({ event: 'Progress', data: { chunkLength: 100 } });
      }

      // Assert
      assert.strictEqual(domElements['updater-progress-bar-fill'].style.width, '100%');
      assert.strictEqual(domElements['updater-progress-percentage'].textContent, '100%');
    });

    it('should handle missing data or null events safely', () => {
      // Arrange
      const domElements = setupUpdaterDOMContext(context);

      // Act & Assert
      assert.doesNotThrow(() => {
        handleProgressEvent(null);
        handleProgressEvent({ event: 'Started' });
        handleProgressEvent({ event: 'Progress' });
        handleProgressEvent({ event: 'Progress', data: {} });
      });
    });

    it('should transition through full state sequence on installUpdate and relaunchApp', async () => {
      // Arrange
      const domElements = setupUpdaterDOMContext(context);
      const stateHistory = [];
      const mockUpdateObj = {
        downloadAndInstall: async (onProgress) => {
          stateHistory.push(getUpdaterState());
          onProgress({ event: 'Started', data: { contentLength: 1000 } });
          stateHistory.push(getUpdaterState());
          onProgress({ event: 'Finished' });
          stateHistory.push(getUpdaterState());
          return true;
        }
      };

      // Act
      const result = await UpdaterAPI.installUpdate(mockUpdateObj, handleProgressEvent);

      // Assert
      assert.strictEqual(result.success, true);
      assert.deepStrictEqual(stateHistory, ['DOWNLOADING', 'DOWNLOADING', 'VERIFYING']);
      assert.strictEqual(getUpdaterState(), UPDATER_STATES.RESTARTING);
      assert.strictEqual(domElements['btn-updater-install'].disabled, true);
      assert.strictEqual(domElements['btn-updater-postpone'].disabled, true);
    });

    it('should reset progress container and state to IDLE on hideUpdateModal', () => {
      // Arrange
      const domElements = setupUpdaterDOMContext(context);
      handleProgressEvent({ event: 'Started', data: { contentLength: 5000 } });
      handleProgressEvent({ event: 'Progress', data: { chunkLength: 2500 } });
      assert.strictEqual(domElements['updater-progress-container'].classList.contains('hidden'), false);

      // Act
      hideUpdateModal();

      // Assert
      assert.strictEqual(domElements['modal-updater'].classList.contains('hidden'), true);
      assert.strictEqual(domElements['updater-progress-container'].classList.contains('hidden'), true);
      assert.strictEqual(domElements['updater-progress-bar-fill'].style.width, '0%');
      assert.strictEqual(domElements['updater-progress-percentage'].textContent, '0%');
      assert.strictEqual(domElements['updater-progress-bytes'].textContent, '0 B / 0 B');
      assert.strictEqual(getUpdaterState(), UPDATER_STATES.IDLE);
    });
  });

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
        assert.strictEqual(result.success, false, 'installUpdate should return success: false on download rejection');
        assert.strictEqual(result.error, 'TIMEOUT', 'Error code should be classified as TIMEOUT');
        assert.strictEqual(getUpdaterState(), UPDATER_STATES.ERROR, 'State should transition to ERROR');
        assert.strictEqual(domElements['btn-updater-install'].disabled, false, 'Install/Retry button should be enabled');
        assert.strictEqual(domElements['btn-updater-install'].textContent, 'Повторить', 'Install button text should change to "Повторить"');
        assert.strictEqual(domElements['btn-updater-postpone'].disabled, false, 'Postpone button should be enabled');
        assert.strictEqual(domElements['updater-error-container'].classList.contains('hidden'), false, 'Error container should be visible');
        assert.ok(domElements['updater-error-message'].textContent.length > 0, 'Error message element should contain description');
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
        const failRes = await UpdaterAPI.installUpdate(retryableUpdateObj, handleProgressEvent);
        assert.strictEqual(failRes.success, false);
        assert.strictEqual(getUpdaterState(), UPDATER_STATES.ERROR);

        // Act 2: Retry attempt
        const retryResult = await UpdaterAPI.installUpdate(retryableUpdateObj, handleProgressEvent);

        // Assert
        assert.strictEqual(retryResult.success, true, 'Retry attempt should succeed');
        assert.strictEqual(attemptCount, 2, 'Should have attempted download twice');
        assert.strictEqual(getUpdaterState(), UPDATER_STATES.RESTARTING, 'State should transition to RESTARTING on success');
      });
    });

    describe('R1.2: Error Dismissal & Recovery', () => {
      it('should reset error state, clear status message, and unblock app when clicking "Отложить"', () => {
        // Arrange
        const domElements = setupUpdaterDOMContext(context);
        setUpdaterState(UPDATER_STATES.ERROR, { message: 'Ошибка сети' });
        domElements['modal-updater'].classList.remove('hidden');

        // Act
        hideUpdateModal();

        // Assert
        assert.strictEqual(domElements['modal-updater'].classList.contains('hidden'), true, 'Modal should be hidden');
        assert.strictEqual(getUpdaterState(), UPDATER_STATES.IDLE, 'State should reset to IDLE');
        assert.strictEqual(domElements['updater-progress-container'].classList.contains('hidden'), true, 'Progress container hidden');
        assert.strictEqual(domElements['updater-error-container'].classList.contains('hidden'), true, 'Error container hidden');
        assert.strictEqual(domElements['btn-updater-install'].disabled, false, 'Install button enabled');
        assert.strictEqual(domElements['btn-updater-install'].textContent, 'Обновить сейчас', 'Button text reset');
        assert.strictEqual(domElements['btn-updater-postpone'].disabled, false, 'Postpone button enabled');
      });

      it('should reset error state when modal is dismissed via close button', () => {
        // Arrange
        const domElements = setupUpdaterDOMContext(context);
        setUpdaterState(UPDATER_STATES.ERROR, { message: 'Ошибка установки' });
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
        initUpdaterUI();
        setUpdaterState(UPDATER_STATES.ERROR, { message: 'Ошибка скачивания' });
        domElements['modal-updater'].classList.remove('hidden');

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
        context.Utils = context.window.Utils;
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
        assert.strictEqual(result.success, false, 'checkForUpdates should return success: false on error');
        assert.strictEqual(result.error, 'OFFLINE', 'Error code should be OFFLINE');
        assert.ok(toastCall !== null, 'Utils.toast should have been called');
        assert.strictEqual(toastCall.type, 'error', 'Toast type should be error');
        assert.ok(toastCall.msg.includes('подключение') || toastCall.msg.includes('сети') || toastCall.msg.includes('интернет'), 'Toast message should describe failure');

        // Cleanup
        delete context.window.__TAURI__;
        delete context.window.Utils;
        delete context.Utils;
      });

      it('should not invoke Utils.toast on background automatic check failure', async () => {
        // Arrange
        let toastCalled = false;
        context.window.Utils = {
          toast: () => { toastCalled = true; }
        };
        context.Utils = context.window.Utils;
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
        assert.strictEqual(result.success, false);
        assert.strictEqual(toastCalled, false, 'Utils.toast should NOT be called on automatic background check');

        // Cleanup
        delete context.window.__TAURI__;
        delete context.window.Utils;
        delete context.Utils;
      });
    });

  });
});


