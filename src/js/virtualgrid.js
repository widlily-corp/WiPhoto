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

  let renderedStartIdx = -1;
  let renderedEndIdx = -1;

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
    Logger.debug('VirtualGrid', "setItems called, newItems count: " + newItems.length);
    items = newItems;
    thumbSize = newThumbSize || thumbSize;
    isActive = true;

    // Reset visible range to force rendering after container clear
    visibleStartRow = -1;
    visibleEndRow = -1;
    renderedStartIdx = -1;
    renderedEndIdx = -1;

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
    
    Logger.debug('VirtualGrid', `recalculate: scrollContainer clientWidth=${scrollContainer.clientWidth}, containerWidth=${containerWidth}, columns=${columns}, totalRows=${totalRows}`);

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
    
    Logger.debug('VirtualGrid', `renderVisible: scrollTop=${scrollTop}, viewportHeight=${viewportHeight}, rowHeight=${rowHeight}, newStartRow=${newStartRow}, newEndRow=${newEndRow}`);

    // Early exit if nothing changed
    if (newStartRow === visibleStartRow && newEndRow === visibleEndRow) {
      Logger.debug('VirtualGrid', "renderVisible early exit (nothing changed)");
      return;
    }

    visibleStartRow = newStartRow;
    visibleEndRow = newEndRow;

    // Disconnect old lazy observations before rendering new set
    if (lazyObserver) {
      lazyObserver.disconnect();
    }

    // Determine which items to render
    const startIdx = visibleStartRow * columns;
    const endIdx = Math.min((visibleEndRow + 1) * columns, items.length);
    
    Logger.debug('VirtualGrid', `renderVisible rendering items range: ${startIdx} to ${endIdx}`);

    if (renderedStartIdx === -1 || renderedEndIdx === -1 || startIdx >= renderedEndIdx || endIdx <= renderedStartIdx) {
      // No overlap or first render
      const fragment = document.createDocumentFragment();
      for (let i = startIdx; i < endIdx; i++) {
        const card = cardRenderer(items[i], i);
        fragment.appendChild(card);
      }
      contentArea.innerHTML = '';
      contentArea.appendChild(fragment);
      
      renderedStartIdx = startIdx;
      renderedEndIdx = endIdx;
      updateSpacers();
      Logger.debug('VirtualGrid', "renderVisible complete, appended items count: " + contentArea.children.length);
      return;
    }

    // We have overlap!
    // 1. Remove elements that left the range from the top
    if (startIdx > renderedStartIdx) {
      const removeCount = startIdx - renderedStartIdx;
      for (let i = 0; i < removeCount; i++) {
        if (contentArea.firstChild) {
          contentArea.removeChild(contentArea.firstChild);
        }
      }
    }
    // 2. Remove elements that left the range from the bottom
    if (endIdx < renderedEndIdx) {
      const removeCount = renderedEndIdx - endIdx;
      for (let i = 0; i < removeCount; i++) {
        if (contentArea.lastChild) {
          contentArea.removeChild(contentArea.lastChild);
        }
      }
    }
    // 3. Prepend elements that entered from the top
    if (startIdx < renderedStartIdx) {
      for (let i = renderedStartIdx - 1; i >= startIdx; i--) {
        const card = cardRenderer(items[i], i);
        contentArea.insertBefore(card, contentArea.firstChild);
      }
    }
    // 4. Append elements that entered from the bottom
    if (endIdx > renderedEndIdx) {
      for (let i = renderedEndIdx; i < endIdx; i++) {
        const card = cardRenderer(items[i], i);
        contentArea.appendChild(card);
      }
    }

    renderedStartIdx = startIdx;
    renderedEndIdx = endIdx;

    updateSpacers();
    Logger.debug('VirtualGrid', "renderVisible complete, appended items count: " + contentArea.children.length);
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
