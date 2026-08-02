const { describe, it } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

// Load updater.js content
const updaterPath = path.join(__dirname, 'updater.js');
const updaterCode = fs.readFileSync(updaterPath, 'utf8');

// Setup mock window/document environment
const context = {
  window: {},
  console: console,
  setTimeout: setTimeout,
  clearTimeout: clearTimeout
};
context.self = context.window;

// Execute updater.js inside VM context
vm.runInNewContext(updaterCode, context);

const {
  isNewerVersion,
  renderMarkdown,
  parseReleaseNotes,
  UpdaterAPI
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
});
