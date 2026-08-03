const { describe, it } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

// Load updater.js content
const updaterPath = path.join(__dirname, 'updater.js');
const updaterCode = fs.readFileSync(updaterPath, 'utf8');

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
    addEventListener: () => {},
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
    'btn-updater-install': createMockElement('btn-updater-install', 'button'),
    'btn-updater-postpone': createMockElement('btn-updater-postpone', 'button'),
    'updater-progress-container': createMockElement('updater-progress-container'),
    'updater-progress-bar-fill': createMockElement('updater-progress-bar-fill'),
    'updater-progress-percentage': createMockElement('updater-progress-percentage'),
    'updater-progress-bytes': createMockElement('updater-progress-bytes')
  };

  elements['modal-updater'].classList.add('hidden');
  elements['updater-progress-container'].classList.add('hidden');

  ctx.document = {
    readyState: 'complete',
    getElementById: (id) => elements[id] || null,
    querySelectorAll: (selector) => [],
    addEventListener: () => {}
  };
  ctx.window.document = ctx.document;
  return elements;
}

function createFreshInstance() {
  const context = {
    window: {},
    console: console,
    setTimeout: setTimeout,
    clearTimeout: clearTimeout
  };
  context.self = context.window;
  const domElements = setupUpdaterDOMContext(context);
  vm.runInNewContext(updaterCode, context);
  return { context, domElements, exports: context.module?.exports || context.window };
}

