// ═══ Slideshow Module ═══

const Slideshow = (() => {
  let images = [];
  let currentIndex = -1;
  let isPlaying = false;
  let timerId = null;
  const slideInterval = 4000; // 4 seconds per slide

  const overlay = () => document.getElementById('slideshow-overlay');
  const imageEl = () => document.getElementById('slideshow-image');
  const pauseBtn = () => document.getElementById('slideshow-pause');

  function init() {
    document.getElementById('slideshow-prev')?.addEventListener('click', prev);
    document.getElementById('slideshow-pause')?.addEventListener('click', togglePlay);
    document.getElementById('slideshow-next')?.addEventListener('click', next);
    document.getElementById('slideshow-close')?.addEventListener('click', stop);
  }

  function start() {
    // Gather non-video images from current gallery view
    images = Gallery.getFilteredImages().filter(img => !img.is_video);
    if (images.length === 0) {
      Utils.toast('Нет изображений для слайдшоу', 'warning');
      return;
    }

    // Determine start index based on selection
    const selected = Gallery.getSelectedImages().filter(img => !img.is_video);
    if (selected.length > 0) {
      currentIndex = images.findIndex(img => img.path === selected[0].path);
    }
    if (currentIndex < 0) {
      currentIndex = 0;
    }

    // Show overlay
    overlay().classList.remove('hidden');
    isPlaying = true;
    updatePauseButton();

    // Display first image
    showSlide();

    // Start timer
    startTimer();

    // Add local key listener
    window.addEventListener('keydown', handleSlideshowKeys);
  }

  function stop() {
    isPlaying = false;
    stopTimer();
    overlay().classList.add('hidden');
    
    // Clean up key listeners
    window.removeEventListener('keydown', handleSlideshowKeys);
  }

  function togglePlay() {
    isPlaying = !isPlaying;
    updatePauseButton();
    if (isPlaying) {
      startTimer();
      next(); // Advance immediately when resuming
    } else {
      stopTimer();
    }
  }

  function next() {
    if (images.length === 0) return;
    currentIndex = (currentIndex + 1) % images.length;
    showSlide();
    if (isPlaying) resetTimer();
  }

  function prev() {
    if (images.length === 0) return;
    currentIndex = (currentIndex - 1 + images.length) % images.length;
    showSlide();
    if (isPlaying) resetTimer();
  }

  async function showSlide() {
    if (currentIndex < 0 || currentIndex >= images.length) return;
    const imgInfo = images[currentIndex];
    const img = imageEl();
    if (!img) return;

    // Crossfade effect (fade out, update source, fade in)
    img.style.opacity = '0';

    try {
      const b64 = await API.loadFullImage(imgInfo.path, 2500);
      
      // Update image source once loaded
      const tempImg = new Image();
      tempImg.onload = () => {
        img.src = Utils.base64Src(b64);
        img.style.opacity = '1';
      };
      tempImg.src = Utils.base64Src(b64);
      
    } catch (err) {
      Logger.error('Slideshow', `Failed to load slide at ${imgInfo.path}`, err);
      img.src = '';
      img.style.opacity = '0.3'; // Dimmed fallback
    }
  }

  function startTimer() {
    stopTimer();
    timerId = setInterval(next, slideInterval);
  }

  function stopTimer() {
    if (timerId) {
      clearInterval(timerId);
      timerId = null;
    }
  }

  function resetTimer() {
    startTimer();
  }

  function updatePauseButton() {
    const btn = pauseBtn();
    if (btn) {
      btn.textContent = isPlaying ? '⏸' : '▶';
    }
  }

  function handleSlideshowKeys(e) {
    if (overlay().classList.contains('hidden')) return;

    switch (e.key) {
      case ' ':
        e.preventDefault();
        togglePlay();
        break;
      case 'ArrowRight':
        e.preventDefault();
        next();
        break;
      case 'ArrowLeft':
        e.preventDefault();
        prev();
        break;
      case 'Escape':
        e.preventDefault();
        stop();
        break;
    }
  }

  return { init, start, stop };
})();

window.Slideshow = Slideshow;
