const fs = require('fs');
let code = fs.readFileSync('src/js/virtualgrid.js', 'utf8');

// 1. Add worker initialization
const workerInit = `
  let worker = null;
  let workerResolvers = new Map();
  let workerMsgId = 0;
  
  if (typeof window !== 'undefined' && window.Worker) {
    worker = new Worker('js/grid-worker.js');
    worker.onmessage = (e) => {
      const { id, data, type } = e.data;
      if (workerResolvers.has(id)) {
        workerResolvers.get(id)(data);
        workerResolvers.delete(id);
      }
    };
  }
  
  function postToWorker(type, data) {
    return new Promise(resolve => {
      if (!worker) { resolve(null); return; }
      const id = ++workerMsgId;
      workerResolvers.set(id, resolve);
      worker.postMessage({ type, data, id });
    });
  }
`;
code = code.replace('let resizeObserver = null;', 'let resizeObserver = null;\n' + workerInit);

// 2. Add sort method to VirtualGrid
const sortMethod = `
  async function sort(sortBy, sortDir) {
    if (worker) {
      const res = await postToWorker('sort', { items, sortBy, sortDir });
      items = res.items;
    } else {
      items = GridLogic.sortItems({ items, sortBy, sortDir });
    }
    recalculate();
    renderVisible();
  }
`;
code = code.replace('function getItemAtIndex(index)', sortMethod + '\n  function getItemAtIndex(index)');

code = code.replace('getActiveCards: () => activeCardMap,', 'getActiveCards: () => activeCardMap,\n    sort,');

// 3. Update recalculate to be async
const recalcOriginal = `  function recalculate() {
    if (!scrollContainer) return;
    cachedContainerWidth = Math.max(0, scrollContainer.clientWidth - 16);
    cachedViewportHeight = scrollContainer.clientHeight || 0;

    columns = Math.max(1, Math.floor((cachedContainerWidth + gap) / (thumbSize + gap)));
    rowHeight = thumbSize + gap;
    totalRows = Math.ceil(items.length / columns);`;

const recalcNew = `  async function recalculate() {
    if (!scrollContainer) return;
    cachedContainerWidth = Math.max(0, scrollContainer.clientWidth - 16);
    cachedViewportHeight = scrollContainer.clientHeight || 0;

    if (worker) {
      const res = await postToWorker('calcLayout', { containerWidth: cachedContainerWidth, thumbSize, gap, itemCount: items.length });
      columns = res.columns;
      rowHeight = res.rowHeight;
      totalRows = res.totalRows;
    } else {
      columns = Math.max(1, Math.floor((cachedContainerWidth + gap) / (thumbSize + gap)));
      rowHeight = thumbSize + gap;
      totalRows = Math.ceil(items.length / columns);
    }`;
code = code.replace(recalcOriginal, recalcNew);

// 4. Update renderVisible to be async
const renderOrig = `  function renderVisible() {
    if (!isActive) return;

    if (items.length === 0) {`;

const renderNew = `  async function renderVisible() {
    if (!isActive) return;

    if (items.length === 0) {`;
code = code.replace(renderOrig, renderNew);

const renderVisibleCalcOrig = `    const scrollTop = scrollContainer.scrollTop;
    const viewportHeight = cachedViewportHeight || scrollContainer.clientHeight;

    const newStartRow = Math.max(0, Math.floor(scrollTop / rowHeight) - bufferRows);
    const newEndRow = Math.min(
      totalRows - 1,
      Math.ceil((scrollTop + viewportHeight) / rowHeight) + bufferRows
    );
    
    // Early exit if nothing changed
    if (newStartRow === visibleStartRow && newEndRow === visibleEndRow) {
      return;
    }

    visibleStartRow = newStartRow;
    visibleEndRow = newEndRow;

    const startIdx = visibleStartRow * columns;
    const endIdx = Math.min((visibleEndRow + 1) * columns, items.length);`;

const renderVisibleCalcNew = `    const scrollTop = scrollContainer.scrollTop;
    const viewportHeight = cachedViewportHeight || scrollContainer.clientHeight;

    let newStartRow, newEndRow, startIdx, endIdx;
    
    if (worker) {
      const res = await postToWorker('calcVisible', { scrollTop, viewportHeight, rowHeight, totalRows, bufferRows, columns, itemCount: items.length });
      newStartRow = res.startRow;
      newEndRow = res.endRow;
      startIdx = res.startIdx;
      endIdx = res.endIdx;
    } else {
      newStartRow = Math.max(0, Math.floor(scrollTop / rowHeight) - bufferRows);
      newEndRow = Math.min(
        totalRows - 1,
        Math.ceil((scrollTop + viewportHeight) / rowHeight) + bufferRows
      );
      startIdx = newStartRow * columns;
      endIdx = Math.min((newEndRow + 1) * columns, items.length);
    }
    
    // Early exit if nothing changed
    if (newStartRow === visibleStartRow && newEndRow === visibleEndRow) {
      return;
    }

    visibleStartRow = newStartRow;
    visibleEndRow = newEndRow;`;

code = code.replace(renderVisibleCalcOrig, renderVisibleCalcNew);

fs.writeFileSync('src/js/virtualgrid.js', code);
