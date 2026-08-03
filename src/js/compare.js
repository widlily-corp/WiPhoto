const CompareMode = (() => {
  let images = [];
  let leftIndex = -1;
  let rightIndex = -1;
  
  let zoomScale = 1;
  let panX = 0;
  let panY = 0;
  let isPanning = false;
  let startPanX = 0;
  let startPanY = 0;

  function init() {
    const viewer = document.getElementById('compare-viewer');
    if (!viewer) return;
    
    viewer.addEventListener('keydown', (e) => {
      switch (e.key) {
        case 'Escape': close(); break;
        case 'ArrowLeft': 
          prev(e.shiftKey); 
          break;
        case 'ArrowRight': 
          next(e.shiftKey); 
          break;
      }
    });
    
    // Zoom/Pan
    viewer.addEventListener('wheel', handleWheelZoom, { passive: false });
    viewer.addEventListener('mousedown', startPanning);
    document.addEventListener('mousemove', handlePanning);
    document.addEventListener('mouseup', stopPanning);

    document.getElementById('compare-close')?.addEventListener('click', close);
  }

  function open(imgList, leftPath, rightPath) {
    images = imgList;
    leftIndex = images.findIndex(i => i.path === leftPath);
    rightIndex = images.findIndex(i => i.path === rightPath);
    
    if (leftIndex < 0) leftIndex = 0;
    if (rightIndex < 0) rightIndex = Math.min(1, images.length - 1);
    
    const fsv = document.getElementById('fullscreen-viewer');
    if (fsv) fsv.classList.add('hidden');
    
    const viewer = document.getElementById('compare-viewer');
    if (viewer) {
      viewer.classList.remove('hidden');
      viewer.setAttribute('tabindex', '0');
      viewer.focus();
    }
    
    resetZoom();
    updateUI();
  }

  function close() {
    const viewer = document.getElementById('compare-viewer');
    if (viewer) viewer.classList.add('hidden');
    resetZoom();
  }

  function updateUI() {
    const leftImg = images[leftIndex];
    const rightImg = images[rightIndex];
    
    const leftEl = document.getElementById('compare-left-img');
    const rightEl = document.getElementById('compare-right-img');
    
    if (leftImg && leftEl) {
      leftEl.src = Utils.assetUrl(leftImg.thumbnail || leftImg.path);
      const infoLeft = document.getElementById('compare-left-info');
      if (infoLeft) {
        infoLeft.innerHTML = `<strong>${leftImg.filename}</strong><br/>${leftImg.camera_model || 'Unknown Camera'} • ${leftImg.rating > 0 ? '★'.repeat(leftImg.rating) : 'No Rating'}`;
      }
    }
    if (rightImg && rightEl) {
      rightEl.src = Utils.assetUrl(rightImg.thumbnail || rightImg.path);
      const infoRight = document.getElementById('compare-right-info');
      if (infoRight) {
        infoRight.innerHTML = `<strong>${rightImg.filename}</strong><br/>${rightImg.camera_model || 'Unknown Camera'} • ${rightImg.rating > 0 ? '★'.repeat(rightImg.rating) : 'No Rating'}`;
      }
    }
    
    updateTransform();
  }

  function prev(shiftKey) {
    if (shiftKey) {
      if (leftIndex > 0) leftIndex--;
    } else {
      if (rightIndex > 0) rightIndex--;
    }
    updateUI();
  }

  function next(shiftKey) {
    if (shiftKey) {
      if (leftIndex < images.length - 1) leftIndex++;
    } else {
      if (rightIndex < images.length - 1) rightIndex++;
    }
    updateUI();
  }

  function handleWheelZoom(e) {
    e.preventDefault();
    const delta = -e.deltaY;
    const factor = delta > 0 ? 1.15 : 1 / 1.15;
    zoomScale = Math.min(8, Math.max(1, zoomScale * factor));
    if (zoomScale === 1) {
      resetZoom();
    } else {
      updateTransform();
    }
  }

  function startPanning(e) {
    if (zoomScale <= 1) return;
    e.preventDefault();
    isPanning = true;
    startPanX = e.clientX - panX;
    startPanY = e.clientY - panY;
    document.getElementById('compare-viewer').style.cursor = 'grabbing';
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
      document.getElementById('compare-viewer').style.cursor = zoomScale > 1 ? 'grab' : 'default';
    }
  }

  function resetZoom() {
    zoomScale = 1;
    panX = 0;
    panY = 0;
    updateTransform();
  }

  function updateTransform() {
    const transformStr = `translate(${panX}px, ${panY}px) scale(${zoomScale})`;
    const leftEl = document.getElementById('compare-left-img');
    const rightEl = document.getElementById('compare-right-img');
    
    if (leftEl) {
      leftEl.style.transform = transformStr;
      leftEl.parentElement.style.cursor = zoomScale > 1 ? 'grab' : 'default';
    }
    if (rightEl) {
      rightEl.style.transform = transformStr;
      rightEl.parentElement.style.cursor = zoomScale > 1 ? 'grab' : 'default';
    }
  }

  return { init, open, close };
})();

window.CompareMode = CompareMode;
