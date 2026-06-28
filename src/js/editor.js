// ═══ Editor Module ═══

const Editor = (() => {
  let currentImage = null;
  let operations = [];
  let historyStack = [];
  let historyIndex = -1;
  let isBeforeAfter = false;
  let updateTimer = null;

  // v3: Crop State
  let activeCropRect = null;
  let isCropActive = false;
  let cropRatio = 'free';
  let cropBox = { left: 0, top: 0, width: 0, height: 0 };

  // v3: Built-in Presets
  const presets = {
    cinematic: { exposure: 15, contrast: 20, temperature: 10, tint: -5, shadows: 10, saturation: -10 },
    bw: { saturation: -100, contrast: 30, exposure: 10, clarity: 15 },
    vibrant: { saturation: 20, contrast: 10, vibrance: 25 },
    moody: { exposure: -25, contrast: 20, temperature: -10, shadows: -15, vignette: 25 },
    film: { temperature: 15, contrast: -10, whites: -10, blacks: 10, clarity: -15 },
    warm: { temperature: 25, contrast: 5, vibrance: -10, saturation: 5 }
  };

  function init() {
    // Slider controls
    document.querySelectorAll('.slider-control').forEach(ctrl => {
      const input = ctrl.querySelector('input[type="range"]');
      const valueSpan = ctrl.querySelector('.slider-value');
      const tool = ctrl.dataset.tool;

      input.addEventListener('input', () => {
        valueSpan.textContent = input.value;
      });

      input.addEventListener('change', () => {
        const value = parseFloat(input.value);
        setToolValue(tool, value);
      });

      // Double-click to reset
      ctrl.querySelector('label').addEventListener('dblclick', () => {
        input.value = 0;
        valueSpan.textContent = '0';
        setToolValue(tool, 0);
      });
    });

    // Toolbar buttons
    document.getElementById('btn-editor-back')?.addEventListener('click', close);
    document.getElementById('btn-undo')?.addEventListener('click', undo);
    document.getElementById('btn-redo')?.addEventListener('click', redo);
    document.getElementById('btn-before-after')?.addEventListener('click', toggleBeforeAfter);
    document.getElementById('btn-zoom-fit')?.addEventListener('click', zoomFit);
    document.getElementById('btn-zoom-100')?.addEventListener('click', zoom100);
    document.getElementById('btn-rotate-cw')?.addEventListener('click', () => addOperation('rotate', 90));
    document.getElementById('btn-flip-h')?.addEventListener('click', () => addOperation('flip_h', 1));
    document.getElementById('btn-flip-v')?.addEventListener('click', () => addOperation('flip_v', 1));
    document.getElementById('btn-save-edit')?.addEventListener('click', saveImage);

    // Crop triggers
    document.getElementById('btn-crop-tool')?.addEventListener('click', startCrop);
    document.getElementById('btn-crop-apply')?.addEventListener('click', confirmCrop);
    document.getElementById('btn-crop-cancel')?.addEventListener('click', cancelCrop);

    // Crop ratios
    document.querySelectorAll('.crop-ratio-toolbar button[data-ratio]').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.crop-ratio-toolbar button[data-ratio]').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        cropRatio = btn.dataset.ratio;
        updateCropBoxRatio();
      });
    });

    // Built-in presets triggers
    document.getElementById('btn-preset-cinematic')?.addEventListener('click', () => applyPreset('cinematic'));
    document.getElementById('btn-preset-bw')?.addEventListener('click', () => applyPreset('bw'));
    document.getElementById('btn-preset-vibrant')?.addEventListener('click', () => applyPreset('vibrant'));
    document.getElementById('btn-preset-moody')?.addEventListener('click', () => applyPreset('moody'));
    document.getElementById('btn-preset-film')?.addEventListener('click', () => applyPreset('film'));
    document.getElementById('btn-preset-warm')?.addEventListener('click', () => applyPreset('warm'));

    // Custom presets triggers
    document.getElementById('btn-save-preset')?.addEventListener('click', saveCustomPreset);

    initCropBoxDragging();
  }

  function open(imageInfo) {
    currentImage = imageInfo;
    operations = [];
    historyStack = [[]];
    historyIndex = 0;
    isBeforeAfter = false;
    activeCropRect = null;
    isCropActive = false;

    // Reset all sliders
    document.querySelectorAll('.slider-control').forEach(ctrl => {
      const input = ctrl.querySelector('input[type="range"]');
      const valueSpan = ctrl.querySelector('.slider-value');
      input.value = 0;
      valueSpan.textContent = '0';
    });

    // Hide crop overlays
    document.getElementById('crop-ratio-toolbar')?.classList.add('hidden');
    document.getElementById('crop-box')?.classList.add('hidden');

    // Load the image
    loadPreview();
    renderHistory();
    renderCustomPresetsList();

    // Show editor view
    App.switchView('editor');
  }

  function close() {
    currentImage = null;
    App.switchView('gallery');
  }

  function setToolValue(tool, value) {
    // Update or add the operation
    const existing = operations.findIndex(op => op.tool === tool);
    if (value === 0 && existing >= 0) {
      operations.splice(existing, 1);
    } else if (existing >= 0) {
      operations[existing].value = value;
    } else if (value !== 0) {
      operations.push({ tool, value });
    }

    pushHistory();
    scheduleUpdate();
  }

  function addOperation(tool, value) {
    operations.push({ tool, value });
    pushHistory();
    scheduleUpdate();
  }

  function pushHistory() {
    historyStack = historyStack.slice(0, historyIndex + 1);
    historyStack.push([...operations.map(op => ({ ...op }))]);
    historyIndex = historyStack.length - 1;
    renderHistory();
  }

  function undo() {
    if (historyIndex > 0) {
      historyIndex--;
      operations = historyStack[historyIndex].map(op => ({ ...op }));
      syncSliders();
      scheduleUpdate();
      renderHistory();
    }
  }

  function redo() {
    if (historyIndex < historyStack.length - 1) {
      historyIndex++;
      operations = historyStack[historyIndex].map(op => ({ ...op }));
      syncSliders();
      scheduleUpdate();
      renderHistory();
    }
  }

  function syncSliders() {
    document.querySelectorAll('.slider-control').forEach(ctrl => {
      const tool = ctrl.dataset.tool;
      const input = ctrl.querySelector('input[type="range"]');
      const valueSpan = ctrl.querySelector('.slider-value');
      const op = operations.find(o => o.tool === tool);
      input.value = op ? op.value : 0;
      valueSpan.textContent = op ? op.value : '0';
    });
  }

  function scheduleUpdate() {
    clearTimeout(updateTimer);
    updateTimer = setTimeout(loadPreview, 300);
  }

  async function loadPreview() {
    if (!currentImage) return;

    const imgEl = document.getElementById('editor-image');
    try {
      imgEl.onload = () => {
        applyVisualCropPreview();
      };

      if (operations.length === 0) {
        const b64 = await API.loadFullImage(currentImage.path, 2000);
        imgEl.src = Utils.base64Src(b64);
      } else {
        const b64 = await API.applyEdit(currentImage.path, operations, 2000);
        imgEl.src = Utils.base64Src(b64);
      }
    } catch (e) {
      Utils.toast(`Ошибка: ${e}`, 'error');
    }
  }

  function toggleBeforeAfter() {
    isBeforeAfter = !isBeforeAfter;
    const btn = document.getElementById('btn-before-after');
    if (btn) btn.classList.toggle('active', isBeforeAfter);

    if (isBeforeAfter && currentImage) {
      API.loadFullImage(currentImage.path, 2000).then(b64 => {
        document.getElementById('editor-image').src = Utils.base64Src(b64);
      });
    } else {
      loadPreview();
    }
  }

  function zoomFit() {
    const imgEl = document.getElementById('editor-image');
    if (imgEl) {
      imgEl.style.maxWidth = '100%';
      imgEl.style.maxHeight = '100%';
    }
  }

  function zoom100() {
    const imgEl = document.getElementById('editor-image');
    if (imgEl) {
      imgEl.style.maxWidth = 'none';
      imgEl.style.maxHeight = 'none';
    }
  }

  async function saveImage() {
    if (!currentImage || (operations.length === 0 && !activeCropRect)) {
      Utils.toast('Нечего сохранять', 'warning');
      return;
    }

    try {
      const outputPath = await API.openSaveDialog(currentImage.path);
      if (outputPath) {
        Utils.toast('Выполняется сохранение...', 'info', 3000);
        await API.saveCroppedEditedImage(currentImage.path, activeCropRect, operations, outputPath, 95);
        Utils.toast('Изображение сохранено', 'success');
      }
    } catch (e) {
      Utils.toast(`Ошибка сохранения: ${e}`, 'error');
    }
  }

  function renderHistory() {
    const list = document.getElementById('history-list');
    if (!list) return;
    list.innerHTML = '';

    const toolNames = {
      exposure: 'Экспозиция', contrast: 'Контраст', highlights: 'Светлые',
      shadows: 'Тени', whites: 'Белые', blacks: 'Чёрные',
      temperature: 'Температура', tint: 'Оттенок', vibrance: 'Сочность',
      saturation: 'Насыщенность', clarity: 'Чёткость', sharpness: 'Резкость',
      vignette: 'Виньетка', rotate: 'Поворот', flip_h: 'Отразить ↔',
      flip_v: 'Отразить ↕', brightness: 'Яркость', crop: 'Обрезка',
    };

    const origItem = Utils.el('div', {
      className: `history-item${historyIndex === 0 ? ' active' : ''}`,
      onClick: () => goToHistoryIndex(0),
    }, [
      Utils.el('div', { className: 'history-dot' }),
      document.createTextNode('Оригинал'),
    ]);
    list.appendChild(origItem);

    historyStack.forEach((ops, idx) => {
      if (idx === 0) return;
      const lastOp = ops[ops.length - 1];
      const name = lastOp ? (toolNames[lastOp.tool] || lastOp.tool) : 'Изменение';
      const value = lastOp ? ` (${lastOp.value > 0 ? '+' : ''}${lastOp.value})` : '';

      const item = Utils.el('div', {
        className: `history-item${idx === historyIndex ? ' active' : ''}${idx > historyIndex ? ' future' : ''}`,
        onClick: () => goToHistoryIndex(idx),
      }, [
        Utils.el('div', { className: 'history-dot' }),
        document.createTextNode(`${name}${value}`),
      ]);
      list.appendChild(item);
    });
  }

  function goToHistoryIndex(idx) {
    historyIndex = idx;
    operations = historyStack[idx].map(op => ({ ...op }));
    syncSliders();
    loadPreview();
    renderHistory();
  }

  // ─── v3: Presets Logic ───
  function applyPreset(name) {
    const preset = presets[name];
    if (!preset) return;

    const nonSliderTools = ['rotate', 'flip_h', 'flip_v'];
    operations = operations.filter(op => nonSliderTools.includes(op.tool));

    for (const [tool, value] of Object.entries(preset)) {
      if (value !== 0) {
        operations.push({ tool, value });
      }
    }

    syncSliders();
    pushHistory();
    loadPreview();
    Utils.toast(`Применен пресет: ${name}`, 'success');
  }

  function saveCustomPreset() {
    const name = prompt('Введите имя для нового пресета:');
    if (!name) return;

    const sliderTools = [
      'exposure', 'contrast', 'highlights', 'shadows', 'whites', 'blacks',
      'temperature', 'tint', 'vibrance', 'saturation', 'clarity', 'sharpness', 'vignette'
    ];

    const presetData = {};
    operations.forEach(op => {
      if (sliderTools.includes(op.tool)) {
        presetData[op.tool] = op.value;
      }
    });

    const saved = localStorage.getItem('wiphoto-user-presets');
    const presetsMap = saved ? JSON.parse(saved) : {};
    presetsMap[name] = presetData;
    localStorage.setItem('wiphoto-user-presets', JSON.stringify(presetsMap));

    Utils.toast(`Пресет "${name}" сохранен`, 'success');
    renderCustomPresetsList();
  }

  function renderCustomPresetsList() {
    const container = document.getElementById('custom-presets-list');
    if (!container) return;
    container.innerHTML = '';

    const saved = localStorage.getItem('wiphoto-user-presets');
    if (!saved) return;

    const presetsMap = JSON.parse(saved);
    const keys = Object.keys(presetsMap);

    keys.forEach(key => {
      const item = Utils.el('div', {
        className: 'custom-preset-item',
        style: 'display: flex; align-items: center; justify-content: space-between; padding: 4px var(--space-xs); border-radius: var(--radius-sm); cursor: pointer;'
      }, [
        Utils.el('span', {
          className: 'preset-apply-link',
          textContent: key,
          style: 'flex: 1; font-size: 11px; color: var(--text-secondary);',
          onClick: () => applyCustomPreset(key, presetsMap[key])
        }),
        Utils.el('button', {
          className: 'preset-delete-btn',
          textContent: '✕',
          style: 'background: transparent; border: none; color: var(--text-muted); cursor: pointer; font-size: 10px;',
          onClick: (e) => {
            e.stopPropagation();
            deleteCustomPreset(key);
          }
        })
      ]);
      container.appendChild(item);
    });
  }

  function applyCustomPreset(name, presetData) {
    const nonSliderTools = ['rotate', 'flip_h', 'flip_v'];
    operations = operations.filter(op => nonSliderTools.includes(op.tool));

    for (const [tool, value] of Object.entries(presetData)) {
      if (value !== 0) {
        operations.push({ tool, value });
      }
    }

    syncSliders();
    pushHistory();
    loadPreview();
    Utils.toast(`Применен пресет: ${name}`, 'success');
  }

  function deleteCustomPreset(name) {
    const saved = localStorage.getItem('wiphoto-user-presets');
    if (!saved) return;
    const presetsMap = JSON.parse(saved);
    delete presetsMap[name];
    localStorage.setItem('wiphoto-user-presets', JSON.stringify(presetsMap));
    renderCustomPresetsList();
    Utils.toast(`Пресет "${name}" удален`, 'success');
  }

  // ─── v3: Crop Visual Control ───
  function startCrop() {
    isCropActive = true;
    document.getElementById('crop-ratio-toolbar')?.classList.remove('hidden');
    
    const cropBoxEl = document.getElementById('crop-box');
    cropBoxEl?.classList.remove('hidden');

    const imgEl = document.getElementById('editor-image');
    const wrapper = document.getElementById('editor-canvas-wrapper');
    if (!imgEl || !wrapper) return;

    // Temporarily reset crop styles to show full image for crop adjustment
    wrapper.style.width = '';
    wrapper.style.height = '';
    imgEl.style.position = '';
    imgEl.style.width = '';
    imgEl.style.height = '';
    imgEl.style.left = '';
    imgEl.style.top = '';
    imgEl.style.maxWidth = '100%';
    imgEl.style.maxHeight = '100%';

    // Reset crop ratio choice in UI
    document.querySelectorAll('.crop-ratio-toolbar button[data-ratio]').forEach(b => {
      b.classList.toggle('active', b.dataset.ratio === 'free');
    });
    cropRatio = 'free';

    const w = imgEl.clientWidth * 0.8;
    const h = imgEl.clientHeight * 0.8;
    const left = (imgEl.clientWidth - w) / 2;
    const top = (imgEl.clientHeight - h) / 2;

    cropBox = { left, top, width: w, height: h };
    applyCropBoxStyles();
  }

  function confirmCrop() {
    const imgEl = document.getElementById('editor-image');
    if (!imgEl || !currentImage) return;

    const scaleX = currentImage.width / imgEl.clientWidth;
    const scaleY = currentImage.height / imgEl.clientHeight;

    activeCropRect = {
      x: Math.round(cropBox.left * scaleX),
      y: Math.round(cropBox.top * scaleY),
      width: Math.round(cropBox.width * scaleX),
      height: Math.round(cropBox.height * scaleY),
    };

    // Clamp
    activeCropRect.x = Math.max(0, Math.min(activeCropRect.x, currentImage.width));
    activeCropRect.y = Math.max(0, Math.min(activeCropRect.y, currentImage.height));
    activeCropRect.width = Math.max(20, Math.min(activeCropRect.width, currentImage.width - activeCropRect.x));
    activeCropRect.height = Math.max(20, Math.min(activeCropRect.height, currentImage.height - activeCropRect.y));

    // Register a crop step in operations history
    const existingIdx = operations.findIndex(op => op.tool === 'crop');
    if (existingIdx >= 0) {
      operations[existingIdx].value = activeCropRect;
    } else {
      operations.push({ tool: 'crop', value: activeCropRect });
    }

    pushHistory();
    cancelCrop();
    applyVisualCropPreview();
  }

  function cancelCrop() {
    isCropActive = false;
    document.getElementById('crop-ratio-toolbar')?.classList.add('hidden');
    document.getElementById('crop-box')?.classList.add('hidden');
    applyVisualCropPreview();
  }

  function applyCropBoxStyles() {
    const el = document.getElementById('crop-box');
    if (!el) return;
    el.style.left = `${cropBox.left}px`;
    el.style.top = `${cropBox.top}px`;
    el.style.width = `${cropBox.width}px`;
    el.style.height = `${cropBox.height}px`;
  }

  function applyVisualCropPreview() {
    const wrapper = document.getElementById('editor-canvas-wrapper');
    const imgEl = document.getElementById('editor-image');
    if (!wrapper || !imgEl || !currentImage) return;

    // Check if crop operation exists in history
    const cropOp = operations.find(op => op.tool === 'crop');
    const crop = cropOp ? cropOp.value : null;

    if (crop) {
      const container = document.getElementById('editor-canvas');
      const containerW = container.clientWidth - 32;
      const containerH = container.clientHeight - 32;

      // Calculate fitted size of the full image in the container
      const imgRatio = currentImage.width / currentImage.height;
      const containerRatio = containerW / containerH;

      let displayW, displayH;
      if (imgRatio > containerRatio) {
        displayW = containerW;
        displayH = containerW / imgRatio;
      } else {
        displayH = containerH;
        displayW = containerH * imgRatio;
      }

      const scaleX = displayW / currentImage.width;
      const scaleY = displayH / currentImage.height;
      
      const w = crop.width * scaleX;
      const h = crop.height * scaleY;
      const left = crop.x * scaleX;
      const top = crop.y * scaleY;

      wrapper.style.width = `${w}px`;
      wrapper.style.height = `${h}px`;
      imgEl.style.position = 'absolute';
      imgEl.style.width = `${displayW}px`;
      imgEl.style.height = `${displayH}px`;
      imgEl.style.left = `-${left}px`;
      imgEl.style.top = `-${top}px`;
      imgEl.style.maxWidth = 'none';
      imgEl.style.maxHeight = 'none';
    } else {
      wrapper.style.width = '';
      wrapper.style.height = '';
      imgEl.style.position = '';
      imgEl.style.width = '';
      imgEl.style.height = '';
      imgEl.style.left = '';
      imgEl.style.top = '';
      imgEl.style.maxWidth = '100%';
      imgEl.style.maxHeight = '100%';
    }
  }

  function updateCropBoxRatio() {
    if (cropRatio === 'free') return;
    const ratio = parseFloat(cropRatio);

    const imgEl = document.getElementById('editor-image');
    if (!imgEl) return;

    const maxW = imgEl.clientWidth;
    const maxH = imgEl.clientHeight;

    let w = cropBox.width;
    let h = w / ratio;
    if (h > maxH) {
      h = maxH * 0.8;
      w = h * ratio;
    }

    cropBox.width = w;
    cropBox.height = h;

    if (cropBox.left + w > maxW) cropBox.left = maxW - w;
    if (cropBox.top + h > maxH) cropBox.top = maxH - h;

    applyCropBoxStyles();
  }

  function initCropBoxDragging() {
    // Drag entire crop box
    const box = document.getElementById('crop-box');
    if (!box) return;

    box.addEventListener('mousedown', (e) => {
      if (e.target.classList.contains('crop-handle')) return;
      e.preventDefault();

      const startX = e.clientX;
      const startY = e.clientY;
      const startLeft = cropBox.left;
      const startTop = cropBox.top;

      const imgEl = document.getElementById('editor-image');
      if (!imgEl) return;
      const maxW = imgEl.clientWidth;
      const maxH = imgEl.clientHeight;

      const onMouseMove = (ev) => {
        const dx = ev.clientX - startX;
        const dy = ev.clientY - startY;

        let newLeft = Math.max(0, startLeft + dx);
        let newTop = Math.max(0, startTop + dy);

        if (newLeft + cropBox.width > maxW) newLeft = maxW - cropBox.width;
        if (newTop + cropBox.height > maxH) newTop = maxH - cropBox.height;

        cropBox.left = newLeft;
        cropBox.top = newTop;
        applyCropBoxStyles();
      };

      const onMouseUp = () => {
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
      };

      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
    });

    // Resize via handles
    document.querySelectorAll('.crop-handle').forEach(handle => {
      handle.addEventListener('mousedown', (e) => {
        e.preventDefault();
        e.stopPropagation();

        const type = handle.className.split(' ')[1]; // nw, n, ne, e, se, s, sw, w
        const startX = e.clientX;
        const startY = e.clientY;
        const startLeft = cropBox.left;
        const startTop = cropBox.top;
        const startWidth = cropBox.width;
        const startHeight = cropBox.height;

        const imgEl = document.getElementById('editor-image');
        if (!imgEl) return;
        const maxW = imgEl.clientWidth;
        const maxH = imgEl.clientHeight;

        const onMouseMove = (ev) => {
          const dx = ev.clientX - startX;
          const dy = ev.clientY - startY;

          let newLeft = startLeft;
          let newTop = startTop;
          let newWidth = startWidth;
          let newHeight = startHeight;

          // Vertical resizing
          if (type.includes('n')) {
            const potentialTop = startTop + dy;
            if (potentialTop >= 0 && potentialTop < startTop + startHeight - 20) {
              newTop = potentialTop;
              newHeight = startHeight - dy;
            }
          }
          if (type.includes('s')) {
            const potentialHeight = startHeight + dy;
            if (potentialHeight > 20 && startTop + potentialHeight <= maxH) {
              newHeight = potentialHeight;
            }
          }

          // Horizontal resizing
          if (type.includes('w')) {
            const potentialLeft = startLeft + dx;
            if (potentialLeft >= 0 && potentialLeft < startLeft + startWidth - 20) {
              newLeft = potentialLeft;
              newWidth = startWidth - dx;
            }
          }
          if (type.includes('e')) {
            const potentialWidth = startWidth + dx;
            if (potentialWidth > 20 && startLeft + potentialWidth <= maxW) {
              newWidth = potentialWidth;
            }
          }

          // Aspect ratio lock
          if (cropRatio !== 'free') {
            const ratio = parseFloat(cropRatio);
            if (type === 'e' || type === 'w' || type === 'ne' || type === 'se') {
              newHeight = newWidth / ratio;
              if (newTop + newHeight > maxH) {
                newHeight = maxH - newTop;
                newWidth = newHeight * ratio;
              }
            } else {
              newWidth = newHeight * ratio;
              if (newLeft + newWidth > maxW) {
                newWidth = maxW - newLeft;
                newHeight = newWidth / ratio;
              }
            }
          }

          cropBox = { left: newLeft, top: newTop, width: newWidth, height: newHeight };
          applyCropBoxStyles();
        };

        const onMouseUp = () => {
          document.removeEventListener('mousemove', onMouseMove);
          document.removeEventListener('mouseup', onMouseUp);
        };

        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
      });
    });
  }

  return { init, open, close, undo, redo, saveImage };
})();

window.Editor = Editor;
