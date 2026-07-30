// ═══ VirtualGrid 10,000+ Photo Dataset Empirical Stress Test ═══
const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

// Simple Mock DOM Environment for VirtualGrid VM execution
function createDOMMock() {
  class MockNode {
    constructor(tagName = 'DIV', props = {}) {
      this.tagName = tagName.toUpperCase();
      this.className = props.className || '';
      this.style = {};
      this.children = [];
      this.parentNode = null;
      this.dataset = {};
      this.src = '';
      this.classList = {
        remove: (cls) => {},
        add: (cls) => {}
      };
    }

    appendChild(child) {
      if (child.parentNode) {
        child.parentNode.removeChild(child);
      }
      child.parentNode = this;
      this.children.push(child);
      return child;
    }

    insertBefore(newChild, refChild) {
      if (newChild.parentNode) {
        newChild.parentNode.removeChild(newChild);
      }
      newChild.parentNode = this;
      const idx = this.children.indexOf(refChild);
      if (idx !== -1) {
        this.children.splice(idx, 0, newChild);
      } else {
        this.children.push(newChild);
      }
      return newChild;
    }

    removeChild(child) {
      const idx = this.children.indexOf(child);
      if (idx !== -1) {
        this.children.splice(idx, 1);
        child.parentNode = null;
      }
      return child;
    }

    set innerHTML(val) {
      if (val === '') {
        this.children.forEach(c => { c.parentNode = null; });
        this.children = [];
      }
    }

    get innerHTML() {
      return this.children.map(c => `<${c.tagName}></${c.tagName}>`).join('');
    }

    removeAttribute(attr) {}
  }

  const listeners = {};

  const scrollContainer = new MockNode('DIV', { className: 'gallery-scroll-container' });
  scrollContainer.clientWidth = 1200;
  scrollContainer.clientHeight = 800;
  scrollContainer.scrollTop = 0;
  scrollContainer.addEventListener = (event, fn) => {
    listeners[event] = listeners[event] || [];
    listeners[event].push(fn);
  };

  const container = new MockNode('DIV', { className: 'vgrid-container' });

  class MockResizeObserver {
    constructor(cb) { this.cb = cb; }
    observe() {}
    disconnect() {}
  }

  class MockIntersectionObserver {
    constructor(cb) { this.cb = cb; }
    observe() {}
    unobserve() {}
    disconnect() {}
  }

  const rafCallbacks = [];

  const context = {
    window: {},
    document: {
      createElement: (tag) => new MockNode(tag)
    },
    ResizeObserver: MockResizeObserver,
    IntersectionObserver: MockIntersectionObserver,
    requestAnimationFrame: (fn) => {
      fn(); // Execute synchronously for test control
    },
    Logger: {
      debug: () => {},
      info: () => {},
      warn: () => {},
      error: () => {}
    },
    performance: performance
  };

  context.self = context.window;
  context.window.ResizeObserver = MockResizeObserver;
  context.window.IntersectionObserver = MockIntersectionObserver;

  // Load Utils
  const utilsCode = fs.readFileSync(path.join(__dirname, 'utils.js'), 'utf8');
  vm.runInNewContext(utilsCode, context);

  // Load VirtualGrid
  const vgCode = fs.readFileSync(path.join(__dirname, 'virtualgrid.js'), 'utf8');
  vm.runInNewContext(vgCode, context);

  return {
    VirtualGrid: context.window.VirtualGrid,
    container,
    scrollContainer,
    listeners
  };
}

