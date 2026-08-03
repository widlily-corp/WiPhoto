const test = require('node:test');
const assert = require('node:assert');

// Pure logic for testing

// 1. Compare State Management
function calculateCompareState(galleryImages, selectedPaths, currentLeftPath, currentRightPath, action, shiftKey) {
  const images = galleryImages || [];
  
  if (action === 'open') {
    if (!selectedPaths || selectedPaths.length < 2) return null;
    return { left: selectedPaths[0], right: selectedPaths[1] };
  }
  
  let leftIdx = images.findIndex(i => i.path === currentLeftPath);
  let rightIdx = images.findIndex(i => i.path === currentRightPath);
  
  if (action === 'next') {
    if (shiftKey) {
      leftIdx = Math.min(leftIdx + 1, images.length - 1);
    } else {
      rightIdx = Math.min(rightIdx + 1, images.length - 1);
    }
  } else if (action === 'prev') {
    if (shiftKey) {
      leftIdx = Math.max(leftIdx - 1, 0);
    } else {
      rightIdx = Math.max(rightIdx - 1, 0);
    }
  }
  
  return {
    left: images[leftIdx]?.path,
    right: images[rightIdx]?.path
  };
}

// 2. Filmstrip Index Calculation
function getFilmstripIndices(currentIndex, totalImages) {
  if (totalImages === 0) return [];
  const start = Math.max(0, currentIndex - 10);
  const end = Math.min(totalImages - 1, currentIndex + 10);
  const indices = [];
  for (let i = start; i <= end; i++) {
    indices.push(i);
  }
  return indices;
}

// 3. Histogram Clipping Calculation
function calculateHistogramClipping(pixelData) { // pixelData is [r,g,b,a, r,g,b,a, ...]
  let shadowCount = 0;
  let highlightCount = 0;
  const totalPixels = pixelData.length / 4;
  
  if (totalPixels === 0) return { shadows: 0, highlights: 0 };

  for (let i = 0; i < pixelData.length; i += 4) {
    const l = Math.round(pixelData[i] * 0.299 + pixelData[i+1] * 0.587 + pixelData[i+2] * 0.114);
    if (l === 0) shadowCount++;
    if (l === 255) highlightCount++;
  }

  return {
    shadows: (shadowCount / totalPixels) * 100,
    highlights: (highlightCount / totalPixels) * 100
  };
}

test('CompareState Management', (t) => {
  const images = [{path: '1'}, {path: '2'}, {path: '3'}, {path: '4'}];
  
  // open
  let state = calculateCompareState(images, ['2', '3'], null, null, 'open', false);
  assert.deepStrictEqual(state, { left: '2', right: '3' });
  
  // next (right)
  state = calculateCompareState(images, null, '2', '3', 'next', false);
  assert.deepStrictEqual(state, { left: '2', right: '4' });
  
  // prev (left) - with shift
  state = calculateCompareState(images, null, '2', '4', 'prev', true);
  assert.deepStrictEqual(state, { left: '1', right: '4' });
});

test('Filmstrip Index Calculation', (t) => {
  // Near start
  let indices = getFilmstripIndices(2, 20);
  assert.strictEqual(indices.length, 13);
  assert.strictEqual(indices[0], 0);
  assert.strictEqual(indices[12], 12);
  
  // Middle
  indices = getFilmstripIndices(50, 100);
  assert.strictEqual(indices.length, 21);
  assert.strictEqual(indices[0], 40);
  assert.strictEqual(indices[20], 60);
});

test('Histogram Clipping Detection', (t) => {
  const data = [
    0,0,0,255,      // shadow
    0,0,0,255,      // shadow
    255,255,255,255,// highlight
    128,128,128,255 // midtone
  ];
  
  const clipping = calculateHistogramClipping(data);
  assert.strictEqual(clipping.shadows, 50); // 2 out of 4
  assert.strictEqual(clipping.highlights, 25); // 1 out of 4
});

module.exports = { calculateCompareState, getFilmstripIndices, calculateHistogramClipping };
