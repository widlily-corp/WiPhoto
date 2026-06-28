// ═══ Batch Operations Module (Rename & Export) ═══

const BatchOps = (() => {
  function init() {
    // ─── Rename Modal Triggers ───
    const patternSelect = document.getElementById('rename-pattern');
    patternSelect?.addEventListener('change', (e) => {
      const customGroup = document.getElementById('custom-prefix-group');
      if (customGroup) {
        if (e.target.value === 'custom') {
          customGroup.classList.remove('hidden');
        } else {
          customGroup.classList.add('hidden');
        }
      }
    });

    document.getElementById('btn-confirm-rename')?.addEventListener('click', confirmRename);

    // ─── Export Modal Triggers ───
    const exportFormat = document.getElementById('export-format');
    exportFormat?.addEventListener('change', (e) => {
      const qualityGroup = document.getElementById('export-quality-group');
      if (qualityGroup) {
        if (e.target.value === 'original' || e.target.value === 'png') {
          qualityGroup.classList.add('hidden');
        } else {
          qualityGroup.classList.remove('hidden');
        }
      }
    });

    const qualitySlider = document.getElementById('export-quality');
    if (qualitySlider) {
      qualitySlider.addEventListener('input', (e) => {
        const valSpan = document.getElementById('export-quality-value');
        if (valSpan) valSpan.textContent = e.target.value;
      });
    }

    document.getElementById('btn-confirm-export')?.addEventListener('click', confirmExport);
  }

  function showRenameModal() {
    const selected = Gallery.getSelectedImages();
    if (selected.length === 0) {
      Utils.toast('Выберите файлы для переименования', 'warning');
      return;
    }

    const countEl = document.getElementById('rename-count');
    if (countEl) countEl.textContent = selected.length;

    // Reset fields
    const pattern = document.getElementById('rename-pattern');
    if (pattern) {
      pattern.value = 'name_n';
      pattern.dispatchEvent(new Event('change'));
    }
    const customInput = document.getElementById('rename-custom-prefix');
    if (customInput) customInput.value = '';
    const startNum = document.getElementById('rename-start-num');
    if (startNum) startNum.value = '1';

    document.getElementById('modal-batch-rename')?.classList.remove('hidden');
  }

  async function confirmRename() {
    const selected = Gallery.getSelectedImages();
    if (selected.length === 0) return;

    const pattern = document.getElementById('rename-pattern').value;
    const startNum = parseInt(document.getElementById('rename-start-num').value) || 1;
    const customPrefix = document.getElementById('rename-custom-prefix').value.trim();

    if (pattern === 'custom' && !customPrefix) {
      Utils.toast('Введите префикс имени', 'warning');
      return;
    }

    const renameMap = [];
    selected.forEach((img, idx) => {
      const ext = Utils.getExtension(img.path);
      const sep = img.path.includes('/') ? '/' : '\\';
      const dir = img.path.substring(0, img.path.lastIndexOf(sep));
      
      let stem = '';
      if (pattern === 'custom') {
        stem = customPrefix;
      } else if (pattern === 'date_n') {
        const d = Utils.parseExifDate(img.date_taken);
        if (d) {
          const y = d.getFullYear();
          const m = String(d.getMonth() + 1).padStart(2, '0');
          const day = String(d.getDate()).padStart(2, '0');
          stem = `${y}-${m}-${day}`;
        } else {
          stem = 'date-unknown';
        }
      } else {
        const origName = img.filename;
        stem = origName.substring(0, origName.lastIndexOf('.'));
      }

      const newName = `${stem}_${startNum + idx}.${ext}`;
      const newPath = `${dir}${sep}${newName}`;
      renameMap.push([img.path, newPath]);
    });

    try {
      const renamedCount = await API.batchRename(renameMap);
      if (renamedCount > 0) {
        // Sync paths in local memory
        renameMap.forEach(([oldPath, newPath]) => {
          const img = Gallery.getAllImages().find(i => i.path === oldPath);
          if (img) {
            img.path = newPath;
            img.filename = Utils.getFilename(newPath);
          }
        });
        Gallery.applyFilters();
        Utils.toast(`Успешно переименовано файлов: ${renamedCount}`, 'success');
      }
      document.getElementById('modal-batch-rename')?.classList.add('hidden');
    } catch (err) {
      Utils.toast(`Ошибка пакетного переименования: ${err}`, 'error');
    }
  }

  function showExportModal() {
    const selected = Gallery.getSelectedImages();
    if (selected.length === 0) {
      Utils.toast('Выберите файлы для экспорта', 'warning');
      return;
    }

    const countEl = document.getElementById('export-count');
    if (countEl) countEl.textContent = selected.length;

    // Reset fields
    const format = document.getElementById('export-format');
    if (format) {
      format.value = 'original';
      format.dispatchEvent(new Event('change'));
    }
    const quality = document.getElementById('export-quality');
    if (quality) quality.value = '90';
    const qualityVal = document.getElementById('export-quality-value');
    if (qualityVal) qualityVal.textContent = '90';
    const maxW = document.getElementById('export-max-w');
    if (maxW) maxW.value = '';
    const maxH = document.getElementById('export-max-h');
    if (maxH) maxH.value = '';
    const watermark = document.getElementById('export-watermark');
    if (watermark) watermark.value = '';

    document.getElementById('modal-batch-export')?.classList.remove('hidden');
  }

  async function confirmExport() {
    const selected = Gallery.getSelectedImages();
    if (selected.length === 0) return;

    const destDir = await API.openFolderDialog();
    if (!destDir) return;

    const format = document.getElementById('export-format').value;
    const quality = parseInt(document.getElementById('export-quality').value) || 90;
    const maxW = document.getElementById('export-max-w').value;
    const maxH = document.getElementById('export-max-h').value;
    const watermarkText = document.getElementById('export-watermark').value.trim();

    const paths = selected.map(i => i.path);
    const parsedMaxW = maxW ? parseInt(maxW) : null;
    const parsedMaxH = maxH ? parseInt(maxH) : null;

    Utils.toast('Выполняется экспорт файлов...', 'info', 3000);
    document.getElementById('modal-batch-export')?.classList.add('hidden');

    try {
      const exportedCount = await API.exportFiles(
        paths,
        destDir,
        format,
        quality,
        parsedMaxW,
        parsedMaxH,
        watermarkText
      );
      Utils.toast(`Экспорт завершен! Обработано файлов: ${exportedCount}`, 'success');
    } catch (err) {
      Utils.toast(`Ошибка экспорта: ${err}`, 'error');
    }
  }

  return { init, showRenameModal, showExportModal };
})();

window.BatchOps = BatchOps;