describe('M1 Challenger Empirical Stress & Boundary Harness', () => {

  describe('1. Content Length Boundary & Anomalous Payloads', () => {
    it('should handle 0 content length safely without NaN or invalid DOM values', () => {
      const { exports, domElements } = createFreshInstance();
      
      const res1 = exports.handleProgressEvent({ event: 'Started', data: { contentLength: 0 } });
      const res2 = exports.handleProgressEvent({ event: 'Progress', data: { chunkLength: 500 } });

      assert.strictEqual(res2.percentage, 0, 'Percentage must be 0 when contentLength is 0');
      assert.strictEqual(domElements['updater-progress-percentage'].textContent, '0%');
      assert.strictEqual(domElements['updater-progress-bar-fill'].style.width, '0%');
      assert.ok(domElements['updater-progress-bytes'].textContent.includes('500') && domElements['updater-progress-bytes'].textContent.includes('B'));
      assert.ok(!domElements['updater-progress-percentage'].textContent.includes('NaN'));
    });

    it('should handle missing, undefined, null, or string contentLength gracefully', () => {
      const { exports, domElements } = createFreshInstance();

      const testPayloads = [
        { event: 'Started', data: {} },
        { event: 'Started', data: { contentLength: undefined } },
        { event: 'Started', data: { contentLength: null } },
        { event: 'Started', data: { contentLength: 'invalid' } },
        { event: 'Started', data: { contentLength: -100 } }
      ];

      for (const payload of testPayloads) {
        assert.doesNotThrow(() => {
          exports.handleProgressEvent(payload);
        });
        assert.strictEqual(domElements['updater-progress-percentage'].textContent.includes('NaN'), false);
      }
    });

    it('should convert numeric string contentLength properly', () => {
      const { exports, domElements } = createFreshInstance();

      exports.handleProgressEvent({ event: 'Started', data: { contentLength: '1000000' } });
      exports.handleProgressEvent({ event: 'Progress', data: { chunkLength: '500000' } });

      assert.strictEqual(domElements['updater-progress-percentage'].textContent, '50%');
      assert.strictEqual(domElements['updater-progress-bar-fill'].style.width, '50%');
    });
  });

  describe('2. Chunk Size Boundary & Overshoot Edge Cases', () => {
    it('should clamp percentage to 100% when cumulative chunks exceed total bytes', () => {
      const { exports, domElements } = createFreshInstance();

      exports.handleProgressEvent({ event: 'Started', data: { contentLength: 1000 } });
      exports.handleProgressEvent({ event: 'Progress', data: { chunkLength: 5000 } }); // 5x total

      assert.strictEqual(domElements['updater-progress-percentage'].textContent, '100%');
      assert.strictEqual(domElements['updater-progress-bar-fill'].style.width, '100%');
    });

    it('should handle multi-gigabyte chunk sizes without numerical overflow', () => {
      const { exports, domElements } = createFreshInstance();
      const tenGB = 10 * 1024 * 1024 * 1024; // 10,737,418,240

      exports.handleProgressEvent({ event: 'Started', data: { contentLength: tenGB } });
      exports.handleProgressEvent({ event: 'Progress', data: { chunkLength: 5 * 1024 * 1024 * 1024 } });

      assert.strictEqual(domElements['updater-progress-percentage'].textContent, '50%');
      assert.strictEqual(domElements['updater-progress-bar-fill'].style.width, '50%');
      assert.ok(domElements['updater-progress-bytes'].textContent.includes('5.0 GB / 10.0 GB'));
    });

    it('should handle zero chunk length and negative chunk length without regression', () => {
      const { exports, domElements } = createFreshInstance();

      exports.handleProgressEvent({ event: 'Started', data: { contentLength: 1000 } });
      exports.handleProgressEvent({ event: 'Progress', data: { chunkLength: 500 } });
      
      // Zero chunk length
      exports.handleProgressEvent({ event: 'Progress', data: { chunkLength: 0 } });
      assert.strictEqual(domElements['updater-progress-percentage'].textContent, '50%');

      // Negative chunk length should be ignored/clamped to 0
      exports.handleProgressEvent({ event: 'Progress', data: { chunkLength: -200 } });
      assert.strictEqual(domElements['updater-progress-percentage'].textContent, '50%');
    });
  });

  describe('3. Rapid Progress Event Bursts & High Frequency Stress', () => {
    it('should process 10,000 rapid progress events smoothly without state corruption', () => {
      const { exports, domElements } = createFreshInstance();
      const total = 1000000;
      const chunkSize = 100;

      exports.handleProgressEvent({ event: 'Started', data: { contentLength: total } });

      const startTime = Date.now();
      for (let i = 0; i < 10000; i++) {
        exports.handleProgressEvent({ event: 'Progress', data: { chunkLength: chunkSize } });
      }
      const duration = Date.now() - startTime;

      assert.strictEqual(domElements['updater-progress-percentage'].textContent, '100%');
      assert.strictEqual(domElements['updater-progress-bar-fill'].style.width, '100%');
      assert.ok(duration < 1000, `10,000 events processed in ${duration}ms (expected < 1000ms)`);
    });
  });

  describe('4. Progress Rounding & Precision Verification', () => {
    it('should produce integer percentages without decimal places or floating point inaccuracies', () => {
      const { exports, domElements } = createFreshInstance();
      
      exports.handleProgressEvent({ event: 'Started', data: { contentLength: 3 } });
      exports.handleProgressEvent({ event: 'Progress', data: { chunkLength: 1 } }); // 1/3 = 33.33333...%

      assert.strictEqual(domElements['updater-progress-percentage'].textContent, '33%');
      assert.strictEqual(domElements['updater-progress-bar-fill'].style.width, '33%');
    });
  });

  describe('5. Out-of-Order & Anomalous Event Sequences', () => {
    it('should handle Progress event before Started event without breaking', () => {
      const { exports, domElements } = createFreshInstance();

      assert.doesNotThrow(() => {
        exports.handleProgressEvent({ event: 'Progress', data: { chunkLength: 1024 } });
      });

      assert.strictEqual(domElements['updater-progress-percentage'].textContent, '0%');
    });

    it('should handle Finished event before Started event gracefully', () => {
      const { exports, domElements } = createFreshInstance();

      assert.doesNotThrow(() => {
        exports.handleProgressEvent({ event: 'Finished' });
      });

      assert.strictEqual(exports.getUpdaterState(), exports.UPDATER_STATES.VERIFYING);
      assert.strictEqual(domElements['updater-progress-percentage'].textContent, '0%');
    });

    it('should reset downloadedBytes on secondary Started event', () => {
      const { exports, domElements } = createFreshInstance();

      exports.handleProgressEvent({ event: 'Started', data: { contentLength: 1000 } });
      exports.handleProgressEvent({ event: 'Progress', data: { chunkLength: 500 } });
      assert.strictEqual(domElements['updater-progress-percentage'].textContent, '50%');

      // Restart update stream
      exports.handleProgressEvent({ event: 'Started', data: { contentLength: 2000 } });
      assert.strictEqual(domElements['updater-progress-percentage'].textContent, '0%');

      exports.handleProgressEvent({ event: 'Progress', data: { chunkLength: 500 } });
      assert.strictEqual(domElements['updater-progress-percentage'].textContent, '25%');
    });
  });

  describe('6. State Machine & Modal UI Interoperability', () => {
    it('should properly disable and re-enable action buttons during state transitions', () => {
      const { exports, domElements } = createFreshInstance();

      // Initial IDLE
      assert.strictEqual(domElements['btn-updater-install'].disabled, false);
      assert.strictEqual(domElements['btn-updater-postpone'].disabled, false);

      // DOWNLOADING
      exports.setUpdaterState(exports.UPDATER_STATES.DOWNLOADING);
      assert.strictEqual(domElements['btn-updater-install'].disabled, true);
      assert.strictEqual(domElements['btn-updater-postpone'].disabled, true);

      // VERIFYING
      exports.setUpdaterState(exports.UPDATER_STATES.VERIFYING);
      assert.strictEqual(domElements['btn-updater-install'].disabled, true);
      assert.strictEqual(domElements['btn-updater-postpone'].disabled, true);

      // ERROR -> Re-enabled
      exports.setUpdaterState(exports.UPDATER_STATES.ERROR);
      assert.strictEqual(domElements['btn-updater-install'].disabled, false);
      assert.strictEqual(domElements['btn-updater-postpone'].disabled, false);
    });

    it('should hide modal and clean reset progress UI when hideUpdateModal is called', () => {
      const { exports, domElements } = createFreshInstance();

      exports.handleProgressEvent({ event: 'Started', data: { contentLength: 1000 } });
      exports.handleProgressEvent({ event: 'Progress', data: { chunkLength: 500 } });

      exports.hideUpdateModal();

      assert.strictEqual(exports.getUpdaterState(), exports.UPDATER_STATES.IDLE);
      assert.strictEqual(domElements['modal-updater'].classList.contains('hidden'), true);
      assert.strictEqual(domElements['updater-progress-container'].classList.contains('hidden'), true);
      assert.strictEqual(domElements['updater-progress-percentage'].textContent, '0%');
      assert.strictEqual(domElements['updater-progress-bar-fill'].style.width, '0%');
      assert.strictEqual(domElements['updater-progress-bytes'].textContent, '0 B / 0 B');
    });
  });
});
