// ═══ Gallery Module ═══
// v3.0 — VirtualGrid integration, folder filtering, drag support

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
  let currentFolderFilter = '';  // v3: folder-level filtering
  let currentTagFilter = '';     // v3: tag filtering

  const grid = () => document.getElementById('gallery-grid');
  const emptyState = () => document.getElementById('gallery-empty');

  function init() {
    // Initialize VirtualGrid
    const scrollContainer = document.getElementById('view-gallery');
    if (scrollContainer && grid()) {
      VirtualGrid.init({
        container: grid(),
        scrollContainer: scrollContainer,
        cardRenderer: createThumbCard,
      });

      // Bind dragstart using event delegation
      grid().addEventListener('dragstart', (e) => {
        const card = e.target.closest('.thumb-card');
        if (!card) return;

        const path = card.dataset.path;
        const idx = parseInt(card.dataset.index);
        
        let dragPaths = [];
        if (selectedIndices.has(idx)) {
          dragPaths = getSelectedImages().map(img => img.path);
        } else {
          dragPaths = [path];
        }

        e.dataTransfer.setData('application/json', JSON.stringify(dragPaths));
        e.dataTransfer.effectAllowed = 'copyMove';
      });
    }

    // Zoom slider
    const zoomSlider = document.getElementById('zoom-slider');
    if (zoomSlider) {
      zoomSlider.addEventListener('input', (e) => {
        thumbSize = parseInt(e.target.value);
        grid().style.setProperty('--thumb-size', `${thumbSize}px`);
        VirtualGrid.updateThumbSize(thumbSize);
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
        currentFolderFilter = '';
        applyFilters();
      });
    });

    // Collection buttons
    document.querySelectorAll('.collection-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        if (btn.dataset.collection === 'trash') {
          if (typeof Trash !== 'undefined') {
            Trash.open();
          }
          return;
        }
        currentFilter = btn.dataset.collection;
        currentFolderFilter = '';
        applyFilters();
      });
    });

    // Click outside to deselect
    grid().addEventListener('click', (e) => {
      if (e.target === grid() || e.target.classList.contains('vgrid-spacer-top') || e.target.classList.contains('vgrid-spacer-bottom')) {
        clearSelection();
      }
    });
  }

  function setImages(images) {
    Logger.debug('Gallery', "setImages called with: " + images.length + " images");
    allImages = images;
    updateBadges();
    applyFilters();
    Logger.debug('Gallery', "setImages finished applying filters");
    if (typeof Sidebar !== 'undefined') {
      Sidebar.updateLibraryStats(allImages);
    }
    Logger.debug('Gallery', "setImages complete");
  }

  function addImage(info) {
    allImages.push(info);
    applyFilters();
    if (typeof Sidebar !== 'undefined') {
      Sidebar.updateLibraryStats(allImages);
    }
  }

  function addImageBatch(batch) {
    allImages.push(...batch);
    applyFilters();
    if (typeof Sidebar !== 'undefined') {
      Sidebar.updateLibraryStats(allImages);
    }
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

    // Folder filter (v3)
    if (currentFolderFilter) {
      images = images.filter(i => {
        const sep = i.path.includes('/') ? '/' : '\\';
        const dir = i.path.substring(0, i.path.lastIndexOf(sep));
        return dir === currentFolderFilter || dir.startsWith(currentFolderFilter + sep);
      });
    }

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
      case 'trash':
        // Handled separately via trash modal
        break;
    }

    // Tag filter (v3)
    if (currentTagFilter) {
      images = images.filter(i => i.tags && i.tags.includes(currentTagFilter));
    }

    // Search
    if (searchQuery) {
      images = images.filter(i => {
        const nameMatch = i.filename.toLowerCase().includes(searchQuery);
        const tagMatch = i.tags && i.tags.some(t => t.toLowerCase().includes(searchQuery));
        const cameraMatch = i.camera_model && i.camera_model.toLowerCase().includes(searchQuery);
        return nameMatch || tagMatch || cameraMatch;
      });
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
    Logger.debug('Gallery', "applyFilters: filteredImages count: " + filteredImages.length);
    renderGrid();
    if (typeof Tags !== 'undefined') {
      Tags.renderGlobalTags();
    }
  }

  function renderGrid() {
    selectedIndices.clear();
    Logger.debug('Gallery', "renderGrid: filteredImages count: " + filteredImages.length);

    if (filteredImages.length === 0) {
      Logger.debug('Gallery', "renderGrid: emptyState shown");
      emptyState().classList.remove('hidden');
      grid().classList.add('hidden');
      updateStatusBar();
      return;
    }

    Logger.debug('Gallery', "renderGrid: displaying grid and calling VirtualGrid.setItems");
    emptyState().classList.add('hidden');
    grid().classList.remove('hidden');
    grid().style.setProperty('--thumb-size', `${thumbSize}px`);

    // Use VirtualGrid for rendering
    VirtualGrid.setItems(filteredImages, thumbSize);
    updateStatusBar();
  }

  function createThumbCard(img, index) {
    const card = Utils.el('div', {
      className: `thumb-card${img.flag_status === 'picked' ? ' picked' : ''}${img.flag_status === 'rejected' ? ' rejected' : ''}${selectedIndices.has(index) ? ' selected' : ''}`,
      'data-path': img.path,
      'data-index': index,
      draggable: 'true',
    });

    // Thumbnail image (rendered directly since grid is virtualized)
    const imgEl = Utils.el('img', {
      className: 'thumb-img',
      alt: img.filename,
    });
    if (img.thumbnail) {
      imgEl.src = Utils.base64Src(img.thumbnail);
    }
    card.appendChild(imgEl);

    // Video play indicator overlay
    if (img.is_video) {
      card.appendChild(Utils.el('div', {
        className: 'thumb-badge-video-play',
        textContent: '▶'
      }));
    }

    // Overlay (contains filename, visible on hover/selection)
    const overlay = Utils.el('div', { className: 'thumb-overlay' });
    overlay.appendChild(Utils.el('div', { className: 'thumb-filename', textContent: img.filename }));
    card.appendChild(overlay);

    // Rating (bottom-left)
    if (img.rating > 0) {
      const ratingEl = Utils.el('div', { className: 'thumb-rating' });
      for (let r = 0; r < img.rating; r++) {
        ratingEl.appendChild(Utils.el('span', { className: 'thumb-star', textContent: '★' }));
      }
      card.appendChild(ratingEl);
    }

    // Color label (top-left)
    if (img.color_label) {
      card.appendChild(Utils.el('div', { className: `thumb-color-label ${img.color_label}` }));
    }

    // Flag indicator (top-left offset)
    if (img.flag_status) {
      const flagChar = img.flag_status === 'picked' ? '✓' : '✗';
      const flagStyle = img.flag_status === 'picked' ? 'color: var(--flag-picked, #10b981)' : 'color: var(--flag-rejected, #ef4444)';
      card.appendChild(Utils.el('span', {
        className: 'thumb-flag',
        style: flagStyle,
        textContent: flagChar
      }));
    }

    // Badges (top-right)
    const badges = Utils.el('div', { className: 'thumb-badges' });
    if (img.is_best_in_group) {
      badges.appendChild(Utils.el('span', { className: 'thumb-badge-best', textContent: '★' }));
    } else if (img.group_id) {
      badges.appendChild(Utils.el('span', { className: 'thumb-badge-dup', textContent: '⊞' }));
    }
    if (img.is_raw) {
      badges.appendChild(Utils.el('span', { className: 'thumb-badge-raw', textContent: 'RAW' }));
    }
    if (img.is_video) {
      badges.appendChild(Utils.el('span', { className: 'thumb-badge-video', textContent: 'VID' }));
    }
    if (badges.children.length) card.appendChild(badges);

    // Events
    card.addEventListener('click', (e) => handleClick(index, e));
    card.addEventListener('dblclick', () => handleDoubleClick(img));
    card.addEventListener('contextmenu', (e) => handleContextMenu(e, img, index));

    // Drag & Drop (v3)
    card.addEventListener('dragstart', (e) => {
      const selected = getSelectedImages();
      const dragPaths = selected.length > 0 ? selected.map(i => i.path) : [img.path];
      e.dataTransfer.setData('application/json', JSON.stringify(dragPaths));
      e.dataTransfer.setData('application/wiphoto-paths', JSON.stringify(dragPaths));
      e.dataTransfer.effectAllowed = 'copyMove';
      card.classList.add('dragging');
    });
    card.addEventListener('dragend', () => {
      card.classList.remove('dragging');
    });

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
    // Update DOM: find card by data-index in the virtual grid's content area
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
    const parts = [`${total} файлов`, `${sel} выбрано`];
    if (sel === 1) {
      const img = getSelectedImages()[0];
      if (img) {
        parts.push(img.filename);
        if (img.width && img.height) parts.push(`${img.width}×${img.height}`);
        if (img.camera_model) parts.push(img.camera_model);
        if (img.rating > 0) parts.push('★'.repeat(img.rating));
      }
    }
    // Total size
    if (total > 0) {
      const totalBytes = filteredImages.reduce((acc, i) => acc + (i.file_size || 0), 0);
      parts.push(Utils.formatSize(totalBytes));
    }
    document.getElementById('status-text').textContent = parts.join(' │ ');

    // Update Contextual Action Bar
    const contextualBar = document.getElementById('contextual-bar');
    const contextualCount = document.getElementById('contextual-count');
    if (contextualBar && contextualCount) {
      if (sel > 0) {
        contextualCount.textContent = `Выбрано: ${sel} файл(ов)`;
        contextualBar.classList.remove('hidden');
      } else {
        contextualBar.classList.add('hidden');
      }
    }
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

  // v3: folder filtering
  function filterByFolder(folderPath) {
    currentFolderFilter = folderPath;
    currentFilter = 'all';
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    const allBtn = document.querySelector('.filter-btn[data-filter="all"]');
    if (allBtn) allBtn.classList.add('active');
    applyFilters();
  }

  // v3: tag filtering
  function filterByTag(tag) {
    currentTagFilter = tag;
    applyFilters();
  }

  function clearTagFilter() {
    currentTagFilter = '';
    applyFilters();
  }

  // v3: get all unique tags
  function getAllTags() {
    const tagSet = new Set();
    allImages.forEach(img => {
      if (img.tags) img.tags.forEach(t => tagSet.add(t));
    });
    return Array.from(tagSet).sort();
  }

  // v3: add tags to selected images
  function addTagToSelected(tag) {
    getSelectedImages().forEach(img => {
      if (!img.tags) img.tags = [];
      if (!img.tags.includes(tag)) {
        img.tags.push(tag);
        API.writeXmpSidecar(img.path, img.rating, img.color_label, img.flag_status, img.tags);
      }
    });
  }

  // v3: remove tag from selected images
  function removeTagFromSelected(tag) {
    getSelectedImages().forEach(img => {
      if (img.tags) {
        img.tags = img.tags.filter(t => t !== tag);
        API.writeXmpSidecar(img.path, img.rating, img.color_label, img.flag_status, img.tags);
      }
    });
  }

  return {
    init, setImages, addImage, applyFilters, getSelectedImages,
    clearSelection, selectAll, setRating, setColorLabel, setFlagStatus,
    removeImages, setDuplicateGroups, getFilteredImages: () => filteredImages,
    getAllImages: () => allImages, updateStatusBar,
    // v3 additions
    filterByFolder, filterByTag, clearTagFilter, getAllTags,
    addTagToSelected, removeTagFromSelected, addImageBatch,
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
      case 'rename': {
        if (selected.length === 1) {
          const img = selected[0];
          const oldName = img.filename;
          // Use prompt-style rename (modal would be better, but keeping it simple)
          const ext = oldName.split('.').pop();
          const stem = oldName.substring(0, oldName.lastIndexOf('.'));
          // Trigger inline rename via a prompt toast
          const newName = prompt('Новое имя файла:', stem);
          if (newName && newName !== stem) {
            const sep = img.path.includes('/') ? '/' : '\\';
            const dir = img.path.substring(0, img.path.lastIndexOf(sep));
            const newPath = `${dir}${sep}${newName}.${ext}`;
            try {
              await API.batchRename([[img.path, newPath]]);
              img.path = newPath;
              img.filename = `${newName}.${ext}`;
              Gallery.applyFilters();
              Utils.toast('Файл переименован', 'success');
            } catch (err) {
              Utils.toast(`Ошибка переименования: ${err}`, 'error');
            }
          }
        } else if (selected.length > 1) {
          if (typeof BatchOps !== 'undefined') {
            BatchOps.showRenameModal();
          }
        }
        break;
      }
      case 'export': {
        if (typeof BatchOps !== 'undefined') {
          BatchOps.showExportModal();
        }
        break;
      }
      case 'delete': {
        const ok = await API.askConfirm(`Удалить ${selected.length} файл(ов) в корзину WiPhoto?`);
        if (ok) {
          const deleted = await API.deleteFiles(selected.map(i => i.path));
          Gallery.removeImages(deleted);
          if (typeof Sidebar !== 'undefined' && typeof App !== 'undefined' && App.currentFolder) {
            Sidebar.loadFolderTree(App.currentFolder);
          }
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
