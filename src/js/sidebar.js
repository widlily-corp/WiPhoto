// ═══ Sidebar Module ═══

const Sidebar = (() => {
  function init() {
    // Toggle buttons
    document.getElementById('toggle-left')?.addEventListener('click', () => {
      document.getElementById('left-sidebar').classList.toggle('collapsed');
    });
    document.getElementById('toggle-right')?.addEventListener('click', () => {
      document.getElementById('right-sidebar').classList.toggle('collapsed');
    });
  }

  async function showPreview(imageInfo) {
    const area = document.getElementById('preview-area');
    if (!area) return;

    try {
      area.innerHTML = '';
      const b64 = await API.loadFullImage(imageInfo.path, 600);
      const img = Utils.el('img', { src: Utils.base64Src(b64), alt: imageInfo.filename });
      
      // Compute histogram and palette instantly on the frontend when the image loads
      img.onload = () => {
        computeAndDrawHistogramAndPalette(img);
      };
      
      area.appendChild(img);
    } catch (err) {
      area.innerHTML = '<span class="preview-placeholder">Ошибка загрузки</span>';
    }

    // Load metadata and AI info
    loadMetadata(imageInfo.path);
    showAiInfo(imageInfo);
  }

  async function loadMetadata(path) {
    const table = document.getElementById('metadata-table');
    if (!table) return;

    try {
      const entries = await API.readExif(path);
      table.innerHTML = '';
      entries.forEach(entry => {
        const row = Utils.el('div', { className: 'meta-row' }, [
          Utils.el('span', { className: 'meta-key', textContent: entry.key }),
          Utils.el('span', { className: 'meta-value', textContent: entry.value }),
        ]);
        table.appendChild(row);
      });
    } catch {
      table.innerHTML = '<div class="meta-row"><span class="meta-key">Ошибка чтения EXIF</span></div>';
    }
  }

  function computeAndDrawHistogramAndPalette(img) {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    
    // Scale down image for fast pixel extraction (100x100 is extremely fast and accurate)
    canvas.width = 100;
    canvas.height = 100;
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    
    let imgData;
    try {
      imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    } catch {
      return;
    }
    
    const data = imgData.data;
    const len = data.length;
    
    // ─── Calculate Histogram ───
    const rHist = new Uint32Array(256);
    const gHist = new Uint32Array(256);
    const bHist = new Uint32Array(256);
    const lHist = new Uint32Array(256);
    
    for (let i = 0; i < len; i += 4) {
      const r = data[i];
      const g = data[i + 1];
      const b = data[i + 2];
      const lum = Math.round(0.299 * r + 0.587 * g + 0.114 * b);
      
      rHist[r]++;
      gHist[g]++;
      bHist[b]++;
      lHist[lum]++;
    }
    
    const histData = {
      red: Array.from(rHist),
      green: Array.from(gHist),
      blue: Array.from(bHist),
      luminance: Array.from(lHist)
    };
    
    // Draw histogram
    const histCanvas = document.getElementById('histogram-canvas');
    if (histCanvas) {
      drawHistogram(histCanvas, histData);
    }
    
    // ─── Calculate Color Palette ───
    const colorCounts = {};
    for (let i = 0; i < len; i += 4) {
      const r = data[i];
      const g = data[i + 1];
      const b = data[i + 2];
      
      // Quantize to group similar colors (step of 32 reduces space to 8x8x8)
      const qr = Math.round(r / 32) * 32;
      const qg = Math.round(g / 32) * 32;
      const qb = Math.round(b / 32) * 32;
      const key = `${qr},${qg},${qb}`;
      colorCounts[key] = (colorCounts[key] || 0) + 1;
    }
    
    // Sort colors by popularity
    const sortedBins = Object.keys(colorCounts).sort((a, b) => colorCounts[b] - colorCounts[a]);
    
    const rgbToHex = (r, g, b) => {
      const clamp = (val) => Math.min(255, Math.max(0, val));
      const hex = (x) => clamp(x).toString(16).padStart(2, '0');
      return `#${hex(r)}${hex(g)}${hex(b)}`;
    };
    
    const palette = [];
    const colorDistance = (hex1, hex2) => {
      const parse = (h) => [
        parseInt(h.slice(1, 3), 16),
        parseInt(h.slice(3, 5), 16),
        parseInt(h.slice(5, 7), 16)
      ];
      const [r1, g1, b1] = parse(hex1);
      const [r2, g2, b2] = parse(hex2);
      return Math.sqrt((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2);
    };
    
    for (let i = 0; i < sortedBins.length && palette.length < 8; i++) {
      const [r, g, b] = sortedBins[i].split(',').map(Number);
      const hex = rgbToHex(r, g, b);
      
      // Filter out colors that are too close to existing palette colors
      if (!palette.some(existing => colorDistance(existing, hex) < 45)) {
        palette.push(hex);
      }
    }
    
    drawColorPalette(palette);
  }

  function drawHistogram(canvas, data) {
    // Sync internal canvas size with display size for sharp rendering
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width || 280;
    canvas.height = rect.height || 80;

    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    // Dark background
    ctx.fillStyle = 'rgba(18, 19, 24, 0.95)';
    ctx.fillRect(0, 0, w, h);

    const channels = [
      { data: data.red, color: 'rgba(239, 68, 68, 0.4)' },
      { data: data.green, color: 'rgba(16, 185, 129, 0.4)' },
      { data: data.blue, color: 'rgba(59, 130, 246, 0.4)' },
      { data: data.luminance, color: 'rgba(255, 255, 255, 0.25)' },
    ];

    const maxVal = Math.max(...channels.flatMap(c => c.data));
    if (maxVal === 0) return;

    channels.forEach(channel => {
      ctx.beginPath();
      ctx.moveTo(0, h);
      for (let i = 0; i < 256; i++) {
        const x = (i / 255) * w;
        const y = h - (channel.data[i] / maxVal) * h;
        ctx.lineTo(x, y);
      }
      ctx.lineTo(w, h);
      ctx.closePath();
      ctx.fillStyle = channel.color;
      ctx.fill();
    });
  }

  function drawColorPalette(colors) {
    const container = document.getElementById('color-palette');
    if (!container) return;
    container.innerHTML = '';
    colors.forEach(color => {
      const swatch = Utils.el('div', {
        className: 'color-swatch',
        title: color,
      });
      swatch.style.backgroundColor = color;
      container.appendChild(swatch);
    });
  }

  function showAiInfo(imageInfo) {
    const el = document.getElementById('ai-info');
    if (!el) return;

    const parts = [];
    if (imageInfo.faces_count > 0) parts.push(`👤 Лица: ${imageInfo.faces_count}`);
    if (imageInfo.animals_count > 0) {
      const species = imageInfo.animal_species && imageInfo.animal_species.length > 0 
        ? ` (${imageInfo.animal_species.join(', ')})` 
        : '';
      parts.push(`🐾 Животные: ${imageInfo.animals_count}${species}`);
    }
    if (imageInfo.sharpness > 0) parts.push(`📐 Резкость: ${imageInfo.sharpness.toFixed(1)}`);
    if (imageInfo.group_id) {
      parts.push(imageInfo.is_best_in_group ? '⭐ Лучшее в группе дубликатов' : `🔄 Дубликат (${imageInfo.group_id.slice(0, 8)})`);
    }

    el.textContent = parts.length ? parts.join('\n') : 'Нет данных анализа';
    el.style.whiteSpace = 'pre-line';
  }

  function clearPreview() {
    const area = document.getElementById('preview-area');
    if (area) area.innerHTML = '<span class="preview-placeholder">Выберите файл</span>';
    const meta = document.getElementById('metadata-table');
    if (meta) meta.innerHTML = '';
    const ai = document.getElementById('ai-info');
    if (ai) ai.textContent = 'Нет данных анализа';
    const palette = document.getElementById('color-palette');
    if (palette) palette.innerHTML = '';
    const canvas = document.getElementById('histogram-canvas');
    if (canvas) {
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
  }

  async function loadFolderTree(rootPath) {
    const container = document.getElementById('folder-tree');
    if (!container) return;

    try {
      const tree = await API.getFolderTree(rootPath);
      container.innerHTML = '';
      renderFolderNodes(container, tree);
    } catch {
      container.innerHTML = '<div style="color:var(--text-muted);font-size:11px;padding:4px 8px">Не удалось загрузить дерево</div>';
    }
  }

  function renderFolderNodes(parent, nodes) {
    nodes.forEach(node => {
      const item = Utils.el('div', {
        className: 'folder-tree-item',
        onClick: () => {
          // Scan this subfolder
          document.querySelectorAll('.folder-tree-item').forEach(i => i.classList.remove('active'));
          item.classList.add('active');
        },
      }, [
        Utils.el('span', { className: 'folder-icon', textContent: '📁' }),
        document.createTextNode(` ${node.name}`),
        Utils.el('span', { className: 'folder-count', textContent: node.file_count || '' }),
      ]);
      parent.appendChild(item);

      if (node.children && node.children.length) {
        const children = Utils.el('div', { className: 'folder-tree-children' });
        renderFolderNodes(children, node.children);
        parent.appendChild(children);
      }
    });
  }

  return { init, showPreview, clearPreview, loadFolderTree };
})();

window.Sidebar = Sidebar;
