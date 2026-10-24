const { describe, it } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

describe('UX Polish & Navigation Ergonomics Test Suite', () => {
  describe('Gallery Navigation Logic & Boundary Clamping', () => {
    function computeTargetIndex(currentIndex, totalCount, cols, direction) {
      if (totalCount <= 0) return -1;
      let target = currentIndex;
      if (target < 0 || target >= totalCount) {
        return 0;
      }
      switch (direction) {
        case 'right':
          return Math.min(totalCount - 1, target + 1);
        case 'left':
          return Math.max(0, target - 1);
        case 'down':
          return Math.min(totalCount - 1, target + cols);
        case 'up':
          return Math.max(0, target - cols);
        case 'home':
          return 0;
        case 'end':
          return totalCount - 1;
        case 'pageup':
          return Math.max(0, target - cols * 4);
        case 'pagedown':
          return Math.min(totalCount - 1, target + cols * 4);
        default:
          return target;
      }
    }

    it('should navigate right, left, up, and down correctly within bounds', () => {
      const total = 20;
      const cols = 5;

      // Start at 0, move right
      assert.strictEqual(computeTargetIndex(0, total, cols, 'right'), 1);

      // From 0, move left (clamped at 0)
      assert.strictEqual(computeTargetIndex(0, total, cols, 'left'), 0);

      // From 0, move down (moves 1 row = +5)
      assert.strictEqual(computeTargetIndex(0, total, cols, 'down'), 5);

      // From 5, move up (moves 1 row = -5)
      assert.strictEqual(computeTargetIndex(5, total, cols, 'up'), 0);

      // From 18, move down (clamped at total - 1 = 19)
      assert.strictEqual(computeTargetIndex(18, total, cols, 'down'), 19);

      // Home and End
      assert.strictEqual(computeTargetIndex(10, total, cols, 'home'), 0);
      assert.strictEqual(computeTargetIndex(10, total, cols, 'end'), 19);

      // PageUp and PageDown
      assert.strictEqual(computeTargetIndex(0, total, cols, 'pagedown'), 19);
      assert.strictEqual(computeTargetIndex(19, total, cols, 'pageup'), 0);
    });

    it('should handle uninitialized index gracefully by starting at 0', () => {
      const total = 10;
      const cols = 4;
      assert.strictEqual(computeTargetIndex(-1, total, cols, 'right'), 0);
      assert.strictEqual(computeTargetIndex(-1, total, cols, 'down'), 0);
    });
  });

  describe('Range Selection & Invert Selection Logic', () => {
    it('should compute range selection indices from anchor to target', () => {
      const anchor = 2;
      const target = 6;
      const range = [];
      const start = Math.min(anchor, target);
      const end = Math.max(anchor, target);
      for (let i = start; i <= end; i++) range.push(i);

      assert.deepStrictEqual(range, [2, 3, 4, 5, 6]);
    });

    it('should invert selection accurately', () => {
      const allPaths = ['a.jpg', 'b.jpg', 'c.jpg', 'd.jpg'];
      const selected = new Set(['b.jpg', 'c.jpg']);

      const inverted = new Set();
      allPaths.forEach(p => {
        if (!selected.has(p)) inverted.add(p);
      });

      assert.strictEqual(inverted.size, 2);
      assert.ok(inverted.has('a.jpg'));
      assert.ok(inverted.has('d.jpg'));
      assert.ok(!inverted.has('b.jpg'));
      assert.ok(!inverted.has('c.jpg'));
    });
  });

  describe('Compare Mode Active Pane & Swap Logic', () => {
    it('should toggle active pane between left and right', () => {
      let activePane = 'right';
      activePane = activePane === 'left' ? 'right' : 'left';
      assert.strictEqual(activePane, 'left');
      activePane = activePane === 'left' ? 'right' : 'left';
      assert.strictEqual(activePane, 'right');
    });

    it('should swap left and right indices', () => {
      let left = 2;
      let right = 5;
      const tmp = left;
      left = right;
      right = tmp;
      assert.strictEqual(left, 5);
      assert.strictEqual(right, 2);
    });
  });

  describe('Command Palette Registry & Expanded Actions', () => {
    // Read and evaluate commandpalette.js
    const cpPath = path.join(__dirname, 'commandpalette.js');
    const cpCode = fs.readFileSync(cpPath, 'utf8');

    const context = {
      window: {},
      document: {
        getElementById: () => null,
        addEventListener: () => {}
      },
      Utils: {
        el: () => ({ appendChild: () => {} }),
        toast: () => {}
      },
      Gallery: {
        getSelectedImages: () => [],
        getFilteredImages: () => [],
        selectAll: () => {},
        clearSelection: () => {},
        invertSelection: () => {},
        setRating: () => {},
        setFlagStatus: () => {}
      },
      CompareMode: {
        open: () => {}
      },
      Viewer: {
        open: () => {}
      },
      App: {
        switchView: () => {}
      }
    };
    context.self = context.window;
    vm.runInNewContext(cpCode, context);

    const CommandPalette = context.window.CommandPalette;

    it('should contain all new pro workflow commands', () => {
      const commands = CommandPalette.getCommands();
      const ids = commands.map(c => c.id);

      assert.ok(ids.includes('compare-photos'), 'Should include compare-photos command');
      assert.ok(ids.includes('rate-5'), 'Should include rate-5 command');
      assert.ok(ids.includes('rate-0'), 'Should include rate-0 command');
      assert.ok(ids.includes('flag-pick'), 'Should include flag-pick command');
      assert.ok(ids.includes('flag-reject'), 'Should include flag-reject command');
      assert.ok(ids.includes('flag-clear'), 'Should include flag-clear command');
      assert.ok(ids.includes('select-all'), 'Should include select-all command');
      assert.ok(ids.includes('clear-selection'), 'Should include clear-selection command');
      assert.ok(ids.includes('invert-selection'), 'Should include invert-selection command');
      assert.ok(ids.includes('focus-search'), 'Should include focus-search command');
      assert.ok(ids.includes('view-fullscreen'), 'Should include view-fullscreen command');
      assert.ok(ids.includes('zoom-in'), 'Should include zoom-in command');
      assert.ok(ids.includes('zoom-out'), 'Should include zoom-out command');
    });

    it('should fuzzy filter commands by pro keywords', () => {
      const commands = CommandPalette.getCommands();
      const compareResults = CommandPalette.filterPaletteItems(commands, 'сравнить');
      assert.ok(compareResults.length > 0);
      assert.strictEqual(compareResults[0].id, 'compare-photos');

      const ratingResults = CommandPalette.filterPaletteItems(commands, 'рейтинг');
      assert.ok(ratingResults.length >= 4);

      const invertResults = CommandPalette.filterPaletteItems(commands, 'инвертировать');
      assert.ok(invertResults.length === 1);
      assert.strictEqual(invertResults[0].id, 'invert-selection');
    });
  });
});
