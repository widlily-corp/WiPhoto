// Shared pure functions for grid worker and tests
function calcLayout({ containerWidth, thumbSize, gap, itemCount }) {
  const columns = Math.max(1, Math.floor((containerWidth + gap) / (thumbSize + gap)));
  const rowHeight = thumbSize + gap;
  const totalRows = Math.ceil(itemCount / columns);
  return { columns, rowHeight, totalRows };
}

function calcVisible({ scrollTop, viewportHeight, rowHeight, totalRows, bufferRows, columns, itemCount }) {
  if (itemCount === 0) {
    return { startIdx: 0, endIdx: 0, startRow: -1, endRow: -1 };
  }
  const startRow = Math.max(0, Math.floor(scrollTop / rowHeight) - bufferRows);
  const endRow = Math.min(
    totalRows - 1,
    Math.ceil((scrollTop + viewportHeight) / rowHeight) + bufferRows
  );
  
  const startIdx = startRow * columns;
  const endIdx = Math.min((endRow + 1) * columns, itemCount);

  return { startIdx, endIdx, startRow, endRow };
}

function sortItems({ items, sortBy, sortDir }) {
  // sortBy can be 'name', 'date', 'size', 'rating'
  // sortDir can be 1 (asc) or -1 (desc)
  const sorted = [...items].sort((a, b) => {
    let valA = a[sortBy];
    let valB = b[sortBy];
    
    if (typeof valA === 'string' && typeof valB === 'string') {
      return valA.localeCompare(valB) * sortDir;
    }
    
    if (valA < valB) return -1 * sortDir;
    if (valA > valB) return 1 * sortDir;
    return 0;
  });
  return sorted;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { calcLayout, calcVisible, sortItems };
}
if (typeof self !== 'undefined') {
  self.GridLogic = { calcLayout, calcVisible, sortItems };
}
