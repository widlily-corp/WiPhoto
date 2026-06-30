// ═══ Welcome Screen Module ═══

const Welcome = (() => {
  function init() {
    document.getElementById('btn-select-folder')?.addEventListener('click', () => selectFolder());

    // Listen to external OS drag-drop on welcome screen
    if (typeof API.onFileDrop === 'function') {
      API.onFileDrop((payload) => {
        const isWelcomeActive = document.getElementById('welcome-screen')?.classList.contains('active');
        if (isWelcomeActive && payload.paths && payload.paths.length > 0) {
          selectFolder(payload.paths[0]);
        }
      });
    }
  }

  async function selectFolder(folderPath = null) {
    let unlistenProgress = null;
    let unlistenScanned = null;
    let batchInterval = null;

    try {
      const folder = folderPath || await API.openFolderDialog();
      if (!folder) return;

      Logger.debug('Welcome', "selectFolder initiated for folder: " + folder);

      const recursive = document.getElementById('checkbox-recursive')?.checked ?? true;

      // Show progress container on welcome (just in case they see it before switch)
      const progressEl = document.getElementById('scan-progress');
      if (progressEl) {
        progressEl.classList.remove('hidden');
        document.getElementById('progress-text').textContent = 'Подготовка к сканированию...';
        document.getElementById('progress-fill').style.width = '0%';
      }

      // Reset gallery and transition to main app instantly
      Gallery.setImages([]);
      Sidebar.loadFolderTree(folder);
      document.getElementById('welcome-screen').classList.remove('active');
      document.getElementById('main-app').classList.add('active');
      App.currentFolder = folder;

      const galleryProgressEl = document.getElementById('gallery-scan-progress');
      const galleryProgressBar = document.getElementById('gallery-progress-bar');
      if (galleryProgressEl) {
        galleryProgressEl.classList.remove('hidden');
        if (galleryProgressBar) galleryProgressBar.style.width = '0%';
      }

      let scanBuffer = [];
      batchInterval = setInterval(() => {
        if (scanBuffer.length > 0) {
          Gallery.addImageBatch(scanBuffer);
          scanBuffer = [];
        }
      }, 150);

      // Listen for progress events
      unlistenProgress = await API.onScanProgress((data) => {
        const pct = data.total > 0 ? Math.round((data.current / data.total) * 100) : 0;
        if (progressEl) {
          document.getElementById('progress-fill').style.width = `${pct}%`;
          document.getElementById('progress-text').textContent = `Сканирование: ${data.current} / ${data.total}`;
        }
        if (galleryProgressBar) {
          galleryProgressBar.style.width = `${pct}%`;
        }
        const fn = data.current_file ? Utils.getFilename(data.current_file) : '';
        document.getElementById('status-text').textContent = `Сканирование: ${data.current} / ${data.total} │ ${fn}`;
      });

      // Listen for progressive image scans
      unlistenScanned = await API.onImageScanned((info) => {
        scanBuffer.push(info);
      });

      Logger.debug('Welcome', "Starting API.scanFolder IPC call");
      // Start scan
      const images = await API.scanFolder(folder, recursive);
      Logger.debug('Welcome', "API.scanFolder resolved with " + (images ? images.length : 'null') + " images");

      // Clear interval and unlisten
      if (batchInterval) clearInterval(batchInterval);
      if (unlistenProgress) unlistenProgress();
      if (unlistenScanned) unlistenScanned();

      if (galleryProgressEl) {
        galleryProgressEl.classList.add('hidden');
      }

      // Final batch render
      if (scanBuffer.length > 0) {
        Gallery.addImageBatch(scanBuffer);
        scanBuffer = [];
      }

      if (images.length === 0) {
        Utils.toast('Нет файлов для отображения', 'warning');
        document.getElementById('welcome-screen').classList.add('active');
        document.getElementById('main-app').classList.remove('active');
        if (progressEl) progressEl.classList.add('hidden');
        return;
      }

      // Final synchronization & sorting
      Gallery.setImages(images);
      Utils.toast(`Загружено файлов: ${images.length}`, 'success');

      // Layout report guarded with isDebug
      if (Logger.isDebug()) {
        setTimeout(() => {
          const mainApp = document.getElementById('main-app');
          const mainContent = document.querySelector('.main-content');
          const centerArea = document.getElementById('center-area');
          const viewGallery = document.getElementById('view-gallery');
          const galleryGrid = document.getElementById('gallery-grid');
          
          const report = `DOM layout dimensions report:
- #main-app: clientWidth=${mainApp?.clientWidth}, clientHeight=${mainApp?.clientHeight}
- .main-content: clientWidth=${mainContent?.clientWidth}, clientHeight=${mainContent?.clientHeight}
- #center-area: clientWidth=${centerArea?.clientWidth}, clientHeight=${centerArea?.clientHeight}
- #view-gallery: clientWidth=${viewGallery?.clientWidth}, clientHeight=${viewGallery?.clientHeight}
- #gallery-grid: clientWidth=${galleryGrid?.clientWidth}, clientHeight=${galleryGrid?.clientHeight}`;
          Logger.debug('Welcome', report);
        }, 800);
      }
    } catch (err) {
      if (batchInterval) clearInterval(batchInterval);
      if (unlistenProgress) unlistenProgress();
      if (unlistenScanned) unlistenScanned();

      Logger.error('Welcome', "Scan folder failed", err);
      Utils.toast(`Ошибка сканирования: ${err}`, 'error');
      document.getElementById('welcome-screen').classList.add('active');
      document.getElementById('main-app').classList.remove('active');
      document.getElementById('scan-progress')?.classList.add('hidden');
      document.getElementById('gallery-scan-progress')?.classList.add('hidden');
    }
  }

  return { init, selectFolder };
})();

window.Welcome = Welcome;
