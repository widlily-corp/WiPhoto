// ═══ Fullscreen Viewer Module ═══

const Viewer = (() => {
  let currentIndex = -1;
  let images = [];

  function init() {
    document.getElementById('viewer-close')?.addEventListener('click', close);
    document.getElementById('viewer-prev')?.addEventListener('click', prev);
    document.getElementById('viewer-next')?.addEventListener('click', next);

    const viewer = document.getElementById('fullscreen-viewer');
    viewer?.addEventListener('keydown', (e) => {
      switch (e.key) {
        case 'Escape': close(); break;
        case 'ArrowLeft': prev(); break;
        case 'ArrowRight': next(); break;
        case 'Home': goTo(0); break;
        case 'End': goTo(images.length - 1); break;
      }
    });
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

    const imgEl = document.getElementById('viewer-image');
    try {
      const b64 = await API.loadFullImage(img.path, 3000);
      imgEl.src = Utils.base64Src(b64);
    } catch {
      imgEl.src = '';
    }
  }

  function close() {
    document.getElementById('fullscreen-viewer').classList.add('hidden');
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

  return { init, open, close };
})();

window.Viewer = Viewer;
