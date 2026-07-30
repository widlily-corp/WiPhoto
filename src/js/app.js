// ═══ Main Application Module & Entry Point ═══

const App = (() => {
  let activeTab = 'gallery'; // gallery, map, timeline
  let mapInstance = null;
  let mapMarkers = [];
  let leafletLoaded = false;

  // Global state
  const state = {
    currentFolder: '',
  };

  function init() {
    // 1. Initialize Sub-Modules
    Welcome.init();
    Gallery.init();
    Sidebar.init();
    Viewer.init();
    Editor.init();
    Settings.init();
    Shortcuts.init();
    Slideshow.init();
    Timeline.init();
    CommandPalette.init();
    if (typeof ContextMenu !== 'undefined') {
      ContextMenu.init();
    }
    if (typeof Trash !== 'undefined') {
      Trash.init();
    }
    if (typeof BatchOps !== 'undefined') {
      BatchOps.init();
    }

    // 2. View Mode Switchers
    document.querySelectorAll('.view-modes button.toolbar-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const view = btn.dataset.view;
        if (view) {
          switchView(view);
        }
      });
    });

    // ─── Toolbar Action Bindings ───
    document.getElementById('btn-delete')?.addEventListener('click', async () => {
      const selected = Gallery.getSelectedImages();
      if (selected.length === 0) {
        Utils.toast('Файлы не выбраны', 'warning');
        return;
      }
      
      const ok = await API.askConfirm(`Удалить ${selected.length} файл(ов) в корзину WiPhoto?`);
      if (!ok) return;

      try {
        const deleted = await API.deleteFiles(selected.map(i => i.path));
        Gallery.removeImages(deleted);
        Sidebar.clearPreview();
        Utils.toast(`Удалено: ${deleted.length}`, 'success');
      } catch (err) {
        Utils.toast(`Ошибка удаления: ${err}`, 'error');
      }
    });

    document.getElementById('btn-copy')?.addEventListener('click', async () => {
      const selected = Gallery.getSelectedImages();
      if (selected.length === 0) {
        Utils.toast('Файлы не выбраны', 'warning');
        return;
      }
      
      try {
        const dest = await API.openFolderDialog();
        if (!dest) return;
        
        const count = await API.copyFiles(selected.map(i => i.path), dest);
        Utils.toast(`Скопировано файлов: ${count}`, 'success');
      } catch (err) {
        Utils.toast(`Ошибка копирования: ${err}`, 'error');
      }
    });

    document.getElementById('btn-move')?.addEventListener('click', async () => {
      const selected = Gallery.getSelectedImages();
      if (selected.length === 0) {
        Utils.toast('Файлы не выбраны', 'warning');
        return;
      }
      
      try {
        const dest = await API.openFolderDialog();
        if (!dest) return;
        
        const moved = await API.moveFiles(selected.map(i => i.path), dest);
        Gallery.removeImages(moved);
        Sidebar.clearPreview();
        Utils.toast(`Перемещено файлов: ${moved.length}`, 'success');
      } catch (err) {
        Utils.toast(`Ошибка перемещения: ${err}`, 'error');
      }
    });

    document.getElementById('btn-keep-best')?.addEventListener('click', async () => {
      const selected = Gallery.getSelectedImages();
      if (selected.length === 0) {
        Utils.toast('Выберите фотографии из групп дубликатов', 'warning');
        return;
      }

      const confirm = await API.askConfirm('Оставить только лучшие фотографии в группах и отклонить остальные?', 'Оставить лучшее');
      if (!confirm) return;

      try {
        // Flag best as picked and duplicates in groups as rejected
        // Gather groups present in selection
        const groups = new Set(selected.map(i => i.group_id).filter(Boolean));
        let pickedCount = 0;
        let rejectedCount = 0;

        Gallery.getAllImages().forEach(img => {
          if (!img.group_id || !groups.has(img.group_id)) return;
          
          if (img.is_best_in_group) {
            img.flag_status = 'picked';
            pickedCount++;
          } else {
            img.flag_status = 'rejected';
            rejectedCount++;
          }
          API.writeXmpSidecar(img.path, img.rating, img.color_label, img.flag_status, img.tags || []);
        });

        Gallery.applyFilters();
        Utils.toast(`Отмечено лучших: ${pickedCount}, отклонено дубликатов: ${rejectedCount}`, 'success');
      } catch (err) {
        Utils.toast(`Ошибка: ${err}`, 'error');
      }
    });

    document.getElementById('btn-compare')?.addEventListener('click', () => {
      showDuplicateFinder();
    });

    document.getElementById('btn-slideshow')?.addEventListener('click', () => {
      Slideshow.start();
    });
  }

  // Switch between center views
  function switchView(viewName) {
    // Prevent switching to map/timeline if no folder loaded
    if (viewName !== 'gallery' && viewName !== 'editor' && !state.currentFolder) {
      Utils.toast('Сначала выберите и загрузите папку с фотографиями', 'warning');
      return;
    }

    // Toggle views active class
    document.querySelectorAll('.center-area > .view').forEach(view => {
      view.classList.remove('active');
    });

    const activeView = document.getElementById(`view-${viewName}`);
    if (activeView) {
      activeView.classList.add('active');
    }

    // Hide contextual bar if leaving gallery
    if (viewName !== 'gallery') {
      document.getElementById('contextual-bar')?.classList.add('hidden');
    } else if (typeof Gallery !== 'undefined' && Gallery.getSelectedImages().length > 0) {
      document.getElementById('contextual-bar')?.classList.remove('hidden');
    }

    // Toggle active state in view mode buttons (if not editor)
    if (viewName !== 'editor') {
      activeTab = viewName;
      document.querySelectorAll('.view-modes button.toolbar-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === viewName);
      });
      // Show view-mode selector in toolbar
      document.querySelector('.view-modes')?.classList.remove('hidden');
    } else {
      // Hide view-mode selectors while in Editor
      document.querySelector('.view-modes')?.classList.add('hidden');
    }

    // Trigger sub-module updates
    if (viewName === 'timeline') {
      Timeline.render();
    } else if (viewName === 'map') {
      renderMap();
    }
  }

  // Open editor
  function openEditor(imageInfo) {
    switchView('editor');
    Editor.open(imageInfo);
  }

  // Show duplicate finder settings modal
  function showDuplicateFinder() {
    Settings.showDuplicateFinder();
  }

  // Dynamic script loader for Leaflet
  function loadLeaflet() {
    return new Promise((resolve, reject) => {
      if (leafletLoaded) {
        resolve();
        return;
      }

      // Link Leaflet CSS
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
      document.head.appendChild(link);

      // Script Leaflet JS
      const script = document.createElement('script');
      script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
      script.onload = () => {
        leafletLoaded = true;
        resolve();
      };
      script.onerror = () => reject(new Error('Не удалось загрузить Leaflet Map API с CDN unpkg'));
      document.head.appendChild(script);
    });
  }

  // Render Leaflet Map
  async function renderMap() {
    try {
      await loadLeaflet();
      
      const mapContainer = document.getElementById('map-container');
      if (!mapContainer) return;

      // Initialize map instance if not already initialized
      if (!mapInstance) {
        mapInstance = L.map('map-container').setView([55.7558, 37.6173], 4); // Centered on Moscow as default
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          maxZoom: 19,
          attribution: '&copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(mapInstance);
      }

      // Clear existing markers
      mapMarkers.forEach(m => mapInstance.removeLayer(m));
      mapMarkers = [];

      const images = Gallery.getFilteredImages();
      const bounds = [];

      images.forEach(img => {
        if (img.gps_location && img.gps_location.length === 2) {
          const [lat, lon] = img.gps_location;
          bounds.push([lat, lon]);

          const thumbSrc = img.thumbnail ? Utils.assetUrl(img.thumbnail) : '';

          // Create marker
          const marker = L.marker([lat, lon]).addTo(mapInstance);
          
          // Bind popup showing file preview
          const popupContent = `
            <div style="text-align: center; font-family: var(--font-family); font-size: 11px;">
              <img src="${thumbSrc}" style="width: 100px; height: 100px; object-fit: cover; border-radius: 4px; display: block; margin: 0 auto 6px; border: 1px solid var(--border-subtle); cursor: pointer;" onclick="App.openPopupImage('${img.path}')" />
              <div style="font-weight: 500; color: #fff; max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${img.filename}</div>
              <div style="color: var(--text-muted); margin-top: 2px;">${lat.toFixed(4)}, ${lon.toFixed(4)}</div>
            </div>
          `;
          
          marker.bindPopup(popupContent, {
            className: 'wiphoto-map-popup'
          });

          // Open preview in sidebar on marker click
          marker.on('click', () => {
            Sidebar.showPreview(img);
          });

          mapMarkers.push(marker);
        }
      });

      // Fit map bounds to show all markers if any exist
      if (bounds.length > 0) {
        mapInstance.fitBounds(bounds, { padding: [40, 40] });
      }

      // Invalidate map size so it renders correctly inside the layout container
      setTimeout(() => {
        mapInstance.invalidateSize();
      }, 200);

    } catch (err) {
      Utils.toast(`Ошибка инициализации карты: ${err.message}`, 'error');
    }
  }

  // Helper function globally accessible to handle clicks on map popup images
  function openPopupImage(path) {
    const images = Gallery.getFilteredImages();
    const img = images.find(i => i.path === path);
    if (img) {
      Viewer.open(img);
    }
  }

  // Expose methods to global scope
  return {
    init,
    switchView,
    openEditor,
    showDuplicateFinder,
    renderMap,
    openPopupImage,
    get currentFolder() { return state.currentFolder; },
    set currentFolder(val) { state.currentFolder = val; }
  };
})();

// Bootstrap Application
document.addEventListener('DOMContentLoaded', () => {
  try {
    const info = [];
    info.push(`window.__TAURI__ exists: ${!!window.__TAURI__}`);
    if (window.__TAURI__) {
      info.push(`window.__TAURI__.core exists: ${!!window.__TAURI__.core}`);
      info.push(`window.__TAURI__.event exists: ${!!window.__TAURI__.event}`);
      if (window.__TAURI__.event) {
        info.push(`window.__TAURI__.event.listen type: ${typeof window.__TAURI__.event.listen}`);
      }
      info.push(`window.__TAURI__.dialog exists: ${!!window.__TAURI__.dialog}`);
    }
    if (window.API && typeof window.API.logJs === 'function') {
      window.API.logJs(`Frontend init diagnostic:\n${info.join('\n')}`);
    }
  } catch (e) {
    console.error(e);
  }
  App.init();
  window.App = App;
});
