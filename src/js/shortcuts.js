// ═══ Global Keyboard Shortcuts Module ═══

const Shortcuts = (() => {
  let isInitialized = false;

  function init() {
    if (isInitialized) return;
    isInitialized = true;
    window.addEventListener('keydown', handleKeyDown);
  }

  async function handleKeyDown(e) {
    // Ignore shortcuts when user is typing in inputs or textareas
    const activeEl = document.activeElement;
    if (activeEl && (
      activeEl.tagName === 'INPUT' ||
      activeEl.tagName === 'TEXTAREA' ||
      activeEl.tagName === 'SELECT' ||
      activeEl.isContentEditable
    )) {
      // Allow Escape to close modals even if focused on input
      if (e.key === 'Escape') {
        closeActiveOverlays();
      }
      return;
    }

    const selected = Gallery.getSelectedImages();
    const isEditorActive = document.getElementById('view-editor').classList.contains('active');
    const isViewerActive = !document.getElementById('fullscreen-viewer').classList.contains('hidden');
    const isSlideshowActive = !document.getElementById('slideshow-overlay').classList.contains('hidden');
    const isCompareActive = document.getElementById('compare-viewer') && !document.getElementById('compare-viewer').classList.contains('hidden');

    // ─── Universal Shortcuts ───
    if (e.key === 'Escape') {
      e.preventDefault();
      closeActiveOverlays();
      return;
    }

    // ─── Editor Shortcuts ───
    if (isEditorActive) {
      if (e.ctrlKey && e.key.toLowerCase() === 'z') {
        e.preventDefault();
        Editor.undo();
        return;
      }
      if (e.ctrlKey && e.key.toLowerCase() === 'y') {
        e.preventDefault();
        Editor.redo();
        return;
      }
      if (e.ctrlKey && e.key.toLowerCase() === 's') {
        e.preventDefault();
        Editor.saveImage();
        return;
      }
      return; // Do not process gallery shortcuts when editor is active
    }

    // ─── Viewer / Slideshow Navigation Shortcuts ───
    if (isViewerActive || isSlideshowActive || isCompareActive) {
      return; // Handled by their respective modules
    }

    // ─── Gallery / Main View Shortcuts ───

    // ─── Gallery Keyboard Navigation & Ergonomics ───
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      Gallery.navigateSelection('right', e.shiftKey);
      return;
    }
    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      Gallery.navigateSelection('left', e.shiftKey);
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      Gallery.navigateSelection('down', e.shiftKey);
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      Gallery.navigateSelection('up', e.shiftKey);
      return;
    }
    if (e.key === 'Home') {
      e.preventDefault();
      Gallery.navigateSelection('home', e.shiftKey);
      return;
    }
    if (e.key === 'End') {
      e.preventDefault();
      Gallery.navigateSelection('end', e.shiftKey);
      return;
    }
    if (e.key === 'PageUp') {
      e.preventDefault();
      Gallery.navigateSelection('pageup', e.shiftKey);
      return;
    }
    if (e.key === 'PageDown') {
      e.preventDefault();
      Gallery.navigateSelection('pagedown', e.shiftKey);
      return;
    }

    // Quick Search: Ctrl+F, /, or F3
    if ((e.ctrlKey && e.key.toLowerCase() === 'f') || e.key === '/' || e.key === 'F3') {
      const searchInput = document.getElementById('search-input');
      if (searchInput) {
        e.preventDefault();
        searchInput.focus();
        searchInput.select();
      }
      return;
    }

    // View Switching: G (Gallery), M (Map), T (Timeline)
    if (!e.ctrlKey && !e.altKey) {
      if (e.key.toLowerCase() === 'g') {
        e.preventDefault();
        App.switchView('gallery');
        return;
      }
      if (e.key.toLowerCase() === 'm') {
        e.preventDefault();
        App.switchView('map');
        return;
      }
      if (e.key.toLowerCase() === 't') {
        e.preventDefault();
        App.switchView('timeline');
        return;
      }
    }

    // C: Compare Mode when 2+ items selected
    if (e.key.toLowerCase() === 'c' && !e.ctrlKey && !e.altKey) {
      if (selected.length >= 2) {
        e.preventDefault();
        document.getElementById('btn-compare')?.click();
      }
      return;
    }

    // Ctrl+I: Toggle Right Sidebar Inspector
    if (e.ctrlKey && e.key.toLowerCase() === 'i') {
      e.preventDefault();
      const rightSidebar = document.getElementById('right-sidebar');
      if (rightSidebar) rightSidebar.classList.toggle('collapsed');
      return;
    }

    // Ctrl+[: Toggle Left Sidebar
    if (e.ctrlKey && e.key === '[') {
      e.preventDefault();
      document.getElementById('toggle-left')?.click();
      return;
    }

    // Ctrl+]: Toggle Right Sidebar
    if (e.ctrlKey && e.key === ']') {
      e.preventDefault();
      document.getElementById('toggle-right')?.click();
      return;
    }

    // Ctrl++ / Ctrl+-: Thumbnail Zoom Slider
    if ((e.key === '+' || e.key === '=') && e.ctrlKey) {
      e.preventDefault();
      const slider = document.getElementById('zoom-slider');
      if (slider) {
        slider.value = Math.min(320, parseInt(slider.value, 10) + 20);
        slider.dispatchEvent(new Event('input'));
      }
      return;
    }
    if (e.key === '-' && e.ctrlKey) {
      e.preventDefault();
      const slider = document.getElementById('zoom-slider');
      if (slider) {
        slider.value = Math.max(100, parseInt(slider.value, 10) - 20);
        slider.dispatchEvent(new Event('input'));
      }
      return;
    }

    
    // F8: Slideshow
    if (e.key === 'F8') {
      e.preventDefault();
      if (typeof Slideshow !== 'undefined') {
        Slideshow.start();
      }
      return;
    }

    // F2: Batch Rename
    if (e.key === 'F2') {
      e.preventDefault();
      if (typeof BatchOps !== 'undefined') {
        BatchOps.showRenameModal();
      }
      return;
    }

    // Ctrl+E: Batch Export
    if (e.ctrlKey && e.key.toLowerCase() === 'e') {
      e.preventDefault();
      if (typeof BatchOps !== 'undefined') {
        BatchOps.showExportModal();
      }
      return;
    }

    // F1: About
    if (e.key === 'F1') {
      e.preventDefault();
      Settings.showAbout();
      return;
    }

    // Ctrl+,: Settings
    if (e.ctrlKey && e.key === ',') {
      e.preventDefault();
      Settings.open();
      return;
    }

    // Ctrl+D: Duplicate Search / Compare
    if (e.ctrlKey && e.key.toLowerCase() === 'd') {
      e.preventDefault();
      Settings.showDuplicateFinder();
      return;
    }

    // Ctrl+A: Select All
    if (e.ctrlKey && e.key.toLowerCase() === 'a') {
      e.preventDefault();
      Gallery.selectAll();
      return;
    }

    // E: Edit
    if (e.key.toLowerCase() === 'e') {
      if (selected.length === 1) {
        e.preventDefault();
        App.openEditor(selected[0]);
      }
      return;
    }

    // F / Enter: Fullscreen
    if (e.key.toLowerCase() === 'f' || e.key === 'Enter') {
      if (selected.length > 0) {
        e.preventDefault();
        Viewer.open(selected[0]);
      }
      return;
    }

    // Space: Toggle Right Sidebar Preview
    if (e.key === ' ') {
      e.preventDefault();
      const rightSidebar = document.getElementById('right-sidebar');
      if (rightSidebar) {
        rightSidebar.classList.toggle('collapsed');
      }
      return;
    }

    // Delete: Delete selected
    if (e.key === 'Delete') {
      if (selected.length > 0) {
        e.preventDefault();
        const ok = await API.askConfirm(`Удалить ${selected.length} файл(ов) в корзину WiPhoto?`);
        if (ok) {
          try {
            const deleted = await API.deleteFiles(selected.map(i => i.path));
            Gallery.removeImages(deleted);
            Sidebar.clearPreview();
            Utils.toast(`Удалено: ${deleted.length}`, 'success');
          } catch (err) {
            Utils.toast(`Ошибка удаления: ${err}`, 'error');
          }
        }
      }
      return;
    }

    // Ctrl+C: Copy selected
    if (e.ctrlKey && e.key.toLowerCase() === 'c') {
      if (selected.length > 0) {
        e.preventDefault();
        try {
          const dest = await API.openFolderDialog();
          if (dest) {
            const count = await API.copyFiles(selected.map(i => i.path), dest);
            Utils.toast(`Скопировано файлов: ${count}`, 'success');
          }
        } catch (err) {
          Utils.toast(`Ошибка копирования: ${err}`, 'error');
        }
      }
      return;
    }

    // Ctrl+X: Move selected
    if (e.ctrlKey && e.key.toLowerCase() === 'x') {
      if (selected.length > 0) {
        e.preventDefault();
        try {
          const dest = await API.openFolderDialog();
          if (dest) {
            const moved = await API.moveFiles(selected.map(i => i.path), dest);
            Gallery.removeImages(moved);
            Sidebar.clearPreview();
            Utils.toast(`Перемещено файлов: ${moved.length}`, 'success');
          }
        } catch (err) {
          Utils.toast(`Ошибка перемещения: ${err}`, 'error');
        }
      }
      return;
    }

    // Ratings: 0-5
    if (e.key >= '0' && e.key <= '5') {
      if (selected.length > 0) {
        e.preventDefault();
        Gallery.setRating(parseInt(e.key));
        Utils.toast(`Установлен рейтинг: ${e.key} звёзд`, 'info');
      }
      return;
    }

    // Flags: P (Pick), X (Reject), U (Unflag)
    if (e.key.toLowerCase() === 'p') {
      if (selected.length > 0) {
        e.preventDefault();
        Gallery.setFlagStatus('picked');
        Utils.toast('Флаг: Выбранные', 'info');
      }
      return;
    }
    if (e.key.toLowerCase() === 'x') {
      if (selected.length > 0) {
        e.preventDefault();
        Gallery.setFlagStatus('rejected');
        Utils.toast('Флаг: Отклонённые', 'info');
      }
      return;
    }
    if (e.key.toLowerCase() === 'u') {
      if (selected.length > 0) {
        e.preventDefault();
        Gallery.setFlagStatus('');
        Utils.toast('Флаг снят', 'info');
      }
      return;
    }

    // Color Labels: 6-9
    // 6: Red, 7: Yellow, 8: Green, 9: Blue
    const colorMap = {
      '6': 'red',
      '7': 'yellow',
      '8': 'green',
      '9': 'blue'
    };
    if (e.key in colorMap) {
      if (selected.length > 0) {
        e.preventDefault();
        const color = colorMap[e.key];
        Gallery.setColorLabel(color);
        Utils.toast(`Цветовая метка: ${color}`, 'info');
      }
      return;
    }
  }

  function closeActiveOverlays() {
    // 0. If compare viewer is active, close it
    const compareViewer = document.getElementById('compare-viewer');
    if (compareViewer && !compareViewer.classList.contains('hidden')) {
      if (typeof CompareMode !== 'undefined') CompareMode.close();
      return;
    }
    // 1. If slideshow is active, close it
    const slideshow = document.getElementById('slideshow-overlay');
    if (slideshow && !slideshow.classList.contains('hidden')) {
      if (typeof Slideshow !== 'undefined') Slideshow.stop();
      return;
    }

    // 2. If fullscreen viewer is active, close it
    const viewer = document.getElementById('fullscreen-viewer');
    if (viewer && !viewer.classList.contains('hidden')) {
      if (typeof Viewer !== 'undefined') Viewer.close();
      return;
    }

    // 3. If editor is active, close it
    const editor = document.getElementById('view-editor');
    if (editor && editor.classList.contains('active')) {
      if (typeof Editor !== 'undefined') Editor.close();
      return;
    }

    // 4. Close any open modals
    document.querySelectorAll('.modal').forEach(m => m.classList.add('hidden'));
  }

  return { init };
})();

window.Shortcuts = Shortcuts;
