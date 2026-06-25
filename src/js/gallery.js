// ═══ Gallery Module ═══

const Gallery = (() => {
  let allImages = [];
  let filteredImages = [];
  let selectedIndices = new Set();
  let lastSelectedIndex = -1;
  let currentFilter = 'all';
  let currentSort = 'name';
  let searchQuery = '';
  let thumbSize = 180;
  let duplicateGroups = [];

  const grid = () => document.getElementById('gallery-grid');
  const emptyState = () => document.getElementById('gallery-empty');

  function init() {
    // Zoom slider
    const zoomSlider = document.getElementById('zoom-slider');
    if (zoomSlider) {
      zoomSlider.addEventListener('input', (e) => {
        thumbSize = parseInt(e.target.value);
        grid().style.setProperty('--thumb-size', `${thumbSize}px`);
      });
    }

    // Search
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
      searchInput.addEventListener('input', Utils.debounce((e) => {
        searchQuery = e.target.value.toLowerCase();
        applyFilters();
      }, 200));
    }

    // Sort
    const sortSelect = document.getElementById('sort-select');
    if (sortSelect) {
      sortSelect.addEventListener('change', (e) => {
        currentSort = e.target.value;
        applyFilters();
      });
    }

    // Filter buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentFilter = btn.dataset.filter;
        applyFilters();
      });
    });

    // Collection buttons
    document.querySelectorAll('.collection-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        currentFilter = btn.dataset.collection;
        applyFilters();
      });
    });

    // Click outside to deselect
    grid().addEventListener('click', (e) => {
      if (e.target === grid()) {
        clearSelection();
      }
    });
  }

  function setImages(images) {
    allImages = images;
    updateBadges();
    applyFilters();
  }

  function addImage(info) {
    allImages.push(info);
    applyFilters();
  }

  function updateBadges() {
    const set = (id, count) => {
      const el = document.getElementById(id);
      if (el) el.textContent = count;
    };
    set('badge-all', allImages.length);
    set('badge-faces', allImages.filter(i => i.faces_count > 0).length);
    set('badge-videos', allImages.filter(i => i.is_video).length);
    set('badge-raw', allImages.filter(i => i.is_raw).length);
    set('badge-gps', allImages.filter(i => i.gps_location).length);
    set('badge-rated', allImages.filter(i => i.rating > 0).length);
  }

  function applyFilters() {
    let images = [...allImages];

    // Filter
    switch (currentFilter) {
      case 'best':
        images = images.filter(i => i.is_best_in_group);
        break;
      case 'duplicates':
        images = images.filter(i => i.group_id);
        break;
      case 'picked':
        images = images.filter(i => i.flag_status === 'picked');
        break;
      case 'rejected':
        images = images.filter(i => i.flag_status === 'rejected');
        break;
      case 'faces':
        images = images.filter(i => i.faces_count > 0);
        break;
      case 'videos':
        images = images.filter(i => i.is_video);
        break;
      case 'raw':
        images = images.filter(i => i.is_raw);
        break;
      case 'gps':
        images = images.filter(i => i.gps_location);
        break;
      case 'rated':
        images = images.filter(i => i.rating > 0);
        break;
    }

    // Search
    if (searchQuery) {
      images = images.filter(i => i.filename.toLowerCase().includes(searchQuery));
    }

    // Sort
    images.sort((a, b) => {
      switch (currentSort) {
        case 'date': return (b.date_taken || '').localeCompare(a.date_taken || '');
        case 'size': return b.file_size - a.file_size;
        case 'camera': return (a.camera_model || '').localeCompare(b.camera_model || '');
        case 'rating': return b.rating - a.rating;
        default: return a.filename.localeCompare(b.filename);
      }
    });

    filteredImages = images;
    renderGrid();
  }

  function renderGrid() {
    const container = grid();
    container.innerHTML = '';
    selectedIndices.clear();

    if (filteredImages.length === 0) {
      emptyState().classList.remove('hidden');
      container.classList.add('hidden');
      return;
    }

    emptyState().classList.add('hidden');
    container.classList.remove('hidden');
    container.style.setProperty('--thumb-size', `${thumbSize}px`);

    // Use document fragment for performance
    const fragment = document.createDocumentFragment();

    filteredImages.forEach((img, index) => {
      const card = createThumbCard(img, index);
      fragment.appendChild(card);
    });

    container.appendChild(fragment);
    updateStatusBar();
  }

  function createThumbCard(img, index) {
    const card = Utils.el('div', {
      className: `thumb-card${img.flag_status === 'picked' ? ' picked' : ''}${img.flag_status === 'rejected' ? ' rejected' : ''}`,
      'data-path': img.path,
      'data-index': index,
    });

    // Thumbnail image (matches .thumb-img in gallery.css)
    const imgEl = Utils.el('img', {
      className: 'thumb-img',
      src: img.thumbnail ? Utils.base64Src(img.thumbnail) : '',
      alt: img.filename,
      loading: 'lazy',
    });
    card.appendChild(imgEl);

    // Video play indicator overlay
    if (img.is_video) {
      card.appendChild(Utils.el('div', {
        className: 'thumb-badge-video',
        style: 'position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 36px; height: 36px; background: rgba(0,0,0,0.65); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 16px; pointer-events: none; z-index: 2; border: 1.5px solid rgba(255,255,255,0.8); box-shadow: 0 4px 12px rgba(0,0,0,0.5);',
        textContent: '▶'
      }));
    }

    // Overlay (contains filename, visible on hover/selection)
    const overlay = Utils.el('div', { className: 'thumb-overlay' });
    overlay.appendChild(Utils.el('div', { className: 'thumb-filename', textContent: img.filename }));
    card.appendChild(overlay);

    // Rating (bottom-left, absolute positioned, always visible)
    if (img.rating > 0) {
      const ratingEl = Utils.el('div', { className: 'thumb-rating' });
      for (let r = 0; r < img.rating; r++) {
        ratingEl.appendChild(Utils.el('span', { className: 'thumb-star', textContent: '★' }));
      }
      card.appendChild(ratingEl);
    }

    // Color label (top-left, absolute positioned, always visible)
    if (img.color_label) {
      card.appendChild(Utils.el('div', { className: `thumb-color-label ${img.color_label}` }));
    }

    // Flag (top-left offset, absolute positioned, always visible)
    if (img.flag_status) {
      const flagChar = img.flag_status === 'picked' ? '✓' : '✗';
      const flagColorClass = img.flag_status === 'picked' ? 'text-success' : 'text-danger';
      const flagStyle = img.flag_status === 'picked' ? 'color: var(--flag-picked, #10b981)' : 'color: var(--flag-rejected, #ef4444)';
      card.appendChild(Utils.el('span', { 
        className: `thumb-flag ${flagColorClass}`, 
        style: flagStyle,
        textContent: flagChar 
      }));
    }

    // Badges (top-right, absolute positioned, always visible)
    const badges = Utils.el('div', { className: 'thumb-badges' });
    if (img.is_best_in_group) {
      badges.appendChild(Utils.el('span', { className: 'thumb-badge-video', style: 'background: var(--accent-primary, #6366f1); border-radius: 3px; font-size: 9px; padding: 1px 4px; color: #fff; text-transform: uppercase;', textContent: 'Лучшее' }));
    } else if (img.group_id) {
      badges.appendChild(Utils.el('span', { className: 'thumb-badge-raw', style: 'background: var(--bg-active, #4b5563); border-radius: 3px; font-size: 9px; padding: 1px 4px; color: #fff; text-transform: uppercase;', textContent: 'Дубл.' }));
    }
    if (img.is_raw) {
      badges.appendChild(Utils.el('span', { className: 'thumb-badge-raw', textContent: 'RAW' }));
    }
    if (img.is_video) {
      badges.appendChild(Utils.el('span', { className: 'thumb-badge-video', textContent: 'Видео' }));
    }
    if (badges.children.length) card.appendChild(badges);

    // Events
    card.addEventListener('click', (e) => handleClick(index, e));
    card.addEventListener('dblclick', () => handleDoubleClick(img));
    card.addEventListener('contextmenu', (e) => handleContextMenu(e, img, index));

    return card;
  }

  function handleClick(index, e) {
    if (e.ctrlKey || e.metaKey) {
      toggleSelection(index);
    } else if (e.shiftKey && lastSelectedIndex >= 0) {
      rangeSelect(lastSelectedIndex, index);
    } else {
      clearSelection();
      selectIndex(index);
    }
    lastSelectedIndex = index;
    updateStatusBar();
    showPreview();
  }

  function handleDoubleClick(img) {
    if (img.is_video) {
      // Open video in system player
      return;
    }
    App.openEditor(img);
  }

  function handleContextMenu(e, img, index) {
    e.preventDefault();
    if (!selectedIndices.has(index)) {
      clearSelection();
      selectIndex(index);
    }
    ContextMenu.show(e.clientX, e.clientY, img);
  }

  function selectIndex(index) {
    selectedIndices.add(index);
    const card = grid().querySelector(`[data-index="${index}"]`);
    if (card) card.classList.add('selected');
  }

  function toggleSelection(index) {
    if (selectedIndices.has(index)) {
      selectedIndices.delete(index);
      const card = grid().querySelector(`[data-index="${index}"]`);
      if (card) card.classList.remove('selected');
    } else {
      selectIndex(index);
    }
  }

  function rangeSelect(from, to) {
    const start = Math.min(from, to);
    const end = Math.max(from, to);
    for (let i = start; i <= end; i++) {
      selectIndex(i);
    }
  }

  function clearSelection() {
    selectedIndices.clear();
    grid().querySelectorAll('.thumb-card.selected').forEach(c => c.classList.remove('selected'));
  }

  function getSelectedImages() {
    return Array.from(selectedIndices).map(i => filteredImages[i]).filter(Boolean);
  }

  function showPreview() {
    const selected = getSelectedImages();
    if (selected.length === 1) {
      Sidebar.showPreview(selected[0]);
    }
  }

  function selectAll() {
    filteredImages.forEach((_, i) => selectIndex(i));
    updateStatusBar();
  }

  function updateStatusBar() {
    const total = filteredImages.length;
    const sel = selectedIndices.size;
    const parts = [`Всего: ${total}`, `Выбрано: ${sel}`];
    if (sel === 1) {
      const img = getSelectedImages()[0];
      if (img) {
        parts.push(img.filename);
        if (img.width && img.height) parts.push(`${img.width}×${img.height}`);
        if (img.camera_model) parts.push(img.camera_model);
        if (img.rating > 0) parts.push('★'.repeat(img.rating));
      }
    }
    document.getElementById('status-text').textContent = parts.join(' │ ');
  }

  function setRating(rating) {
    getSelectedImages().forEach(img => {
      img.rating = rating;
      API.writeXmpSidecar(img.path, img.rating, img.color_label, img.flag_status, img.tags || []);
    });
    applyFilters();
  }

  function setColorLabel(color) {
    getSelectedImages().forEach(img => {
      img.color_label = img.color_label === color ? '' : color;
      API.writeXmpSidecar(img.path, img.rating, img.color_label, img.flag_status, img.tags || []);
    });
    applyFilters();
  }

  function setFlagStatus(status) {
    getSelectedImages().forEach(img => {
      img.flag_status = status;
      API.writeXmpSidecar(img.path, img.rating, img.color_label, img.flag_status, img.tags || []);
    });
    applyFilters();
  }

  function removeImages(paths) {
    const pathSet = new Set(paths);
    allImages = allImages.filter(i => !pathSet.has(i.path));
    applyFilters();
    updateBadges();
  }

  function setDuplicateGroups(groups) {
    duplicateGroups = groups;
    groups.forEach(group => {
      group.images.forEach(path => {
        const img = allImages.find(i => i.path === path);
        if (img) {
          img.group_id = group.group_id;
          img.is_best_in_group = path === group.best_path;
        }
      });
    });
    applyFilters();
    updateBadges();
  }

  return {
    init, setImages, addImage, applyFilters, getSelectedImages,
    clearSelection, selectAll, setRating, setColorLabel, setFlagStatus,
    removeImages, setDuplicateGroups, getFilteredImages: () => filteredImages,
    getAllImages: () => allImages,
    updateStatusBar,
  };
})();