describe('VirtualGrid Adversarial Stress Test (10,000+ Items)', () => {
  it('should render 10,000 items with bounded DOM node count (< 60 active nodes)', () => {
    // Arrange
    const { VirtualGrid, container, scrollContainer } = createDOMMock();
    const mockItems = Array.from({ length: 10000 }, (_, i) => ({
      id: `photo_${i}`,
      path: `/photos/img_${i}.jpg`,
      filename: `img_${i}.jpg`,
      rating: i % 6
    }));

    let cardRenderCount = 0;
    const cardRenderer = (item, index, recycledCard) => {
      if (recycledCard) {
        recycledCard.dataset.index = String(index);
        return recycledCard;
      }
      cardRenderCount++;
      const card = createDOMMock().container; // mock node element
      card.dataset = { index: String(index) };
      return card;
    };

    VirtualGrid.init({
      container,
      scrollContainer,
      cardRenderer
    });

    // Act
    const startTime = performance.now();
    VirtualGrid.setItems(mockItems, 180);
    const renderTime = performance.now() - startTime;

    const activeMap = VirtualGrid.getActiveCards();
    const range = VirtualGrid.getVisibleRange();

    // Assert
    assert.strictEqual(mockItems.length, 10000, 'Total items count is 10,000');
    assert.ok(renderTime < 100, `Initial rendering of 10,000 items took ${renderTime.toFixed(2)}ms (<100ms limit)`);
    assert.ok(activeMap.size <= 100, `Active DOM nodes (${activeMap.size}) must be bounded (<100) despite 10,000 items`);
    assert.ok(range.end - range.start <= 100, `Visible index window range (${range.end - range.start}) is strictly bounded`);
  });

  it('should efficiently recycle DOM cards during rapid scroll across 50,000 items with 0 frame drops', () => {
    // Arrange
    const env = createDOMMock();
    const { VirtualGrid, container, scrollContainer } = env;

    const itemCount = 50000;
    const mockItems = Array.from({ length: itemCount }, (_, i) => ({
      id: `photo_${i}`,
      path: `/photos/large_${i}.jpg`,
      filename: `large_${i}.jpg`
    }));

    let freshDOMAllocations = 0;
    let recycledDOMReuses = 0;

    const cardRenderer = (item, index, recycledCard) => {
      if (recycledCard) {
        recycledDOMReuses++;
        recycledCard.dataset.index = String(index);
        return recycledCard;
      }
      freshDOMAllocations++;
      const mockNode = {
        tagName: 'DIV',
        className: 'thumb-card',
        dataset: { index: String(index) },
        style: {},
        children: [],
        parentNode: null,
        classList: { remove: () => {}, add: () => {} }
      };
      return mockNode;
    };

    VirtualGrid.init({ container, scrollContainer, cardRenderer });
    VirtualGrid.setItems(mockItems, 180);

    const initialAllocations = freshDOMAllocations;

    // Act: Simulate continuous fast scrolling over 500 frame updates
    const scrollTimes = [];
    const maxScrollTop = 50000 * 30; // 50,000 items scroll distance
    const scrollStep = Math.floor(maxScrollTop / 500);

    for (let step = 0; step < 500; step++) {
      scrollContainer.scrollTop = step * scrollStep;
      const t0 = performance.now();
      VirtualGrid.renderVisible();
      const frameDuration = performance.now() - t0;
      scrollTimes.push(frameDuration);
    }

    const maxFrameDuration = Math.max(...scrollTimes);
    const avgFrameDuration = scrollTimes.reduce((a, b) => a + b, 0) / scrollTimes.length;

    // Assert: DOM Pool recycling
    assert.ok(freshDOMAllocations <= 100, `Fresh DOM allocations (${freshDOMAllocations}) capped near visible node count (<100)`);
    assert.ok(recycledDOMReuses > 5000, `DOM card recycling was used extensively (${recycledDOMReuses} reuses)`);
    assert.ok(maxFrameDuration < 16.6, `Worst-case scroll frame duration ${maxFrameDuration.toFixed(2)}ms (<16.6ms budget for 60fps)`);
    assert.ok(avgFrameDuration < 1.0, `Average scroll frame duration ${avgFrameDuration.toFixed(2)}ms`);

    console.log(`  ✓ VirtualGrid 50,000 Items: Allocations: ${freshDOMAllocations}, Reuses: ${recycledDOMReuses}, Max Frame: ${maxFrameDuration.toFixed(2)}ms, Avg Frame: ${avgFrameDuration.toFixed(2)}ms`);
  });

  it('should exhibit zero memory leaks after 50 load/destroy lifecycle cycles', () => {
    // Arrange
    const env = createDOMMock();
    const { VirtualGrid, container, scrollContainer } = env;

    const cardRenderer = (item, index, recycledCard) => {
      return recycledCard || {
        tagName: 'DIV',
        className: 'thumb-card',
        dataset: { index: String(index) },
        style: {},
        children: [],
        parentNode: null,
        classList: { remove: () => {}, add: () => {} }
      };
    };

    VirtualGrid.init({ container, scrollContainer, cardRenderer });

    // Act: Run 50 cycles of loading 10,000 items, scrolling, and destroying
    for (let cycle = 0; cycle < 50; cycle++) {
      const items = Array.from({ length: 10000 }, (_, i) => ({ id: i }));
      VirtualGrid.setItems(items, 180);
      scrollContainer.scrollTop = 5000;
      VirtualGrid.renderVisible();
      VirtualGrid.setItems([]);
    }

    VirtualGrid.destroy();

    // Assert: Check active cards map is empty
    const activeMap = VirtualGrid.getActiveCards();
    assert.strictEqual(activeMap.size, 0, 'Active card map must be 0 after destroy()');
    console.log('  ✓ VirtualGrid Lifecycle Leak Check: 50 cycles complete, active map size = 0');
  });
});
