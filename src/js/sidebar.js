// ═══ Sidebar Module ═══

const Sidebar = (() => {
  let computeTimer = null;

  function init() {
    // Toggle buttons
    document.getElementById('toggle-left')?.addEventListener('click', () => {
      document.getElementById('left-sidebar').classList.toggle('collapsed');
    });
    document.getElementById('toggle-right')?.addEventListener('click', () => {
      document.getElementById('right-sidebar').classList.toggle('collapsed');
    });

    if (typeof Tags !== 'undefined') {
      Tags.init();
    }
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
      Logger.error('Sidebar', `Failed to show preview for ${imageInfo.path}`, err);
      area.innerHTML = '<span class="preview-placeholder">Ошибка загрузки</span>';
    }

    // Load metadata and AI info
    loadMetadata(imageInfo.path);
    showAiInfo(imageInfo);

    if (typeof Tags !== 'undefined') {
      Tags.updateSelectedImage(imageInfo);
    }
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
    } catch (err) {
      Logger.warn('Sidebar', `Failed to load metadata for ${path}`, err);
      table.innerHTML = '<div class="meta-row"><span class="meta-key">Ошибка чтения EXIF</span></div>';
    }
  }

  function computeAndDrawHistogramAndPalette(img) {
    clearTimeout(computeTimer);
    computeTimer = setTimeout(() => {
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      
      // Scale down image for fast pixel extraction (100x100 is extremely fast and accurate)
      canvas.width = 100;
      canvas.height = 100;
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      
      let imgData;
      try {
        imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      } catch (err) {
        Logger.debug('Sidebar', `Failed to get image data for histogram/palette: ${err}`);
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
    }, 150);
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
    if (typeof Tags !== 'undefined') {
      Tags.clear();
    }
  }

  async function loadFolderTree(rootPath) {
    const container = document.getElementById('folder-tree');
    if (!container) return;

    try {
      const tree = await API.getFolderTree(rootPath);
      container.innerHTML = '';
      renderFolderNodes(container, tree);
    } catch (err) {
      Logger.error('Sidebar', `Failed to load folder tree for ${rootPath}`, err);
      container.innerHTML = '<div style="color:var(--text-muted);font-size:11px;padding:4px 8px">Не удалось загрузить дерево</div>';
    }
  }

  function renderFolderNodes(parent, nodes) {
    nodes.forEach(node => {
      const item = Utils.el('div', {
        className: 'folder-tree-item',
        'data-path': node.path,
        onClick: () => {
          document.querySelectorAll('.folder-tree-item').forEach(i => i.classList.remove('active'));
          item.classList.add('active');
          if (typeof Gallery !== 'undefined') {
            Gallery.filterByFolder(node.path);
          }
        },
      }, [
        Utils.el('span', { className: 'folder-icon', textContent: '📁' }),
        document.createTextNode(` ${node.name}`),
        Utils.el('span', { className: 'folder-count', textContent: node.file_count || '0' }),
      ]);

      // Drag and drop events for folder targets
      item.addEventListener('dragover', (e) => {
        e.preventDefault();
        item.classList.add('drag-over');
      });

      item.addEventListener('dragleave', () => {
        item.classList.remove('drag-over');
      });

      item.addEventListener('drop', async (e) => {
        e.preventDefault();
        item.classList.remove('drag-over');

        try {
          const rawData = e.dataTransfer.getData('application/json');
          if (!rawData) return;
          const sourcePaths = JSON.parse(rawData);
          if (!Array.isArray(sourcePaths) || sourcePaths.length === 0) return;

          // Check if dropping onto the same folder
          const isSameFolder = sourcePaths.every(p => {
            const sep = p.includes('/') ? '/' : '\\';
            const dir = p.substring(0, p.lastIndexOf(sep));
            return dir.toLowerCase() === node.path.toLowerCase();
          });

          if (isSameFolder) {
            Utils.toast('Файлы уже находятся в этой папке', 'warning');
            return;
          }

          const doMove = await API.askConfirm(
            `Переместить ${sourcePaths.length} файл(ов) в папку "${node.name}"? (Нажмите ОК для Перемещения, Отмена для Копирования)`,
            'Перемещение или копирование'
          );

          if (doMove) {
            Utils.toast('Перемещение файлов...', 'info');
            const count = await API.moveFiles(sourcePaths, node.path);
            if (count > 0) {
              if (typeof Gallery !== 'undefined') {
                Gallery.removeImages(sourcePaths);
              }
              // Reload tree
              if (typeof App !== 'undefined' && App.currentFolder) {
                loadFolderTree(App.currentFolder);
              }
              Utils.toast(`Успешно перемещено файлов: ${count}`, 'success');
            }
          } else {
            const doCopy = await API.askConfirm(
              `Скопировать ${sourcePaths.length} файл(ов) в папку "${node.name}"?`,
              'Копирование'
            );
            if (doCopy) {
              Utils.toast('Копирование файлов...', 'info');
              const count = await API.copyFiles(sourcePaths, node.path);
              if (count > 0) {
                if (typeof App !== 'undefined' && App.currentFolder) {
                  loadFolderTree(App.currentFolder);
                }
                Utils.toast(`Успешно скопировано файлов: ${count}`, 'success');
              }
            }
          }
        } catch (err) {
          Utils.toast(`Ошибка перетаскивания: ${err}`, 'error');
        }
      });

      parent.appendChild(item);

      if (node.children && node.children.length) {
        const children = Utils.el('div', { className: 'folder-tree-children' });
        renderFolderNodes(children, node.children);
        parent.appendChild(children);
      }
    });
  }

  function updateLibraryStats(images) {
    const statsContainer = document.getElementById('stats-content');
    if (!statsContainer) return;

    if (!images || images.length === 0) {
      statsContainer.innerHTML = '<div class="stats-placeholder">Нет данных</div>';
      return;
    }

    const totalCount = images.length;
    const totalBytes = images.reduce((sum, img) => sum + (img.file_size || 0), 0);
    const formattedSize = Utils.formatSize(totalBytes);

    const formats = {};
    const cameras = {};
    let minDate = null;
    let maxDate = null;
    const monthlyCounts = {};

    images.forEach(img => {
      const ext = Utils.getExtension(img.path).toUpperCase() || 'UNKNOWN';
      formats[ext] = (formats[ext] || 0) + 1;

      const camera = img.camera_model ? img.camera_model.trim() : null;
      if (camera) {
        cameras[camera] = (cameras[camera] || 0) + 1;
      }

      const date = Utils.parseExifDate(img.date_taken);
      if (date) {
        if (!minDate || date < minDate) minDate = date;
        if (!maxDate || date > maxDate) maxDate = date;

        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const monthKey = `${year}-${month}`;
        monthlyCounts[monthKey] = (monthlyCounts[monthKey] || 0) + 1;
      }
    });

    let dateRangeStr = 'Нет дат';
    if (minDate && maxDate) {
      const options = { year: 'numeric', month: 'short' };
      dateRangeStr = `${minDate.toLocaleDateString('ru-RU', options)} — ${maxDate.toLocaleDateString('ru-RU', options)}`;
    }

    const topFormats = Object.entries(formats)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([name, count]) => `${name}: ${count}`)
      .join(', ');

    const topCameras = Object.entries(cameras)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 2)
      .map(([name, count]) => `${name.substring(0, 18)} (${count})`)
      .join(', ') || 'Нет данных';

    const sparklineHtml = generateSparkline(monthlyCounts, minDate, maxDate);

    statsContainer.innerHTML = '';
    const statsList = Utils.el('div', { className: 'stats-list' }, [
      createStatRow('Всего файлов', `${totalCount} (${formattedSize})`),
      createStatRow('Форматы', topFormats || 'Нет данных'),
      createStatRow('Камеры', topCameras),
      createStatRow('Период', dateRangeStr),
      Utils.el('div', { className: 'stats-sparkline-title', textContent: 'АКТИВНОСТЬ ПО МЕСЯЦАМ' }),
      Utils.el('div', { className: 'stats-sparkline-wrapper', innerHTML: sparklineHtml })
    ]);

    statsContainer.appendChild(statsList);
  }

  function createStatRow(label, value) {
    return Utils.el('div', { className: 'stats-row' }, [
      Utils.el('span', { className: 'stats-key', textContent: label }),
      Utils.el('span', { className: 'stats-val', textContent: value })
    ]);
  }

  function generateSparkline(monthlyCounts, minDate, maxDate) {
    if (!minDate || !maxDate) return '<div class="sparkline-empty">Нет временных данных</div>';

    const months = [];
    let current = new Date(minDate.getFullYear(), minDate.getMonth(), 1);
    const end = new Date(maxDate.getFullYear(), maxDate.getMonth(), 1);

    while (current <= end) {
      const y = current.getFullYear();
      const m = String(current.getMonth() + 1).padStart(2, '0');
      months.push(`${y}-${m}`);
      current.setMonth(current.getMonth() + 1);
    }

    const displayMonths = months.slice(-18);
    const values = displayMonths.map(m => monthlyCounts[m] || 0);
    const maxVal = Math.max(...values, 1);

    const svgWidth = 180;
    const svgHeight = 28;
    const barWidth = Math.max(2, Math.floor(svgWidth / displayMonths.length) - 2);
    const actualWidth = displayMonths.length * (barWidth + 2);

    let bars = '';
    values.forEach((val, i) => {
      const height = (val / maxVal) * svgHeight;
      const x = i * (barWidth + 2);
      const y = svgHeight - height;
      const label = displayMonths[i];
      bars += `<rect x="${x}" y="${y}" width="${barWidth}" height="${height}" fill="var(--accent-primary)" opacity="0.85" rx="1">
        <title>${label}: ${val} фото</title>
      </rect>`;
    });

    return `<svg width="${actualWidth}" height="${svgHeight}" style="overflow: visible;">
      ${bars}
    </svg>`;
  }

  return { init, showPreview, clearPreview, loadFolderTree, updateLibraryStats };
})();

window.Sidebar = Sidebar;
