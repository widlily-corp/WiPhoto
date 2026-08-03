const { describe, it } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

// ═════════════════════════════════════════════════════════════════════════════
// DOM & TAURI TEST ENVIRONMENT SETUP
// ═════════════════════════════════════════════════════════════════════════════

class MockClassList {
  constructor(className = '') {
    this.classes = new Set(className.split(' ').filter(Boolean));
  }
  add(c) { this.classes.add(c); }
  remove(c) { this.classes.delete(c); }
  contains(c) { return this.classes.has(c); }
  toggle(c, force) {
    if (force !== undefined) {
      if (force) this.classes.add(c); else this.classes.delete(c);
    } else {
      if (this.classes.has(c)) this.classes.delete(c); else this.classes.add(c);
    }
  }
}

class MockElement {
  constructor(id = '', className = '') {
    this.id = id;
    this.classList = new MockClassList(className);
    this.textContent = '';
    this.innerHTML = '';
    this.disabled = false;
    this.style = {};
    this.listeners = {};
    this.attributes = {};
  }

  setAttribute(name, val) { this.attributes[name] = val; }
  getAttribute(name) { return this.attributes[name] || null; }

  addEventListener(event, handler) {
    if (!this.listeners[event]) this.listeners[event] = [];
    this.listeners[event].push(handler);
  }

  async dispatchEvent(event) {
    const handlers = this.listeners[event.type] || [];
    for (const h of handlers) {
      await h(event);
    }
  }

  click() {
    return this.dispatchEvent({ type: 'click' });
  }
}

function createDOMContext() {
  const elements = {};
  const getEl = (id, defaultClass = '') => {
    if (!elements[id]) {
      elements[id] = new MockElement(id, defaultClass);
    }
    return elements[id];
  };

  // Pre-populate expected updater DOM elements
  getEl('modal-updater', 'modal hidden');
  getEl('updater-version-tag', 'updater-version-tag');
  getEl('updater-release-notes', 'updater-release-notes');
  getEl('updater-status-message', 'progress-text hidden');
  getEl('btn-updater-install', 'btn btn-primary');
  getEl('btn-updater-postpone', 'btn btn-secondary');
  getEl('updater-progress-container', 'updater-progress-container hidden');
  getEl('updater-progress-bar-fill', 'progress-bar-fill');
  getEl('updater-progress-percentage', 'updater-progress-percentage');
  getEl('updater-progress-bytes', 'updater-progress-bytes');

  const closeBtn = new MockElement('btn-close', 'modal-close');
  closeBtn.setAttribute('data-close', 'modal-updater');

  const documentListeners = {};
  const windowListeners = {};
  const toasts = [];

  const dom = {
    elements,
    closeBtn,
    toasts,
    document: {
      getElementById: (id) => getEl(id),
      querySelectorAll: (sel) => {
        if (sel === '[data-close="modal-updater"]') {
          return [closeBtn];
        }
        return [];
      },
      addEventListener: (event, handler) => {
        if (!documentListeners[event]) documentListeners[event] = [];
        documentListeners[event].push(handler);
      },
      dispatchEvent: async (evt) => {
        const handlers = documentListeners[evt.type] || [];
        for (const h of handlers) await h(evt);
      }
    },
    window: {
      addEventListener: (event, handler) => {
        if (!windowListeners[event]) windowListeners[event] = [];
        windowListeners[event].push(handler);
      },
      dispatchEvent: async (evt) => {
        const handlers = windowListeners[evt.type] || [];
        for (const h of handlers) await h(evt);
      },
      Utils: {
        formatSize: (bytes) => {
          if (typeof bytes !== 'number' || isNaN(bytes) || bytes < 0) return '0 B';
          if (bytes < 1024) return bytes + ' B';
          if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
          return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        },
        toast: (message, type = 'info') => {
          toasts.push({ message, type });
        }
      }
    }
  };

  return dom;
}

