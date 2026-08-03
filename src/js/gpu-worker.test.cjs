const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const logicCode = fs.readFileSync(path.join(__dirname, 'grid-worker-logic.js'), 'utf8');
const logicContext = {};
// Evaluate code in context
(new Function('self', logicCode))(logicContext);
const { calcLayout, calcVisible, sortItems } = logicContext.GridLogic;

const GPURendererCode = fs.readFileSync(path.join(__dirname, 'gpu-renderer.js'), 'utf8');
function getGPURenderer(nav) {
  const context = { window: {} };
  (new Function('window', 'navigator', 'module', GPURendererCode))(context.window, nav, {});
  return context.window.GPURenderer;
}

test('GridLogic.calcLayout computes columns and rows correctly', () => {
  const result = calcLayout({ containerWidth: 1000, thumbSize: 180, gap: 6, itemCount: 100 });
  assert.strictEqual(result.columns, 5); // floor(1006 / 186) = 5
  assert.strictEqual(result.rowHeight, 186); // 180 + 6
  assert.strictEqual(result.totalRows, 20); // 100 / 5 = 20
});

test('GridLogic.calcVisible computes visible indices correctly', () => {
  const result = calcVisible({
    scrollTop: 400,
    viewportHeight: 500,
    rowHeight: 186,
    totalRows: 20,
    bufferRows: 3,
    columns: 5,
    itemCount: 100
  });

  // startRow: Math.max(0, floor(400/186) - 3) = Math.max(0, 2 - 3) = 0
  // endRow: Math.min(19, ceil(900/186) + 3) = Math.min(19, 5 + 3) = 8
  
  assert.strictEqual(result.startRow, 0);
  assert.strictEqual(result.endRow, 8);
  assert.strictEqual(result.startIdx, 0); // 0 * 5 = 0
  assert.strictEqual(result.endIdx, 45); // (8 + 1) * 5 = 45
});

test('GridLogic.sortItems sorts correctly by string and number', () => {
  const items = [
    { name: 'b', size: 100 },
    { name: 'c', size: 50 },
    { name: 'a', size: 200 }
  ];

  const sortedByName = sortItems({ items, sortBy: 'name', sortDir: 1 });
  assert.strictEqual(sortedByName[0].name, 'a');
  assert.strictEqual(sortedByName[2].name, 'c');

  const sortedBySizeDesc = sortItems({ items, sortBy: 'size', sortDir: -1 });
  assert.strictEqual(sortedBySizeDesc[0].size, 200);
  assert.strictEqual(sortedBySizeDesc[2].size, 50);
});

test('GPURenderer isAvailable checks for navigator.gpu', () => {
  // Test environment doesn't have navigator.gpu
  assert.strictEqual(getGPURenderer(undefined).isAvailable(), false);
  
  assert.strictEqual(getGPURenderer({ gpu: {} }).isAvailable(), true);
});

test('Worker protocol mock test', async () => {
  // Simple test simulating the worker environment
  const msg = { type: 'calcLayout', data: { containerWidth: 1000, thumbSize: 180, gap: 6, itemCount: 100 }, id: 1 };
  
  const result = logicContext.GridLogic.calcLayout(msg.data);
  assert.strictEqual(result.columns, 5);
});
