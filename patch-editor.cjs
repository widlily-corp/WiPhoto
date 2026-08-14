const fs = require('fs');
let code = fs.readFileSync('src/js/editor.js', 'utf8');

// 1. Initialize GPURenderer
const initOrig = `  function init() {
    // Slider controls`;

const initNew = `  let gpuCanvas = null;
  let gpuInitialized = false;

  async function init() {
    // Setup GPU canvas
    gpuCanvas = document.createElement('canvas');
    gpuCanvas.id = 'editor-gpu-canvas';
    gpuCanvas.style.position = 'absolute';
    gpuCanvas.style.top = '0';
    gpuCanvas.style.left = '0';
    gpuCanvas.style.width = '100%';
    gpuCanvas.style.height = '100%';
    gpuCanvas.style.objectFit = 'contain';
    gpuCanvas.style.pointerEvents = 'none'; // let clicks pass through to crop overlay etc
    
    // Add canvas to wrapper
    const wrapper = document.getElementById('editor-canvas-wrapper');
    if (wrapper) {
      wrapper.appendChild(gpuCanvas);
    }
    
    if (typeof GPURenderer !== 'undefined' && GPURenderer.isAvailable()) {
      gpuInitialized = await GPURenderer.init(gpuCanvas);
    }

    // Slider controls`;

code = code.replace(initOrig, initNew);

// 2. Modify loadPreview
const loadOrig = `  async function loadPreview() {
    if (!currentImage) return;

    const imgEl = document.getElementById('editor-image');
    try {
      imgEl.onload = () => {
        applyVisualCropPreview();
      };

      if (operations.length === 0) {
        const fullPath = await API.loadFullImage(currentImage.path, 2000);
        imgEl.src = Utils.assetUrl(fullPath);
      } else {
        const editedPath = await API.applyEdit(currentImage.path, operations, 2000);
        imgEl.src = Utils.assetUrl(editedPath);
      }
    } catch (e) {
      Utils.toast(\`Ошибка: \${e}\`, 'error');
    }
  }`;

const loadNew = `  async function loadPreview() {
    if (!currentImage) return;

    const imgEl = document.getElementById('editor-image');
    try {
      imgEl.onload = () => {
        applyVisualCropPreview();
      };

      if (operations.length === 0) {
        if (gpuCanvas) gpuCanvas.style.display = 'none';
        imgEl.style.opacity = '1';
        const fullPath = await API.loadFullImage(currentImage.path, 2000);
        imgEl.src = Utils.assetUrl(fullPath);
      } else {
        if (gpuInitialized) {
          // Prepare image bitmap
          const fullPath = await API.loadFullImage(currentImage.path, 2000);
          const imgUrl = Utils.assetUrl(fullPath);
          const img = new Image();
          img.crossOrigin = 'anonymous';
          img.src = imgUrl;
          await new Promise((resolve, reject) => {
            img.onload = resolve;
            img.onerror = reject;
          });
          const bitmap = await createImageBitmap(img);
          
          // Map operations to adjustments object
          const adjustments = {};
          operations.forEach(op => {
            if (['exposure', 'contrast', 'temperature', 'saturation', 'highlights', 'shadows'].includes(op.tool)) {
              adjustments[op.tool] = op.value / 100; // rough scale
            }
          });
          
          await GPURenderer.render(bitmap, adjustments);
          imgEl.style.opacity = '0'; // Hide original, show GPU canvas
          gpuCanvas.style.display = 'block';
          
          // Still need to call applyVisualCropPreview manually since onload won't fire for canvas
          applyVisualCropPreview();
        } else {
          if (gpuCanvas) gpuCanvas.style.display = 'none';
          imgEl.style.opacity = '1';
          const editedPath = await API.applyEdit(currentImage.path, operations, 2000);
          imgEl.src = Utils.assetUrl(editedPath);
        }
      }
    } catch (e) {
      Utils.toast(\`Ошибка: \${e}\`, 'error');
    }
  }`;

code = code.replace(loadOrig, loadNew);

fs.writeFileSync('src/js/editor.js', code);
