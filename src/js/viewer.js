// ═══ Fullscreen Viewer Module ═══

const Viewer = (() => {
  let currentIndex = -1;
  let images = [];
  const preloadCache = new Map(); // path -> base64 URL

  // Zoom & Pan state
  let zoomScale = 1;
  let panX = 0;
  let panY = 0;
  let isPanning = false;
  let startPanX = 0;
  let startPanY = 0;
  let histogramTimer = null;

  function init() {
    document.getElementById('viewer-close')?.addEventListener('click', close);
    document.getElementById('viewer-prev')?.addEventListener('click', prev);
    document.getElementById('viewer-next')?.addEventListener('click', next);

    document.getElementById('viewer-zoom-fit')?.addEventListener('click', () => zoomTo('fit'));
    document.getElementById('viewer-zoom-fill')?.addEventListener('click', () => zoomTo('fill'));
    document.getElementById('viewer-zoom-100')?.addEventListener('click', () => zoomTo('100'));
    document.getElementById('viewer-zoom-200')?.addEventListener('click', () => zoomTo('200'));

    const viewer = document.getElementById('fullscreen-viewer');
    viewer?.addEventListener('keydown', (e) => {
      switch (e.key) {
        case 'Escape': close(); break;
        case 'ArrowLeft': prev(); break;
        case 'ArrowRight': next(); break;
        case 'Home': goTo(0); break;
        case 'End': goTo(images.length - 1); break;
        case 'f':
        case 'F':
          e.preventDefault();
          toggleInfoOverlay();
          break;
      }
    });

    // Setup zoom and pan mouse handlers on the viewer image
    const imgEl = document.getElementById('viewer-image');
    if (imgEl) {
      imgEl.addEventListener('dblclick', toggleZoom);
      imgEl.addEventListener('wheel', handleWheelZoom, { passive: false });
      imgEl.addEventListener('mousedown', startPanning);
      
      imgEl.onload = () => {
        resetZoom();
        drawHistogram(imgEl);

        // Trigger loaded transition
        imgEl.classList.remove('viewer-fade-in');
        void imgEl.offsetWidth; // force reflow
        imgEl.classList.add('viewer-fade-in');
      };
    }

    document.addEventListener('mousemove', handlePanning);
    document.addEventListener('mouseup', stopPanning);
  }

  function open(imageInfo) {
    images = Gallery.getFilteredImages().filter(i => !i.is_video);
    currentIndex = images.findIndex(i => i.path === imageInfo.path);
    if (currentIndex < 0) currentIndex = 0;

    show();
  }

  async function show() {
    if (currentIndex < 0 || currentIndex >= images.length) return;

    const viewer = document.getElementById('fullscreen-viewer');
    viewer.classList.remove('hidden');
    viewer.setAttribute('tabindex', '0');
    viewer.focus();

    const img = images[currentIndex];
    document.getElementById('viewer-filename').textContent = img.filename;
    document.getElementById('viewer-counter').textContent = `${currentIndex + 1} / ${images.length}`;

    // Clean active states
    resetZoom();

    // EXIF loading
    loadExif(img.path);

    const imgEl = document.getElementById('viewer-image');
    try {
      if (preloadCache.has(img.path)) {
        imgEl.src = preloadCache.get(img.path);
      } else {
        const b64 = await API.loadFullImage(img.path, 3000);
        const src = Utils.base64Src(b64);
        imgEl.src = src;
        preloadCache.set(img.path, src);
      }
    } catch (err) {
      Logger.error('Viewer', `Failed to load image at ${img.path}`, err);
      imgEl.src = '';
    }

    // Trigger preloading for next/prev images
    triggerPreloads();
  }

  function close() {
    document.getElementById('fullscreen-viewer').classList.add('hidden');
    resetZoom();
  }

  function prev() {
    if (currentIndex > 0) { currentIndex--; show(); }
  }

  function next() {
    if (currentIndex < images.length - 1) { currentIndex++; show(); }
  }

  function goTo(index) {
    if (index >= 0 && index < images.length) { currentIndex = index; show(); }
  }

  // ─── Cache Preloading ───
  async function triggerPreloads() {
    // Clean old entries to limit memory
    if (preloadCache.size > 8) {
      const keepPaths = [];
      for (let i = -2; i <= 2; i++) {
        const idx = currentIndex + i;
        if (idx >= 0 && idx < images.length) keepPaths.push(images[idx].path);
      }
      for (const key of preloadCache.keys()) {
        if (!keepPaths.includes(key)) {
          preloadCache.delete(key);
        }
      }
    }

    // Preload next
    if (currentIndex < images.length - 1) {
      const path = images[currentIndex + 1].path;
      preloadPath(path);
    }
    // Preload prev
    if (currentIndex > 0) {
      const path = images[currentIndex - 1].path;
      preloadPath(path);
    }
  }

  async function preloadPath(path) {
    if (preloadCache.has(path)) return;
    try {
      const b64 = await API.loadFullImage(path, 3000);
      preloadCache.set(path, Utils.base64Src(b64));
    } catch (err) {
      Logger.debug('Viewer', `Failed to preload image at ${path}: ${err}`);
    }
  }

  // ─── Zoom & Pan Operations ───
  function toggleZoom(e) {
    const imgEl = document.getElementById('viewer-image');
    if (!imgEl) return;

    if (zoomScale === 1) {
      zoomScale = 2.5;
      imgEl.style.transition = 'transform 180ms cubic-bezier(0.32, 0.72, 0, 1)';
      
      const rect = imgEl.getBoundingClientRect();
      const offsetX = e.clientX - rect.left - rect.width / 2;
      const offsetY = e.clientY - rect.top - rect.height / 2;
      panX = -offsetX * 1.5;
      panY = -offsetY * 1.5;
    } else {
      imgEl.style.transition = 'transform 180ms cubic-bezier(0.32, 0.72, 0, 1)';
      resetZoom();
    }
    updateTransform();
  }

  function handleWheelZoom(e) {
    e.preventDefault();
    const imgEl = document.getElementById('viewer-image');
    if (!imgEl) return;

    imgEl.style.transition = 'none'; // Instant change when wheeling
    const delta = -e.deltaY;
    const factor = delta > 0 ? 1.15 : 1 / 1.15;
    const newScale = Math.min(8, Math.max(1, zoomScale * factor));

    if (newScale === 1) {
      resetZoom();
    } else {
      zoomScale = newScale;
      updateTransform();
    }
  }

  function startPanning(e) {
    if (zoomScale <= 1) return;
    e.preventDefault();
    isPanning = true;
    startPanX = e.clientX - panX;
    startPanY = e.clientY - panY;

    const imgEl = document.getElementById('viewer-image');
    if (imgEl) {
      imgEl.style.transition = 'none';
      imgEl.style.cursor = 'grabbing';
    }
  }

  function handlePanning(e) {
    if (!isPanning) return;
    panX = e.clientX - startPanX;
    panY = e.clientY - startPanY;
    updateTransform();
  }

  function stopPanning() {
    if (isPanning) {
      isPanning = false;
      const imgEl = document.getElementById('viewer-image');
      if (imgEl) {
        imgEl.style.cursor = 'grab';
      }
    }
  }

  function resetZoom() {
    zoomScale = 1;
    panX = 0;
    panY = 0;
    updateTransform();

    // Sync UI buttons
    document.querySelectorAll('.viewer-zoom-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById('viewer-zoom-fit')?.classList.add('active');
  }

  function updateTransform() {
    const imgEl = document.getElementById('viewer-image');
    if (imgEl) {
      imgEl.style.transform = `translate(${panX}px, ${panY}px) scale(${zoomScale})`;
      imgEl.style.cursor = zoomScale > 1 ? 'grab' : 'default';

      if (zoomScale === 1) {
        document.querySelectorAll('.viewer-zoom-btn').forEach(btn => btn.classList.remove('active'));
        document.getElementById('viewer-zoom-fit')?.classList.add('active');
      } else {
        document.getElementById('viewer-zoom-fit')?.classList.remove('active');
      }
    }
  }

  function zoomTo(mode) {
    const imgEl = document.getElementById('viewer-image');
    if (!imgEl) return;

    // Reset active button class
    document.querySelectorAll('.viewer-zoom-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById(`viewer-zoom-${mode}`)?.classList.add('active');

    imgEl.style.transition = 'transform 180ms cubic-bezier(0.32, 0.72, 0, 1)';

    if (mode === 'fit') {
      resetZoom();
    } else {
      const scaleX = window.innerWidth / imgEl.naturalWidth;
      const scaleY = window.innerHeight / imgEl.naturalHeight;
      const baseScale = Math.min(scaleX, scaleY);
      
      if (mode === 'fill') {
        zoomScale = Math.max(scaleX, scaleY) / baseScale;
      } else if (mode === '100') {
        zoomScale = 1 / baseScale;
      } else if (mode === '200') {
        zoomScale = 2 / baseScale;
      }
      
      panX = 0;
      panY = 0;
      updateTransform();
    }
  }

  function toggleInfoOverlay() {
    const overlay = document.getElementById('viewer-info-overlay');
    if (overlay) {
      overlay.classList.toggle('hidden');
    }
  }

  // ─── EXIF Loading ───
  async function loadExif(path) {
    const exifEl = document.getElementById('viewer-exif');
    if (!exifEl) return;
    exifEl.textContent = 'Загрузка EXIF...';

    try {
      const data = await API.readExif(path);
      const cam = data.find(e => e.key === 'Камера')?.value || 'Unknown Camera';
      const lens = data.find(e => e.key === 'Объектив')?.value;
      const lensStr = lens ? `\n${lens}` : '';
      const exp = data.find(e => e.key === 'Выдержка')?.value || '';
      const f = data.find(e => e.key === 'Диафрагма')?.value;
      const fStr = f ? `f/${f}` : '';
      const iso = data.find(e => e.key === 'ISO')?.value;
      const isoStr = iso ? `ISO ${iso}` : '';
      const focal = data.find(e => e.key === 'Фокусное расстояние')?.value;
      const focalStr = focal ? `${focal}mm` : '';
      
      const settings = [exp, fStr, isoStr, focalStr].filter(Boolean).join('  ');
      exifEl.textContent = `${cam}${lensStr}\n${settings}`;
    } catch (err) {
      Logger.warn('Viewer', `Failed to load EXIF for ${path}`, err);
      exifEl.textContent = 'EXIF не найден';
    }
  }

  // ─── Color Histogram Generation (Client-Side) ───
  function drawHistogram(img) {
    const canvas = document.getElementById('viewer-histogram');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    clearTimeout(histogramTimer);
    histogramTimer = setTimeout(() => {
      // Create a scaling canvas to sample pixels quickly
      const sampleCanvas = document.createElement('canvas');
      sampleCanvas.width = 120;
      sampleCanvas.height = 80;
      const sampleCtx = sampleCanvas.getContext('2d');

      try {
        sampleCtx.drawImage(img, 0, 0, sampleCanvas.width, sampleCanvas.height);
        const imgData = sampleCtx.getImageData(0, 0, sampleCanvas.width, sampleCanvas.height);
        const data = imgData.data;

        const rHist = new Array(256).fill(0);
        const gHist = new Array(256).fill(0);
        const bHist = new Array(256).fill(0);

        for (let i = 0; i < data.length; i += 4) {
          rHist[data[i]]++;
          gHist[data[i + 1]]++;
          bHist[data[i + 2]]++;
        }

        // Find max value to normalize height
        const maxVal = Math.max(...rHist, ...gHist, ...bHist);
        if (maxVal === 0) return;

        const w = canvas.width;
        const h = canvas.height;
        const step = w / 256;

        ctx.lineWidth = 1.5;
        ctx.globalCompositeOperation = 'screen';

        const drawChannel = (hist, color) => {
          ctx.strokeStyle = color;
          ctx.beginPath();
          for (let i = 0; i < 256; i++) {
            const x = i * step;
            const y = h - (hist[i] / maxVal) * h * 0.9;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          }
          ctx.stroke();
        };

        drawChannel(rHist, 'rgba(239, 68, 68, 0.7)');
        drawChannel(gHist, 'rgba(34, 197, 94, 0.7)');
        drawChannel(bHist, 'rgba(59, 130, 246, 0.7)');
      } catch (err) {
        Logger.debug('Viewer', `Failed to draw histogram: ${err}`);
      }
    }, 150);
  }

  return { init, open, close };
})();

window.Viewer = Viewer;
