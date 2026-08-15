// ═══ Settings & Modals Module ═══

const Settings = (() => {
  let currentSettings = null;

  function init() {
    // ─── Modal Close Helpers ───
    document.querySelectorAll('.modal-close, .modal-overlay').forEach(el => {
      el.addEventListener('click', (e) => {
        const modal = e.target.closest('.modal');
        if (modal) {
          modal.classList.add('hidden');
        }
      });
    });

    // ─── Settings Modal Trigger ───
    document.getElementById('btn-settings')?.addEventListener('click', open);

    // Save settings button
    document.getElementById('btn-save-settings')?.addEventListener('click', save);

    // Clear cache button
    document.getElementById('btn-clear-cache')?.addEventListener('click', clearCache);

    // OTA Update Check buttons
    const triggerUpdateCheck = async () => {
      if (typeof UpdaterAPI !== 'undefined') {
        Utils.toast('Проверка наличия обновлений...', 'info');
        try {
          const res = await UpdaterAPI.checkForUpdates({ isManual: true });
          if (res && res.success) {
            if (res.available && typeof showUpdateModal === 'function') {
              showUpdateModal(res);
            } else {
              Utils.toast('У вас установлена актуальная версия WiPhoto', 'success');
            }
          }
        } catch (err) {
          Utils.toast(`Ошибка при проверке обновлений: ${err}`, 'error');
        }
      } else {
        Utils.toast('Модуль обновления недоступен', 'warning');
      }
    };

    document.getElementById('btn-check-updates-settings')?.addEventListener('click', triggerUpdateCheck);
    document.getElementById('btn-check-updates-about')?.addEventListener('click', triggerUpdateCheck);

    // Sync hamming value span
    const hammingSlider = document.getElementById('setting-hamming');
    if (hammingSlider) {
      hammingSlider.addEventListener('input', (e) => {
        const valSpan = document.getElementById('hamming-value');
        if (valSpan) valSpan.textContent = e.target.value;
      });
    }

    // ─── Duplicate Finder Triggers ───
    document.getElementById('btn-start-dup-search')?.addEventListener('click', runDuplicateSearch);
  }

  // Open settings modal
  async function open() {
    try {
      currentSettings = await API.loadSettings();
      
      // Populate fields
      const workersInput = document.getElementById('setting-workers');
      if (workersInput) workersInput.value = currentSettings.worker_count;

      const rawQualitySelect = document.getElementById('setting-raw-quality');
      if (rawQualitySelect) rawQualitySelect.value = currentSettings.raw_quality;

      const sharpnessCheckbox = document.getElementById('setting-sharpness');
      if (sharpnessCheckbox) sharpnessCheckbox.checked = currentSettings.calculate_sharpness;

      const hammingInput = document.getElementById('setting-hamming');
      if (hammingInput) {
        hammingInput.value = currentSettings.hamming_threshold;
        const valSpan = document.getElementById('hamming-value');
        if (valSpan) valSpan.textContent = currentSettings.hamming_threshold;
      }

      // Show modal
      document.getElementById('modal-settings')?.classList.remove('hidden');
    } catch (err) {
      Utils.toast(`Ошибка загрузки настроек: ${err}`, 'error');
    }
  }

  // Save settings
  async function save() {
    if (!currentSettings) return;

    try {
      const workersInput = document.getElementById('setting-workers');
      const rawQualitySelect = document.getElementById('setting-raw-quality');
      const sharpnessCheckbox = document.getElementById('setting-sharpness');
      const hammingInput = document.getElementById('setting-hamming');

      const newSettings = {
        ...currentSettings,
        worker_count: parseInt(workersInput?.value || '4'),
        raw_quality: rawQualitySelect?.value || 'half',
        calculate_sharpness: sharpnessCheckbox ? sharpnessCheckbox.checked : true,
        hamming_threshold: parseInt(hammingInput?.value || '5'),
      };

      await API.saveSettings(newSettings);
      currentSettings = newSettings;

      document.getElementById('modal-settings')?.classList.add('hidden');
      Utils.toast('Настройки сохранены', 'success');
    } catch (err) {
      Utils.toast(`Ошибка сохранения: ${err}`, 'error');
    }
  }

  // Clear Cache
  async function clearCache() {
    try {
      const confirm = await API.askConfirm('Вы действительно хотите очистить кэш миниатюр?', 'Очистка кэша');
      if (!confirm) return;

      await API.clearThumbnailCache();
      Utils.toast('Кэш миниатюр успешно очищен', 'success');
    } catch (err) {
      Utils.toast(`Ошибка очистки кэша: ${err}`, 'error');
    }
  }

  // Show About Dialog
  async function showAbout() {
    try {
      const info = await API.getAppInfo();
      
      const verEl = document.getElementById('about-version');
      if (verEl) verEl.textContent = `v${info.version}`;

      const descEl = document.getElementById('about-description');
      if (descEl) descEl.textContent = info.description;

      const copyEl = document.getElementById('about-copyright');
      if (copyEl) copyEl.textContent = info.copyright;

      document.getElementById('modal-about')?.classList.remove('hidden');
    } catch (err) {
      Utils.toast(`Не удалось загрузить сведения: ${err}`, 'error');
    }
  }

  // Show Duplicate Finder Modal
  function showDuplicateFinder() {
    const progressEl = document.getElementById('dup-progress');
    const resultsEl = document.getElementById('dup-results');
    if (progressEl) progressEl.classList.add('hidden');
    if (resultsEl) resultsEl.classList.add('hidden');

    const startBtn = document.getElementById('btn-start-dup-search');
    if (startBtn) startBtn.removeAttribute('disabled');

    // Ensure the default method is selected in the UI
    const defaultRadio = document.querySelector('input[name="dup-method"][value="phash"]');
    if (defaultRadio) {
      defaultRadio.checked = true;
    }

    document.getElementById('modal-duplicates')?.classList.remove('hidden');

    // Auto-run search with recommended method (phash)
    runDuplicateSearch();
  }

  // Run Duplicate Finder Search
  async function runDuplicateSearch() {
    const images = Gallery.getAllImages();
    if (images.length === 0) {
      Utils.toast('Нет изображений для поиска дубликатов', 'warning');
      return;
    }

    const startBtn = document.getElementById('btn-start-dup-search');
    const progressEl = document.getElementById('dup-progress');
    const resultsEl = document.getElementById('dup-results');
    const progressFill = document.getElementById('dup-progress-fill');
    const statusText = document.getElementById('dup-status');

    try {
      startBtn?.setAttribute('disabled', 'true');
      if (progressEl) progressEl.classList.remove('hidden');
      if (resultsEl) resultsEl.classList.add('hidden');
      if (progressFill) progressFill.style.width = '20%';
      if (statusText) statusText.textContent = 'Подготовка к вычислению хэшей...';

      // Load settings to get hamming threshold
      const settings = currentSettings || await API.loadSettings();
      const threshold = settings.hamming_threshold;

      // Select method
      const methodRadio = document.querySelector('input[name="dup-method"]:checked');
      const method = methodRadio ? methodRadio.value : 'phash';

      let unlisten = null;
      if (typeof API.onDupProgress === 'function') {
        unlisten = await API.onDupProgress((payload) => {
          const percent = Math.round((payload.current / payload.total) * 100);
          if (progressFill) progressFill.style.width = `${percent}%`;
          if (statusText) statusText.textContent = `Сравнение хэшей: ${payload.current} / ${payload.total} (${percent}%)`;
        });
      }

      const paths = images.map(i => i.path);
      const groups = await API.findDuplicates(paths, method, threshold);

      if (unlisten) {
        unlisten();
      }

      if (progressFill) progressFill.style.width = '90%';
      if (statusText) statusText.textContent = 'Обработка результатов...';

      if (groups.length === 0) {
        if (progressEl) progressEl.classList.add('hidden');
        Utils.toast('Дубликаты не найдены', 'info');
        document.getElementById('modal-duplicates')?.classList.add('hidden');
        return;
      }

      // Load stats from backend
      const stats = await API.getDuplicateStats(groups);
      
      if (progressFill) progressFill.style.width = '100%';
      if (statusText) statusText.textContent = 'Готово!';

      // Set groups in gallery
      Gallery.setDuplicateGroups(groups);

      // Show stats summary
      const statsEl = document.getElementById('dup-stats');
      if (statsEl) {
        statsEl.innerHTML = `
          <div>Найдено групп дубликатов: <strong>${stats.total_groups}</strong></div>
          <div>Всего копий: <strong>${stats.total_duplicates}</strong></div>
          <div>Возможная экономия места: <strong>${stats.potential_savings_mb.toFixed(2)} МБ</strong></div>
        `;
      }

      if (resultsEl) resultsEl.classList.remove('hidden');
      
      // Delay closing or transition to duplicates filter
      setTimeout(() => {
        document.getElementById('modal-duplicates')?.classList.add('hidden');
        // Switch gallery filter to duplicates
        const dupFilterBtn = document.querySelector('.filter-btn[data-filter="duplicates"]');
        if (dupFilterBtn) {
          dupFilterBtn.click();
        }
        Utils.toast(`Найдено дубликатов: ${stats.total_duplicates} файлов в ${stats.total_groups} группах`, 'success');
      }, 1500);

    } catch (err) {
      Utils.toast(`Ошибка поиска дубликатов: ${err}`, 'error');
      if (progressEl) progressEl.classList.add('hidden');
      startBtn?.removeAttribute('disabled');
    }
  }

  return { init, open, save, showAbout, showDuplicateFinder };
})();

window.Settings = Settings;
