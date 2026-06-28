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
  let visibleStartRow = 0;
  let visibleEndRow = 0;
  let bufferRows = 3;
  let renderedCards = new Map(); // row -> DOM elements
  let spacerTop = null;
  let spacerBottom = null;
  let contentArea = null;
  let isActive = false;
  let resizeObserver = null;
  let lazyObserver = null;

  // Callbacks
  let onCardClick = null;
  let onCardDoubleClick = null;
  let onCardContextMenu = null;
  let cardRenderer = null;

  function init(config) {
    container = config.container;
    scrollContainer = config.scrollContainer;
    onCardClick = config.onCardClick;
    onCardDoubleClick = config.onCardDoubleClick;
    onCardContextMenu = config.onCardContextMenu;
    cardRenderer = config.cardRenderer;

    // Create layout structure
    spacerTop = Utils.el('div', { className: 'vgrid-spacer-top' });
    contentArea = Utils.el('div', { className: 'vgrid-content' });
    spacerBottom = Utils.el('div', { className: 'vgrid-spacer-bottom' });

    // Initialize IntersectionObserver for lazy loading
    if (window.IntersectionObserver) {
      lazyObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            const img = entry.target;
            if (img.dataset.src) {
              img.src = img.dataset.src;
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

    // Listen to scroll events (throttled)
    scrollContainer.addEventListener('scroll', Utils.throttle(onScroll, 16));

    // Track container resizes
    resizeObserver = new ResizeObserver(Utils.debounce(() => {
      if (isActive) {
        recalculate();
        renderVisible();
      }
    }, 100));
    resizeObserver.observe(scrollContainer);
  }

  function setItems(newItems, newThumbSize) {
    items = newItems;
    thumbSize = newThumbSize || thumbSize;
    isActive = true;

    // Clear existing
    container.innerHTML = '';
    renderedCards.clear();

    container.appendChild(spacerTop);
    container.appendChild(contentArea);
    container.appendChild(spacerBottom);

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
    const containerWidth = scrollContainer.clientWidth - 16; // minus padding
    columns = Math.max(1, Math.floor((containerWidth + gap) / (thumbSize + gap)));
    rowHeight = thumbSize + gap;
    totalRows = Math.ceil(items.length / columns);
    const totalHeight = totalRows * rowHeight;

    // Set grid layout on content area
    contentArea.style.display = 'grid';
    contentArea.style.gridTemplateColumns = `repeat(${columns}, 1fr)`;
    contentArea.style.gap = `${gap}px`;
    contentArea.style.padding = '4px';

    // Total scrollable height via spacers
    updateSpacers();
  }

  function onScroll() {
    if (!isActive) return;
    renderVisible();
  }

  function renderVisible() {
    const scrollTop = scrollContainer.scrollTop;
    const viewportHeight = scrollContainer.clientHeight;

    const newStartRow = Math.max(0, Math.floor(scrollTop / rowHeight) - bufferRows);
    const newEndRow = Math.min(
      totalRows - 1,
      Math.ceil((scrollTop + viewportHeight) / rowHeight) + bufferRows
    );

    // Early exit if nothing changed
    if (newStartRow === visibleStartRow && newEndRow === visibleEndRow) return;

    visibleStartRow = newStartRow;
    visibleEndRow = newEndRow;

    // Disconnect old lazy observations before rendering new set
    if (lazyObserver) {
      lazyObserver.disconnect();
    }

    // Determine which items to render
    const startIdx = visibleStartRow * columns;
    const endIdx = Math.min((visibleEndRow + 1) * columns, items.length);

    // Build new content
    const fragment = document.createDocumentFragment();
    for (let i = startIdx; i < endIdx; i++) {
      const card = cardRenderer(items[i], i);
      fragment.appendChild(card);

      // Lazy load observation
      if (lazyObserver) {
        const imgEl = card.querySelector('.thumb-img');
        if (imgEl && imgEl.dataset.src) {
          lazyObserver.observe(imgEl);
        }
      }
    }

    contentArea.innerHTML = '';
    contentArea.appendChild(fragment);

    updateSpacers();
  }

  function updateSpacers() {
    const topHeight = visibleStartRow * rowHeight;
    const renderedRows = visibleEndRow - visibleStartRow + 1;
    const bottomHeight = Math.max(0, (totalRows - visibleStartRow - renderedRows) * rowHeight);

    spacerTop.style.height = `${topHeight}px`;
    spacerBottom.style.height = `${bottomHeight}px`;
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
      start: visibleStartRow * columns,
      end: Math.min((visibleEndRow + 1) * columns, items.length),
    };
  }

  function destroy() {
    isActive = false;
    renderedCards.clear();
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
    destroy,
  };
})();

window.VirtualGrid = VirtualGrid;