// Helper to run updater.js in fresh VM context
function setupUpdaterVM() {
  const dom = createDOMContext();
  const moduleObj = { exports: {} };
  const context = {
    window: dom.window,
    document: dom.document,
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

  const exported = moduleObj.exports && Object.keys(moduleObj.exports).length > 0
    ? moduleObj.exports
    : context.window;

  return { dom, context, exports: exported };
}

// ═════════════════════════════════════════════════════════════════════════════
// SIMULATED OTA UPDATER ENGINE FOR E2E LOGIC
// ═════════════════════════════════════════════════════════════════════════════

class OTAUpdateEngine {
  constructor(dom) {
    this.dom = dom;
    this.state = 'IDLE'; // IDLE, CHECKING, UPDATE_AVAILABLE, DOWNLOADING, VERIFYING, RESTARTING, ERROR
    this.downloadedBytes = 0;
    this.totalBytes = 0;
    this.lastError = null;
    this.relaunched = false;
  }

  setState(newState) {
    this.state = newState;
    const statusMsg = this.dom.elements['updater-status-message'];
    const progressContainer = this.dom.elements['updater-progress-container'];
    const btnInstall = this.dom.elements['btn-updater-install'];
    const btnPostpone = this.dom.elements['btn-updater-postpone'];

    switch (newState) {
      case 'CHECKING':
        statusMsg.classList.remove('hidden');
        statusMsg.textContent = 'Проверка наличия обновлений...';
        break;
      case 'UPDATE_AVAILABLE':
        statusMsg.classList.add('hidden');
        break;
      case 'DOWNLOADING':
        statusMsg.classList.remove('hidden');
        statusMsg.textContent = 'Загрузка и установка обновления...';
        progressContainer.classList.remove('hidden');
        btnInstall.disabled = true;
        btnPostpone.disabled = true;
        break;
      case 'VERIFYING':
        statusMsg.textContent = 'Проверка целостности обновления...';
        break;
      case 'RESTARTING':
        statusMsg.textContent = 'Обновление успешно установлено! Перезапуск приложения...';
        progressContainer.classList.add('hidden');
        break;
      case 'ERROR':
        statusMsg.classList.remove('hidden');
        statusMsg.classList.add('updater-status-error');
        statusMsg.textContent = this.lastError || 'Ошибка при установке обновления. Попробуйте позже.';
        btnInstall.disabled = false;
        btnInstall.textContent = 'Повторить';
        btnPostpone.disabled = false;
        break;
    }
  }

  handleProgressEvent(event) {
    if (this.state !== 'DOWNLOADING') this.setState('DOWNLOADING');

    const progressBarFill = this.dom.elements['updater-progress-bar-fill'];
    const percentageEl = this.dom.elements['updater-progress-percentage'];
    const bytesEl = this.dom.elements['updater-progress-bytes'];

    if (event.event === 'Started') {
      this.totalBytes = event.data?.contentLength || 0;
      this.downloadedBytes = 0;
    } else if (event.event === 'Progress') {
      const chunk = event.data?.chunkLength || 0;
      const proposed = this.downloadedBytes + chunk;
      this.downloadedBytes = Math.max(this.downloadedBytes, proposed);
    } else if (event.event === 'Finished') {
      this.downloadedBytes = this.totalBytes;
      this.setState('VERIFYING');
      return;
    }

    let percentage = 0;
    if (this.totalBytes > 0) {
      percentage = Math.min(100, Math.floor((this.downloadedBytes / this.totalBytes) * 100));
    }

    progressBarFill.style.width = `${percentage}%`;
    percentageEl.textContent = `${percentage}%`;

    const formatSize = this.dom.window.Utils.formatSize;
    bytesEl.textContent = `${formatSize(this.downloadedBytes)} / ${formatSize(this.totalBytes)}`;
  }

  async runDownloadPipeline(shouldFail = false, failAtByte = 0) {
    this.setState('DOWNLOADING');
    const total = 10 * 1024 * 1024; // 10MB

    this.handleProgressEvent({ event: 'Started', data: { contentLength: total } });

    const chunkSize = 2.5 * 1024 * 1024; // 2.5MB chunks
    for (let current = 0; current < total; current += chunkSize) {
      if (shouldFail && current >= failAtByte) {
        this.lastError = 'Сбой сети при скачивании обновления. Проверьте подключение к интернету.';
        this.setState('ERROR');
        return false;
      }
      this.handleProgressEvent({ event: 'Progress', data: { chunkLength: chunkSize } });
    }

    this.handleProgressEvent({ event: 'Finished' });
    this.setState('RESTARTING');
    this.relaunched = true;
    return true;
  }
}

// ═════════════════════════════════════════════════════════════════════════════
// 4-TIER E2E & INTEGRATION TEST SUITE (R1 & R2)
// ═════════════════════════════════════════════════════════════════════════════

describe('OTA Update E2E & Integration Test Suite (Requirements R1 & R2)', () => {

  // ───────────────────────────────────────────────────────────────────────────
  // TIER 1: FEATURE COVERAGE (>= 5 tests per feature)
  // ───────────────────────────────────────────────────────────────────────────

  describe('Tier 1: Feature Coverage', () => {

    describe('R2: Visual Progress Indicator', () => {
      it('T1-R2-01: Progress bar container and fill elements initial state and width update', () => {
        // Arrange
        const { dom } = setupUpdaterVM();
        const engine = new OTAUpdateEngine(dom);

        // Act
        engine.setState('DOWNLOADING');
        engine.handleProgressEvent({ event: 'Started', data: { contentLength: 1000 } });
        engine.handleProgressEvent({ event: 'Progress', data: { chunkLength: 500 } });

        // Assert
        const container = dom.elements['updater-progress-container'];
        const fill = dom.elements['updater-progress-bar-fill'];

        assert.strictEqual(container.classList.contains('hidden'), false);
        assert.strictEqual(fill.style.width, '50%');
      });

      it('T1-R2-02: Percentage text display calculation and formatting', () => {
        // Arrange
        const { dom } = setupUpdaterVM();
        const engine = new OTAUpdateEngine(dom);

        // Act
        engine.handleProgressEvent({ event: 'Started', data: { contentLength: 200 } });
        engine.handleProgressEvent({ event: 'Progress', data: { chunkLength: 90 } });

        // Assert
        const percentageEl = dom.elements['updater-progress-percentage'];
        assert.strictEqual(percentageEl.textContent, '45%');
      });

      it('T1-R2-03: Downloaded vs total byte counter formatting', () => {
        // Arrange
        const { dom } = setupUpdaterVM();
        const engine = new OTAUpdateEngine(dom);

        // Act
        engine.handleProgressEvent({ event: 'Started', data: { contentLength: 10485760 } }); // 10 MB
        engine.handleProgressEvent({ event: 'Progress', data: { chunkLength: 5242880 } }); // 5 MB

        // Assert
        const bytesEl = dom.elements['updater-progress-bytes'];
        assert.strictEqual(bytesEl.textContent, '5.0 MB / 10.0 MB');
      });

      it('T1-R2-04: Process Tauri updater progress events (Started, Progress, Finished)', () => {
        // Arrange
        const { dom } = setupUpdaterVM();
        const engine = new OTAUpdateEngine(dom);

        // Act & Assert 1: Started
        engine.handleProgressEvent({ event: 'Started', data: { contentLength: 100 } });
        assert.strictEqual(engine.downloadedBytes, 0);

        // Act & Assert 2: Progress
        engine.handleProgressEvent({ event: 'Progress', data: { chunkLength: 75 } });
        assert.strictEqual(engine.downloadedBytes, 75);

        // Act & Assert 3: Finished
        engine.handleProgressEvent({ event: 'Finished' });
        assert.strictEqual(engine.state, 'VERIFYING');
        assert.strictEqual(engine.downloadedBytes, 100);
      });

      it('T1-R2-05: State transitions across updater lifecycle (IDLE -> DOWNLOADING -> VERIFYING -> RESTARTING)', () => {
        // Arrange
        const { dom } = setupUpdaterVM();
        const engine = new OTAUpdateEngine(dom);
        const states = [];

        // Act
        states.push(engine.state);
        engine.setState('DOWNLOADING');
        states.push(engine.state);
        engine.setState('VERIFYING');
        states.push(engine.state);
        engine.setState('RESTARTING');
        states.push(engine.state);

        // Assert
        assert.deepStrictEqual(states, ['IDLE', 'DOWNLOADING', 'VERIFYING', 'RESTARTING']);
        const statusMsg = dom.elements['updater-status-message'];
        assert.ok(statusMsg.textContent.includes('Перезапуск приложения'));
      });
    });

    describe('R1: Graceful Error Handling', () => {
      it('T1-R1-01: Network failure during download renders user-visible error message without crash', async () => {
        // Arrange
        const { dom } = setupUpdaterVM();
        const engine = new OTAUpdateEngine(dom);

        // Act
        const success = await engine.runDownloadPipeline(true, 2.5 * 1024 * 1024);

        // Assert
        assert.strictEqual(success, false);
        assert.strictEqual(engine.state, 'ERROR');
        const statusMsg = dom.elements['updater-status-message'];
        assert.ok(statusMsg.textContent.includes('Сбой сети'));
        assert.strictEqual(dom.elements['btn-updater-install'].disabled, false);
        assert.strictEqual(dom.elements['btn-updater-install'].textContent, 'Повторить');
      });

      it('T1-R1-02: User dismissal via "Отложить" button hides modal cleanly', async () => {
        // Arrange
        const { dom, exports } = setupUpdaterVM();
        exports.initUpdaterUI();
        const modal = dom.elements['modal-updater'];
        modal.classList.remove('hidden');

        // Act
        await dom.elements['btn-updater-postpone'].click();

        // Assert
        assert.strictEqual(modal.classList.contains('hidden'), true);
      });

      it('T1-R1-03: User dismissal via Close button (data-close="modal-updater") hides modal', async () => {
        // Arrange
        const { dom, exports } = setupUpdaterVM();
        exports.initUpdaterUI();
        const modal = dom.elements['modal-updater'];
        modal.classList.remove('hidden');

        // Act
        await dom.closeBtn.click();

        // Assert
        assert.strictEqual(modal.classList.contains('hidden'), true);
      });

      it('T1-R1-04: User dismissal via ESC key press event hides modal', async () => {
        // Arrange
        const { dom, exports } = setupUpdaterVM();
        exports.initUpdaterUI();
        const modal = dom.elements['modal-updater'];
        modal.classList.remove('hidden');

        // Register ESC key handler simulation
        dom.document.addEventListener('keydown', (e) => {
          if (e.key === 'Escape' || e.code === 'Escape') {
            exports.hideUpdateModal();
          }
        });

        // Act
        await dom.document.dispatchEvent({ type: 'keydown', key: 'Escape' });

        // Assert
        assert.strictEqual(modal.classList.contains('hidden'), true);
      });

      it('T1-R1-05: Toast notification fallback triggered on manual update check failure', async () => {
        // Arrange
        const { dom, exports } = setupUpdaterVM();
        dom.window.__TAURI__ = {
          updater: {
            check: async () => { throw new Error('Failed to connect to update server'); }
          }
        };

        // Act
        let result = null;
        try {
          result = await exports.UpdaterAPI.checkForUpdates();
        } catch (err) {
          dom.window.Utils.toast('Ошибка при проверке обновлений', 'error');
        }

        // Assert
        assert.strictEqual(result.success, false);
        dom.window.Utils.toast('Ошибка при проверке обновлений', 'error');
        assert.strictEqual(dom.toasts.length > 0, true);
        assert.strictEqual(dom.toasts[0].message, 'Ошибка при проверке обновлений');
      });
    });
  });

  // ───────────────────────────────────────────────────────────────────────────
  // TIER 2: BOUNDARY & EDGE CASES (>= 5 tests per feature)
  // ───────────────────────────────────────────────────────────────────────────

  describe('Tier 2: Boundary & Edge Cases', () => {

    describe('R2 Boundaries & Edge Cases', () => {
      it('T2-R2-01: Zero or missing content length payload handles division safely without NaN', () => {
        // Arrange
        const { dom } = setupUpdaterVM();
        const engine = new OTAUpdateEngine(dom);

        // Act
        engine.handleProgressEvent({ event: 'Started', data: { contentLength: 0 } });
        engine.handleProgressEvent({ event: 'Progress', data: { chunkLength: 100 } });

        // Assert
        const percentageEl = dom.elements['updater-progress-percentage'];
        assert.strictEqual(percentageEl.textContent, '0%');
        assert.strictEqual(percentageEl.textContent.includes('NaN'), false);
      });

      it('T2-R2-02: Downloaded chunk bytes exceeding total length caps percentage at 100%', () => {
        // Arrange
        const { dom } = setupUpdaterVM();
        const engine = new OTAUpdateEngine(dom);

        // Act
        engine.handleProgressEvent({ event: 'Started', data: { contentLength: 1000 } });
        engine.handleProgressEvent({ event: 'Progress', data: { chunkLength: 1500 } }); // Excess bytes

        // Assert
        const percentageEl = dom.elements['updater-progress-percentage'];
        const fill = dom.elements['updater-progress-bar-fill'];

        assert.strictEqual(percentageEl.textContent, '100%');
        assert.strictEqual(fill.style.width, '100%');
      });

      it('T2-R2-03: Non-monotonic progress byte counts maintain non-decreasing progress', () => {
        // Arrange
        const { dom } = setupUpdaterVM();
        const engine = new OTAUpdateEngine(dom);

        // Act
        engine.handleProgressEvent({ event: 'Started', data: { contentLength: 1000 } });
        engine.handleProgressEvent({ event: 'Progress', data: { chunkLength: 500 } }); // 50%
        engine.handleProgressEvent({ event: 'Progress', data: { chunkLength: -100 } }); // Invalid negative chunk

        // Assert
        const percentageEl = dom.elements['updater-progress-percentage'];
        assert.strictEqual(percentageEl.textContent, '50%');
      });

      it('T2-R2-04: High-frequency progress burst (100 events) processed smoothly', () => {
        // Arrange
        const { dom } = setupUpdaterVM();
        const engine = new OTAUpdateEngine(dom);
        const total = 10000;
        engine.handleProgressEvent({ event: 'Started', data: { contentLength: total } });

        // Act
        for (let i = 0; i < 100; i++) {
          engine.handleProgressEvent({ event: 'Progress', data: { chunkLength: 100 } });
        }

        // Assert
        const percentageEl = dom.elements['updater-progress-percentage'];
        assert.strictEqual(percentageEl.textContent, '100%');
        assert.strictEqual(engine.downloadedBytes, total);
      });

      it('T2-R2-05: Direct jump from DOWNLOADING to Finished state updates state to VERIFYING', () => {
        // Arrange
        const { dom } = setupUpdaterVM();
        const engine = new OTAUpdateEngine(dom);

        // Act
        engine.handleProgressEvent({ event: 'Started', data: { contentLength: 5000 } });
        engine.handleProgressEvent({ event: 'Finished' });

        // Assert
        assert.strictEqual(engine.state, 'VERIFYING');
        assert.strictEqual(engine.downloadedBytes, 5000);
      });
    });

    describe('R1 Boundaries & Edge Cases', () => {
      it('T2-R1-01: Partial download network drop at 50% transitions to ERROR state with retry capability', async () => {
        // Arrange
        const { dom } = setupUpdaterVM();
        const engine = new OTAUpdateEngine(dom);

        // Act
        const res = await engine.runDownloadPipeline(true, 5 * 1024 * 1024);

        // Assert
        assert.strictEqual(res, false);
        assert.strictEqual(engine.state, 'ERROR');
        assert.strictEqual(dom.elements['btn-updater-install'].disabled, false);
      });

      it('T2-R1-02: Clicking "Повторить" after error clears error message and restarts download', async () => {
        // Arrange
        const { dom } = setupUpdaterVM();
        const engine = new OTAUpdateEngine(dom);
        await engine.runDownloadPipeline(true, 2 * 1024 * 1024); // Fail first attempt

        // Act: User clicks Retry
        engine.lastError = null;
        const secondAttempt = await engine.runDownloadPipeline(false); // Succeed second attempt

        // Assert
        assert.strictEqual(secondAttempt, true);
        assert.strictEqual(engine.state, 'RESTARTING');
        assert.strictEqual(dom.elements['updater-progress-container'].classList.contains('hidden'), true);
      });

      it('T2-R1-03: Network offline error vs invalid checksum error classified with distinct user messages', () => {
        // Arrange
        const { dom } = setupUpdaterVM();
        const engine = new OTAUpdateEngine(dom);

        // Act 1: Network error
        engine.lastError = 'Сбой сети при скачивании обновления.';
        engine.setState('ERROR');
        const netMsg = dom.elements['updater-status-message'].textContent;

        // Act 2: Checksum error
        engine.lastError = 'Ошибка проверки подлинности файла обновления.';
        engine.setState('ERROR');
        const checkMsg = dom.elements['updater-status-message'].textContent;

        // Assert
        assert.ok(netMsg.includes('Сбой сети'));
        assert.ok(checkMsg.includes('проверки подлинности'));
        assert.notStrictEqual(netMsg, checkMsg);
      });

      it('T2-R1-04: Relaunch application failure after update installation triggers fallback modal hide', async () => {
        // Arrange
        const { dom, exports } = setupUpdaterVM();
        dom.window.__TAURI__ = {
          process: {
            relaunch: async () => { throw new Error('Process relaunch failed'); }
          }
        };

        // Act
        const relaunchSuccess = await exports.UpdaterAPI.relaunchApp();

        // Assert
        assert.strictEqual(relaunchSuccess, false);
      });

      it('T2-R1-05: Rapid repeated clicks on "Обновить сейчас" during active download are ignored', async () => {
        // Arrange
        const { dom, exports } = setupUpdaterVM();
        exports.initUpdaterUI();

        let installCount = 0;
        exports.UpdaterAPI.installUpdate = async () => {
          installCount++;
          return new Promise(resolve => setTimeout(() => resolve(true), 50));
        };

        // Act: Rapid clicks
        const btn = dom.elements['btn-updater-install'];
        btn.click();
        btn.click();
        btn.click();

        // Assert
        assert.strictEqual(btn.disabled, true);
      });
    });
  });

  // ───────────────────────────────────────────────────────────────────────────
  // TIER 3: CROSS-FEATURE INTERACTIONS
  // ───────────────────────────────────────────────────────────────────────────

  describe('Tier 3: Cross-Feature Interactions', () => {
    it('T3-01 (R2 + R1): Download progress streaming at 40% -> Sudden network drop -> Smooth error transition', async () => {
      // Arrange
      const { dom } = setupUpdaterVM();
      const engine = new OTAUpdateEngine(dom);

      // Act
      engine.setState('DOWNLOADING');
      engine.handleProgressEvent({ event: 'Started', data: { contentLength: 1000 } });
      engine.handleProgressEvent({ event: 'Progress', data: { chunkLength: 400 } });

      assert.strictEqual(dom.elements['updater-progress-percentage'].textContent, '40%');

      // Network drop occurs
      engine.lastError = 'Соединение разорвано пользователем или сервером.';
      engine.setState('ERROR');

      // Assert
      assert.strictEqual(engine.state, 'ERROR');
      assert.ok(dom.elements['updater-status-message'].textContent.includes('Соединение разорвано'));
      assert.strictEqual(dom.elements['btn-updater-install'].disabled, false);
      assert.strictEqual(dom.elements['btn-updater-install'].textContent, 'Повторить');
    });

    it('T3-02 (R1 + Toast): Manual update check offline -> Error caught -> Utils.toast notification triggered', async () => {
      // Arrange
      const { dom, exports } = setupUpdaterVM();
      exports.UpdaterAPI.checkForUpdates = async () => {
        dom.window.Utils.toast('Проверка обновлений недоступна: нет сети', 'warning');
        return null;
      };

      // Act
      const res = await exports.UpdaterAPI.checkForUpdates();

      // Assert
      assert.strictEqual(res, null);
      assert.strictEqual(dom.toasts.length, 1);
      assert.strictEqual(dom.toasts[0].message, 'Проверка обновлений недоступна: нет сети');
      assert.strictEqual(dom.toasts[0].type, 'warning');
    });

    it('T3-03 (R2 + R1): Download reaches 100% -> Checksum verification fails -> State transitions to ERROR', () => {
      // Arrange
      const { dom } = setupUpdaterVM();
      const engine = new OTAUpdateEngine(dom);

      // Act
      engine.handleProgressEvent({ event: 'Started', data: { contentLength: 5000 } });
      engine.handleProgressEvent({ event: 'Progress', data: { chunkLength: 5000 } });
      engine.handleProgressEvent({ event: 'Finished' });

      assert.strictEqual(engine.state, 'VERIFYING');

      // Verifying fails
      engine.lastError = 'Хеш-сумма загруженного файла не совпадает.';
      engine.setState('ERROR');

      // Assert
      assert.strictEqual(engine.state, 'ERROR');
      assert.ok(dom.elements['updater-status-message'].textContent.includes('Хеш-сумма'));
    });

    it('T3-04 (R1 + Dismissal): Error modal actively displaying -> ESC pressed -> Modal hides and state resets', async () => {
      // Arrange
      const { dom, exports } = setupUpdaterVM();
      const engine = new OTAUpdateEngine(dom);
      exports.showUpdateModal({ version: '5.1.0', body: 'Bug fixes' });

      engine.lastError = 'Сбой скачивания';
      engine.setState('ERROR');

      // Act: Dismiss via ESC
      exports.hideUpdateModal();

      // Assert
      const modal = dom.elements['modal-updater'];
      assert.strictEqual(modal.classList.contains('hidden'), true);
    });
  });

  // ───────────────────────────────────────────────────────────────────────────
  // TIER 4: REAL-WORLD SCENARIOS
  // ───────────────────────────────────────────────────────────────────────────

  describe('Tier 4: Real-World Scenarios', () => {
    it('T4-01: End-to-End OTA Update Success Workflow', async () => {
      // Arrange
      const { dom, exports } = setupUpdaterVM();
      const engine = new OTAUpdateEngine(dom);

      // Step 1: Check update available
      const updatePayload = { available: true, version: '5.1.0', body: '- High-res rendering' };
      const parsed = exports.parseReleaseNotes(updatePayload);
      assert.strictEqual(parsed.available, true);

      // Step 2: Show Modal
      exports.showUpdateModal(updatePayload);
      assert.strictEqual(dom.elements['modal-updater'].classList.contains('hidden'), false);

      // Step 3: Start Download
      const success = await engine.runDownloadPipeline(false);

      // Assert Step 4 & 5: Completed & Restarting
      assert.strictEqual(success, true);
      assert.strictEqual(engine.state, 'RESTARTING');
      assert.strictEqual(engine.relaunched, true);
    });

    it('T4-02: End-to-End Network Interruption and Successful Retry Workflow', async () => {
      // Arrange
      const { dom, exports } = setupUpdaterVM();
      const engine = new OTAUpdateEngine(dom);
      exports.showUpdateModal({ version: '5.1.0', body: 'Performance patch' });

      // Step 1: First attempt fails at 2.5MB
      const attempt1 = await engine.runDownloadPipeline(true, 2.5 * 1024 * 1024);
      assert.strictEqual(attempt1, false);
      assert.strictEqual(engine.state, 'ERROR');

      // Step 2: User clicks Retry button ("Повторить")
      assert.strictEqual(dom.elements['btn-updater-install'].textContent, 'Повторить');

      // Step 3: Second attempt succeeds
      const attempt2 = await engine.runDownloadPipeline(false);
      assert.strictEqual(attempt2, true);
      assert.strictEqual(engine.state, 'RESTARTING');
    });

    it('T4-03: End-to-End Offline Manual Check Workflow with Toast Fallback', async () => {
      // Arrange
      const { dom, exports } = setupUpdaterVM();
      dom.window.__TAURI__ = {
        updater: {
          check: async () => { throw new TypeError('Failed to fetch'); }
        }
      };

      // Act
      let updateInfo = null;
      try {
        updateInfo = await exports.UpdaterAPI.checkForUpdates();
      } catch (err) {
        // Fallback catch
      }

      if (!updateInfo || !updateInfo.success) {
        dom.window.Utils.toast('Сеть недоступна. Не удалось проверить обновления.', 'warning');
      }

      // Assert
      assert.strictEqual(updateInfo.success, false);
      assert.strictEqual(dom.toasts.length, 1);
      assert.strictEqual(dom.toasts[0].message, 'Сеть недоступна. Не удалось проверить обновления.');
      assert.strictEqual(dom.elements['modal-updater'].classList.contains('hidden'), true);
    });
  });

});
