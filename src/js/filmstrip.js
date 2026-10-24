const Filmstrip = (() => {
  let images = [];
  let currentIndex = -1;
  let hideTimeout = null;
  let isInitialized = false;

  function init() {
    if (isInitialized) return;
    isInitialized = true;
    const container = document.getElementById('filmstrip-container');
    if (!container) return;

    // Mouse move logic to unhide
    const viewer = document.getElementById('fullscreen-viewer');
    if (viewer) {
      viewer.addEventListener('mousemove', (e) => {
        if (window.innerHeight - e.clientY < 150) {
          show();
        } else {
          startAutoHide();
        }
      });
    }

    container.addEventListener('mouseenter', () => {
      clearTimeout(hideTimeout);
      container.classList.remove('hidden');
    });

    container.addEventListener('mouseleave', () => {
      startAutoHide();
    });
    
    // Support horizontal scroll with wheel
    container.addEventListener('wheel', (e) => {
      e.preventDefault();
      container.scrollLeft += e.deltaY;
    }, { passive: false });

    // Event delegation for thumbnail click
    container.addEventListener('click', (e) => {
      const thumb = e.target.closest('.filmstrip-thumb');
      if (!thumb) return;
      const idx = parseInt(thumb.dataset.index, 10);
      if (!isNaN(idx) && images[idx] && typeof Viewer !== 'undefined') {
        Viewer.open(images[idx]);
      }
    });
  }

  function update(imgList, currentIdx) {
    images = imgList;
    currentIndex = currentIdx;
    render();
    show();
    startAutoHide();
  }

  function toggle() {
    const container = document.getElementById('filmstrip-container');
    if (container) {
      if (container.classList.contains('hidden')) {
        show();
        startAutoHide();
      } else {
        container.classList.add('hidden');
        clearTimeout(hideTimeout);
      }
    }
  }

  function show() {
    const container = document.getElementById('filmstrip-container');
    if (container) container.classList.remove('hidden');
  }

  function startAutoHide() {
    clearTimeout(hideTimeout);
    hideTimeout = setTimeout(() => {
      const container = document.getElementById('filmstrip-container');
      if (container) container.classList.add('hidden');
    }, 3000);
  }

  function render() {
    const container = document.getElementById('filmstrip-container');
    if (!container) return;

    container.innerHTML = '';
    if (images.length === 0) return;

    const start = Math.max(0, currentIndex - 10);
    const end = Math.min(images.length - 1, currentIndex + 10);

    for (let i = start; i <= end; i++) {
      const img = images[i];
      const thumb = document.createElement('img');
      thumb.className = `filmstrip-thumb ${i === currentIndex ? 'active' : ''}`;
      thumb.src = Utils.assetUrl(img.thumbnail || img.path);
      thumb.dataset.index = i;
      container.appendChild(thumb);
    }
    
    // Auto-scroll to center active thumb
    setTimeout(() => {
      const activeThumb = container.querySelector('.filmstrip-thumb.active');
      if (activeThumb) {
        const centerPos = activeThumb.offsetLeft - (container.offsetWidth / 2) + (activeThumb.offsetWidth / 2);
        container.scrollTo({ left: centerPos, behavior: 'smooth' });
      }
    }, 50);
  }

  return { init, update, toggle };
})();

window.Filmstrip = Filmstrip;
