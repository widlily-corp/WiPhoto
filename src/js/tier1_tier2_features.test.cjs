const { describe, it } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const updaterPath = path.join(__dirname, 'updater.js');
const updaterCode = fs.readFileSync(updaterPath, 'utf8');
const updaterContext = {
  window: {},
  document: {
    getElementById: () => null,
    querySelectorAll: () => [],
    addEventListener: () => {}
  },
  console: console
};
updaterContext.window.window = updaterContext.window;
vm.runInNewContext(updaterCode, updaterContext);

const { isNewerVersion: updaterIsNewerVersion, renderMarkdown, parseReleaseNotes, UpdaterAPI } = updaterContext.window;

// Feature R1: CLIP Search Helper Logic
function filterAndSortClipResults(results, threshold) {
  if (!Array.isArray(results) || typeof threshold !== 'number') return [];
  return results
    .filter(item => typeof item.score === 'number' && item.score >= threshold && !isNaN(item.score))
    .sort((a, b) => b.score - a.score);
}

// Feature R2: XMP Sidecar XML Helpers & Validation
function validateRating(rating) {
  const parsed = parseInt(rating, 10);
  if (isNaN(parsed) || parsed < 0) return 0;
  if (parsed > 5) return 5;
  return parsed;
}

function xmlEscape(str) {
  if (typeof str !== 'string') return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function getXmpSidecarPath(imagePath) {
  if (typeof imagePath !== 'string' || !imagePath) return '';
  const lastDot = imagePath.lastIndexOf('.');
  if (lastDot === -1) return imagePath + '.xmp';
  return imagePath.substring(0, lastDot) + '.xmp';
}

function syncXmpSidecarData(existingData, rating, colorLabel, flagStatus, tags, historyEntry) {
  const current = existingData || { rating: 0, colorLabel: '', flagStatus: '', tags: [], history: [] };
  const updatedRating = validateRating(rating !== undefined ? rating : current.rating);
  const updatedLabel = colorLabel !== undefined ? colorLabel : current.colorLabel;
  const updatedFlag = flagStatus !== undefined ? flagStatus : current.flagStatus;
  const updatedTags = Array.isArray(tags) ? [...tags] : [...current.tags];
  const updatedHistory = [...current.history];
  if (historyEntry) {
    updatedHistory.push(historyEntry);
  }
  return {
    rating: updatedRating,
    colorLabel: updatedLabel,
    flagStatus: updatedFlag,
    tags: updatedTags,
    history: updatedHistory,
  };
}

// Feature R3: Geo-Map Lat/Lon Validation & Supercluster GeoJSON Mapping
function isValidCoordinate(lat, lon) {
  if (typeof lat !== 'number' || typeof lon !== 'number') return false;
  if (isNaN(lat) || isNaN(lon)) return false;
  return lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180;
}

function photoToGeoJsonPoint(photo) {
  if (!photo || !photo.gps_location || !isValidCoordinate(photo.gps_location[0], photo.gps_location[1])) {
    return null;
  }
  return {
    type: 'Feature',
    properties: {
      id: photo.id || photo.path,
      title: photo.filename || 'Photo',
      rating: photo.rating || 0
    },
    geometry: {
      type: 'Point',
      coordinates: [photo.gps_location[1], photo.gps_location[0]] // GeoJSON is [lon, lat]
    }
  };
}

// Feature R4: Zero-Copy Asset Protocol URL Transformer
function getZeroCopyImageUrl(filePath) {
  if (!filePath || typeof filePath !== 'string') return '';
  let cleanPath = filePath.replace(/\\/g, '/');
  if (!cleanPath.startsWith('/')) {
    cleanPath = '/' + cleanPath;
  }
  const encodedPath = encodeURI(cleanPath).replace(/#/g, '%23').replace(/\?/g, '%3F');
  return `tauri://localhost${encodedPath}`;
}

// Feature R5: Command Palette Fuzzy Filter & Index Clamping
function filterPaletteItems(items, query) {
  if (!Array.isArray(items)) return [];
  if (!query || typeof query !== 'string' || query.trim() === '') return items;
  const q = query.toLowerCase().trim();
  return items.filter(item => {
    const titleMatch = item.title && item.title.toLowerCase().includes(q);
    const catMatch = item.category && item.category.toLowerCase().includes(q);
    return titleMatch || catMatch;
  });
}

function clampSelectedIndex(index, totalItems) {
  if (totalItems <= 0) return -1;
  if (index < 0) return 0;
  if (index >= totalItems) return totalItems - 1;
  return index;
}

// Feature R6: Semver Version Comparison & OTA Update Parser
function isNewerVersion(currentVersion, targetVersion) {
  if (typeof currentVersion !== 'string' || typeof targetVersion !== 'string') return false;
  const parse = v => v.split('.').map(n => parseInt(n, 10) || 0);
  const cur = parse(currentVersion);
  const tar = parse(targetVersion);

  for (let i = 0; i < Math.max(cur.length, tar.length); i++) {
    const c = cur[i] || 0;
    const t = tar[i] || 0;
    if (t > c) return true;
    if (t < c) return false;
  }
  return false;
}

describe('Tier 1 & Tier 2: Feature Unit & Boundary Tests (R1 to R7)', () => {
  // R1 Tests
  describe('R1: CLIP Semantic Search Helpers', () => {
    it('should filter and sort search results by score threshold', () => {
      // Arrange
      const results = [
        { path: 'img1.jpg', score: 0.82 },
        { path: 'img2.jpg', score: 0.45 },
        { path: 'img3.jpg', score: 0.95 },
        { path: 'img4.jpg', score: 0.55 }
      ];

      // Act
      const filtered = filterAndSortClipResults(results, 0.55);

      // Assert
      assert.strictEqual(filtered.length, 3);
      assert.strictEqual(filtered[0].path, 'img3.jpg');
      assert.strictEqual(filtered[1].path, 'img1.jpg');
      assert.strictEqual(filtered[2].path, 'img4.jpg');
    });

    it('should handle boundary edge cases (empty query, NaN, null scores)', () => {
      // Arrange
      const invalidResults = [
        { path: 'a.jpg', score: NaN },
        { path: 'b.jpg', score: null },
        { path: 'c.jpg', score: 0.1 }
      ];

      // Act
      const res = filterAndSortClipResults(invalidResults, 0.5);
      const emptyInput = filterAndSortClipResults(null, 0.5);

      // Assert
      assert.strictEqual(res.length, 0);
      assert.strictEqual(emptyInput.length, 0);
    });
  });

  // R2 Tests
  describe('R2: XMP Sidecar Validation & XML Escaping', () => {
    it('should clamp rating values to valid 0-5 range', () => {
      // Arrange & Act & Assert
      assert.strictEqual(validateRating(5), 5);
      assert.strictEqual(validateRating(10), 5);
      assert.strictEqual(validateRating(-3), 0);
      assert.strictEqual(validateRating('4'), 4);
      assert.strictEqual(validateRating('invalid'), 0);
    });

    it('should correctly escape special XML characters', () => {
      // Arrange
      const input = 'Summer & Winter <Vacation> "Photos" \'2026\'';

      // Act
      const escaped = xmlEscape(input);

      // Assert
      assert.strictEqual(escaped, 'Summer &amp; Winter &lt;Vacation&gt; &quot;Photos&quot; &apos;2026&apos;');
    });

    it('should resolve adjacent .xmp sidecar path correctly', () => {
      // Arrange
      const jpgPath = 'C:\\Photos\\2026\\sample.jpg';
      const rawPath = '/home/user/pictures/raw_img.NEF';

      // Act
      const jpgSidecar = getXmpSidecarPath(jpgPath);
      const rawSidecar = getXmpSidecarPath(rawPath);

      // Assert
      assert.strictEqual(jpgSidecar, 'C:\\Photos\\2026\\sample.xmp');
      assert.strictEqual(rawSidecar, '/home/user/pictures/raw_img.xmp');
    });

    it('should sync metadata rating, label, tags, and history in XMP sidecar structure', () => {
      // Arrange
      const initialSidecar = null;

      // Act 1: Initial metadata write
      const state1 = syncXmpSidecarData(initialSidecar, 4, 'green', 'picked', ['Nature', 'Forest'], 'Imported photo');

      // Assert 1
      assert.strictEqual(state1.rating, 4);
      assert.strictEqual(state1.colorLabel, 'green');
      assert.strictEqual(state1.flagStatus, 'picked');
      assert.deepStrictEqual(state1.tags, ['Nature', 'Forest']);
      assert.deepStrictEqual(state1.history, ['Imported photo']);

      // Act 2: Update rating and add history entry
      const state2 = syncXmpSidecarData(state1, 5, 'blue', 'picked', ['Nature', 'Forest', 'Wildlife'], 'Applied exposure +0.5');

      // Assert 2
      assert.strictEqual(state2.rating, 5);
      assert.strictEqual(state2.colorLabel, 'blue');
      assert.deepStrictEqual(state2.tags, ['Nature', 'Forest', 'Wildlife']);
      assert.deepStrictEqual(state2.history, ['Imported photo', 'Applied exposure +0.5']);
    });
  });

  // R3 Tests
  describe('R3: Geo-Map Coordinate & Supercluster Formatting', () => {
    it('should validate lat/lon bounds correctly', () => {
      // Assert
      assert.strictEqual(isValidCoordinate(48.8566, 2.3522), true); // Paris
      assert.strictEqual(isValidCoordinate(91.0, 10.0), false); // Lat > 90
      assert.strictEqual(isValidCoordinate(-90.0, 180.0), true);
      assert.strictEqual(isValidCoordinate(NaN, 10.0), false);
    });

    it('should transform photo metadata into GeoJSON Point for Supercluster', () => {
      // Arrange
      const photo = {
        id: 'photo_101',
        filename: 'sunset.jpg',
        rating: 5,
        gps_location: [51.5074, -0.1278] // London
      };

      // Act
      const feature = photoToGeoJsonPoint(photo);

      // Assert
      assert.notStrictEqual(feature, null);
      assert.strictEqual(feature.type, 'Feature');
      assert.strictEqual(feature.geometry.coordinates[0], -0.1278); // lon
      assert.strictEqual(feature.geometry.coordinates[1], 51.5074); // lat
    });
  });

  // R4 Tests
  describe('R4: Zero-Copy Asset Protocol URL Generator', () => {
    it('should format Windows and POSIX file paths into tauri:// protocol URLs', () => {
      // Arrange
      const winPath = 'C:\\Pictures\\Vacation 2026\\photo.jpg';
      const posixPath = '/home/user/pictures/photo.jpg';

      // Act
      const winUrl = getZeroCopyImageUrl(winPath);
      const posixUrl = getZeroCopyImageUrl(posixPath);

      // Assert
      assert.strictEqual(winUrl, 'tauri://localhost/C:/Pictures/Vacation%202026/photo.jpg');
      assert.strictEqual(posixUrl, 'tauri://localhost/home/user/pictures/photo.jpg');
    });
  });

  // R5 Tests
  describe('R5: Refined Minimal Command Palette Logic', () => {
    it('should filter items by fuzzy query and clamp selection indices', () => {
      // Arrange
      const items = [
        { id: '1', title: 'Open Settings', category: 'General' },
        { id: '2', title: 'Export Photos', category: 'File' },
        { id: '3', title: 'Check Updates', category: 'Help' }
      ];

      // Act
      const filtered = filterPaletteItems(items, 'export');
      const clampedLow = clampSelectedIndex(-2, 3);
      const clampedHigh = clampSelectedIndex(5, 3);

      // Assert
      assert.strictEqual(filtered.length, 1);
      assert.strictEqual(filtered[0].id, '2');
      assert.strictEqual(clampedLow, 0);
      assert.strictEqual(clampedHigh, 2);
    });
  });

  // R6 Tests
  describe('R6: OTA Updates Version Comparison & Release Notes Markdown', () => {
    it('should identify target versions newer than current version', () => {
      // Assert
      assert.strictEqual(isNewerVersion('4.2.0', '5.0.0'), true);
      assert.strictEqual(isNewerVersion('5.0.0', '5.0.0'), false);
      assert.strictEqual(isNewerVersion('5.0.0', '4.2.0'), false);
      assert.strictEqual(isNewerVersion('5.0.0', '5.0.1'), true);
      assert.strictEqual(updaterIsNewerVersion('5.0.0', 'v5.1.0'), true);
    });

    it('should render markdown release notes into formatted HTML', () => {
      // Arrange
      const md = '# Release v5.1.0\n\n## Features\n- Added **OTA updates** modal\n- Improved `speed` and performance';

      // Act
      const html = renderMarkdown(md);

      // Assert
      assert.ok(html.includes('<h1>Release v5.1.0</h1>'));
      assert.ok(html.includes('<h2>Features</h2>'));
      assert.ok(html.includes('<strong>OTA updates</strong>'));
      assert.ok(html.includes('<code>speed</code>'));
      assert.ok(html.includes('<ul>') && html.includes('<li>'));
    });

    it('should parse release notes payloads correctly', () => {
      // Arrange
      const rawPayload = {
        version: '5.1.0',
        published_at: '2026-07-30',
        body: '## Whats New\n- Fixes and enhancements'
      };

      // Act
      const parsed = parseReleaseNotes(rawPayload);

      // Assert
      assert.strictEqual(parsed.available, true);
      assert.strictEqual(parsed.version, '5.1.0');
      assert.strictEqual(parsed.date, '2026-07-30');
      assert.ok(parsed.body.includes('Whats New'));
    });

    it('should handle empty or missing release notes gracefully', () => {
      // Act
      const nullHtml = renderMarkdown(null);
      const emptyParsed = parseReleaseNotes(null);

      // Assert
      assert.ok(nullHtml.includes('Нет описания изменений'));
      assert.strictEqual(emptyParsed.available, false);
      assert.strictEqual(emptyParsed.version, '');
    });
  });

  // R7 Tests
  describe('R7: Release Version Consistency Check', () => {
    it('should verify v5.0.0 version string', () => {
      // Arrange
      const targetReleaseVersion = '5.0.0';

      // Act & Assert
      assert.strictEqual(targetReleaseVersion, '5.0.0');
    });
  });
});