// ─── Context Menu ───
const ContextMenu = (() => {
  const menu = () => document.getElementById('context-menu');
  let currentImage = null;

  function init() {
    document.addEventListener('click', () => hide());
    document.addEventListener('contextmenu', (e) => {
      if (!e.target.closest('.thumb-card')) hide();
    });

    menu().querySelectorAll('button[data-action]').forEach(btn => {
      btn.addEventListener('click', () => {
        handleAction(btn.dataset.action);
        hide();
      });
    });
  }

  function show(x, y, image) {
    currentImage = image;
    const m = menu();
    m.style.left = `${Math.min(x, window.innerWidth - 220)}px`;
    m.style.top = `${Math.min(y, window.innerHeight - 400)}px`;
    m.classList.remove('hidden');
  }

  function hide() {
    menu().classList.add('hidden');
  }

  async function handleAction(action) {
    const selected = Gallery.getSelectedImages();
    if (!selected.length) return;

    switch (action) {
      case 'edit':
        App.openEditor(selected[0]);
        break;
      case 'view-fullscreen':
        Viewer.open(selected[0]);
        break;
      case 'copy': {
        const dest = await API.openFolderDialog();
        if (dest) {
          const count = await API.copyFiles(selected.map(i => i.path), dest);
          Utils.toast(`Скопировано файлов: ${count}`, 'success');
        }
        break;
      }
      case 'move': {
        const dest = await API.openFolderDialog();
        if (dest) {
          const moved = await API.moveFiles(selected.map(i => i.path), dest);
          Gallery.removeImages(moved);
          Utils.toast(`Перемещено файлов: ${moved.length}`, 'success');
        }
        break;
      }
      case 'delete': {
        const ok = await API.askConfirm(`Удалить ${selected.length} файл(ов) в корзину WiPhoto?`);
        if (ok) {
          const deleted = await API.deleteFiles(selected.map(i => i.path));
          Gallery.removeImages(deleted);
          Utils.toast(`Удалено: ${deleted.length}`, 'success');
        }
        break;
      }
      case 'rate-5': Gallery.setRating(5); break;
      case 'rate-3': Gallery.setRating(3); break;
      case 'rate-0': Gallery.setRating(0); break;
      case 'flag-pick': Gallery.setFlagStatus('picked'); break;
      case 'flag-reject': Gallery.setFlagStatus('rejected'); break;
      case 'flag-none': Gallery.setFlagStatus(''); break;
      case 'find-similar':
        App.showDuplicateFinder();
        break;
    }
  }

  return { init, show, hide };
})();

window.Gallery = Gallery;
window.ContextMenu = ContextMenu;
