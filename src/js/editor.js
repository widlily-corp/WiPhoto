// ═══ Editor Module ═══

const Editor = (() => {
  let currentImage = null;
  let operations = [];
  let historyStack = [];
  let historyIndex = -1;
  let isBeforeAfter = false;
  let updateTimer = null;

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
  }

  function open(imageInfo) {
    currentImage = imageInfo;
    operations = [];
    historyStack = [[]];
    historyIndex = 0;
    isBeforeAfter = false;

    // Reset all sliders
    document.querySelectorAll('.slider-control').forEach(ctrl => {
      const input = ctrl.querySelector('input[type="range"]');
      const valueSpan = ctrl.querySelector('.slider-value');
      input.value = 0;
      valueSpan.textContent = '0';
    });

    // Load the image
    loadPreview();
    renderHistory();

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

    // Save to history
    pushHistory();
    scheduleUpdate();
  }

  function addOperation(tool, value) {
    operations.push({ tool, value });
    pushHistory();
    scheduleUpdate();
  }

  function pushHistory() {
    // Trim any "future" entries
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
      if (operations.length === 0) {
        // Load original
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
      // Show original
      API.loadFullImage(currentImage.path, 2000).then(b64 => {
        document.getElementById('editor-image').src = Utils.base64Src(b64);
      });
    } else {
      loadPreview();
    }
  }

  function zoomFit() {
    const imgEl = document.getElementById('editor-image');
    imgEl.style.maxWidth = '100%';
    imgEl.style.maxHeight = '100%';
  }

  function zoom100() {
    const imgEl = document.getElementById('editor-image');
    imgEl.style.maxWidth = 'none';
    imgEl.style.maxHeight = 'none';
  }

  async function saveImage() {
    if (!currentImage || operations.length === 0) {
      Utils.toast('Нечего сохранять', 'warning');
      return;
    }

    try {
      const outputPath = await API.openSaveDialog(currentImage.path);
      if (outputPath) {
        await API.saveEdited(currentImage.path, operations, outputPath, 95);
        Utils.toast('Сохранено', 'success');
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

    // Original state
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

  return { init, open, close, undo, redo, saveImage };
})();

window.Editor = Editor;
