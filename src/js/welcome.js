// ═══ Welcome Screen Module ═══

const Welcome = (() => {
  function init() {
    document.getElementById('btn-select-folder')?.addEventListener('click', selectFolder);
  }

  async function selectFolder() {
    try {
      const folder = await API.openFolderDialog();
      if (!folder) return;

      const recursive = document.getElementById('checkbox-recursive')?.checked ?? true;

      // Show progress
      const progressEl = document.getElementById('scan-progress');
      progressEl?.classList.remove('hidden');
      document.getElementById('progress-text').textContent = 'Подготовка к сканированию...';
      document.getElementById('progress-fill').style.width = '0%';

      // Listen for progress events
      API.onScanProgress((data) => {
        const pct = data.total > 0 ? Math.round((data.current / data.total) * 100) : 0;
        document.getElementById('progress-fill').style.width = `${pct}%`;
        document.getElementById('progress-text').textContent = `Сканирование: ${data.current} / ${data.total}`;
      });

      // Start scan
      const images = await API.scanFolder(folder, recursive);

      if (images.length === 0) {
        Utils.toast('Нет файлов для отображения', 'warning');
        progressEl?.classList.add('hidden');
        return;
      }

      // Switch to main app
      Gallery.setImages(images);
      Sidebar.loadFolderTree(folder);

      document.getElementById('welcome-screen').classList.remove('active');
      document.getElementById('main-app').classList.add('active');

      Utils.toast(`Загружено файлов: ${images.length}`, 'success');
      App.currentFolder = folder;
    } catch (err) {
      Utils.toast(`Ошибка: ${err}`, 'error');
      document.getElementById('scan-progress')?.classList.add('hidden');
    }
  }

  return { init };
})();

window.Welcome = Welcome;
