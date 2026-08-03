// ═══ Virtual Grid — Performant Scrolling for Large Galleries ═══
// Renders only visible cards + a small buffer. Critical for 10K+ image libraries.

const VirtualGrid = (() => {
  let container = null;
  let scrollContainer = null;
  let items = [];
  let thumbSize = 180;
  let gap = 6;
  let columns = 1;
  let rowHeight = 0;
  let totalRows = 0;
  let visibleStartRow = -1;
  let visibleEndRow = -1;
  let bufferRows = 3;

  // DOM recycling pool and active card map
  let cardPool = []; // Pool of detached .thumb-card DOM elements for reuse
  let activeCardMap = new Map(); // Map<index, HTMLElement> for currently rendered cards

  // Cached container dimensions to avoid layout reads during scroll
  let cachedContainerWidth = 0;
  let cachedViewportHeight = 0;

  // Frame lock for rAF scroll handling
  let ticking = false;

  let contentArea = null;
  let isActive = false;
  let resizeObserver = null;

  let worker = null;
  let workerResolvers = new Map();
  let workerMsgId = 0;
  
  if (typeof window !== 'undefined' && window.Worker) {
    worker = new Worker('js/grid-worker.js');
    worker.onmessage = (e) => {
      const { id, data } = e.data;
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

  let lazyObserver = null;

  // Callbacks
  let _onCardClick = null;
  let _onCardDoubleClick = null;
  let _onCardContextMenu = null;
  let cardRenderer = null;

  function init(config) {
    container = config.container;
    scrollContainer = config.scrollContainer;
    _onCardClick = config.onCardClick;
    _onCardDoubleClick = config.onCardDoubleClick;
    _onCardContextMenu = config.onCardContextMenu;
    cardRenderer = config.cardRenderer;

    // Create layout structure
    contentArea = Utils.el('div', { className: 'vgrid-content' });
    contentArea.style.position = 'absolute';
    contentArea.style.top = '0';
    contentArea.style.left = '0';
    contentArea.style.right = '0';

    // Initialize IntersectionObserver for lazy loading
    if (window.IntersectionObserver) {
      lazyObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            const img = entry.target;
            if (img.dataset.src) {
              img.src = Utils.assetUrl(img.dataset.src);
              img.removeAttribute('data-src');
              img.classList.remove('loading');
            }
            lazyObserver.unobserve(img);
          }
        });
      }, {
        root: scrollContainer,
        rootMargin: '200px 0px',
      });
    }

    // Listen to scroll events with rAF frame lock & passive listener
    scrollContainer.addEventListener('scroll', onScroll, { passive: true });

    // Track container resizes and cache dimensions
    resizeObserver = new ResizeObserver(Utils.debounce(() => {
      if (isActive) {
        requestAnimationFrame(() => {
          recalculate();
          renderVisible();
        });
      }
    }, 100));
    resizeObserver.observe(scrollContainer);
  }

  function setItems(newItems, newThumbSize) {
    Logger.debug('VirtualGrid', "setItems called, newItems count: " + newItems.length);
    items = newItems;
    thumbSize = newThumbSize || thumbSize;
    isActive = true;

    // Recycle all active cards into cardPool
    for (const card of activeCardMap.values()) {
      if (card.parentNode) {
        card.parentNode.removeChild(card);
      }
      cardPool.push(card);
    }
    activeCardMap.clear();

    visibleStartRow = -1;
    visibleEndRow = -1;

    // Reset layout containers
    container.innerHTML = '';
    container.style.position = 'relative';
    container.appendChild(contentArea);

    recalculate();
    renderVisible();
  }

  function updateThumbSize(newSize) {
    thumbSize = newSize;
    if (isActive) {
      recalculate();
      renderVisible();
    }
  }

  function recalculate() {
    if (!scrollContainer) return;
    cachedContainerWidth = Math.max(0, scrollContainer.clientWidth - 16);
    cachedViewportHeight = scrollContainer.clientHeight || 0;

    columns = Math.max(1, Math.floor((cachedContainerWidth + gap) / (thumbSize + gap)));
    rowHeight = thumbSize + gap;
    totalRows = Math.ceil(items.length / columns);
    
    Logger.debug('VirtualGrid', `recalculate: clientWidth=${scrollContainer.clientWidth}, containerWidth=${cachedContainerWidth}, columns=${columns}, totalRows=${totalRows}`);

    // Set grid layout on content area
    contentArea.style.display = 'grid';
    contentArea.style.gridTemplateColumns = `repeat(${columns}, 1fr)`;
    contentArea.style.gap = `${gap}px`;
    contentArea.style.padding = '4px';

    // Set total scrollable height
    container.style.height = `${totalRows * rowHeight}px`;

    updateSpacers();
  }

  function onScroll() {
    if (!ticking && isActive) {
      requestAnimationFrame(() => {
        renderVisible();
        ticking = false;
      });
      ticking = true;
    }
  }

  function renderVisible() {
    if (!isActive) return;

    if (items.length === 0) {
      for (const card of activeCardMap.values()) {
        if (card.parentNode) card.parentNode.removeChild(card);
        cardPool.push(card);
      }
      activeCardMap.clear();
      visibleStartRow = -1;
      visibleEndRow = -1;
      updateSpacers();
      return;
    }

    const scrollTop = scrollContainer.scrollTop;
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
    const endIdx = Math.min((visibleEndRow + 1) * columns, items.length);

    // 1. Recycle elements that scrolled out of the visible window
    for (const [idx, card] of activeCardMap.entries()) {
      if (idx < startIdx || idx >= endIdx) {
        if (card.parentNode) {
          card.parentNode.removeChild(card);
        }
        activeCardMap.delete(idx);
        cardPool.push(card);
      }
    }

    // 2. Render or recycle elements for new visible indices using DocumentFragment batching
    const useFragment = typeof document !== 'undefined' && typeof document.createDocumentFragment === 'function';
    const fragment = useFragment ? document.createDocumentFragment() : null;
    let firstExistingCard = null;

    for (let i = startIdx; i < endIdx; i++) {
      if (activeCardMap.has(i)) {
        if (!firstExistingCard && useFragment) {
          firstExistingCard = activeCardMap.get(i);
        }
        continue;
      }

      const recycledCard = cardPool.length > 0 ? cardPool.pop() : null;
      const card = cardRenderer ? cardRenderer(items[i], i, recycledCard) : null;
      if (!card) continue;

      activeCardMap.set(i, card);

      const img = card.tagName === 'IMG' ? card : (card.querySelector ? card.querySelector('img') : null);
      if (img && lazyObserver) {
        if (img.dataset && img.dataset.src) {
          lazyObserver.observe(img);
        }
      }

      if (fragment) {
        fragment.appendChild(card);
      } else {
        if (firstExistingCard && firstExistingCard.parentNode === contentArea) {
          contentArea.insertBefore(card, firstExistingCard);
        } else {
          contentArea.appendChild(card);
        }
      }
    }

    if (fragment && fragment.hasChildNodes && fragment.hasChildNodes()) {
      if (firstExistingCard && firstExistingCard.parentNode === contentArea) {
        contentArea.insertBefore(fragment, firstExistingCard);
      } else {
        contentArea.appendChild(fragment);
      }
    }

    updateSpacers();
  }

  function updateSpacers() {
    const topHeight = visibleStartRow > 0 ? visibleStartRow * rowHeight : 0;
    contentArea.style.transform = `translateY(${topHeight}px)`;
  }

  
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

  function getItemAtIndex(index) {
    return items[index] || null;
  }

  function scrollToIndex(index) {
    const row = Math.floor(index / columns);
    scrollContainer.scrollTop = row * rowHeight;
  }

  function getVisibleRange() {
    return {
      start: Math.max(0, visibleStartRow) * columns,
      end: Math.min((visibleEndRow + 1) * columns, items.length),
    };
  }

  function getRenderedCard(index) {
    return activeCardMap.get(index) || null;
  }

  function destroy() {
    isActive = false;
    for (const card of activeCardMap.values()) {
      if (card.parentNode) card.parentNode.removeChild(card);
    }
    activeCardMap.clear();
    cardPool = [];
    if (resizeObserver) {
      resizeObserver.disconnect();
    }
    if (lazyObserver) {
      lazyObserver.disconnect();
    }
  }

  return {
    init,
    setItems,
    updateThumbSize,
    recalculate,
    renderVisible,
    getItemAtIndex,
    scrollToIndex,
    getVisibleRange,
    getRenderedCard,
    getActiveCards: () => activeCardMap,
    sort,
    destroy,
  };
})();

window.VirtualGrid = VirtualGrid;

