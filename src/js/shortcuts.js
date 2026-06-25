// ═══ Global Keyboard Shortcuts Module ═══

const Shortcuts = (() => {
  function init() {
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
    if (isViewerActive || isSlideshowActive) {
      return; // Handled by their respective modules
    }

    // ─── Gallery / Main View Shortcuts ───
    
    // F8: Slideshow
    if (e.key === 'F8') {
      e.preventDefault();
      if (typeof Slideshow !== 'undefined') {
        Slideshow.start();
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
