// ═══ Recycle Bin (Trash) Module ═══

const Trash = (() => {
  const modal = () => document.getElementById('modal-trash');
  const listEl = () => document.getElementById('trash-list');

  function init() {
    document.getElementById('btn-empty-trash')?.addEventListener('click', empty);
    
    // Close modal triggers
    document.querySelectorAll('[data-close="modal-trash"]').forEach(btn => {
      btn.addEventListener('click', close);
    });

    // Initial update of trash badge
    loadBadgeCount();
  }

  async function open() {
    modal()?.classList.remove('hidden');
    await load();
  }

  function close() {
    modal()?.classList.add('hidden');
  }

  async function loadBadgeCount() {
    try {
      const items = await API.listTrash();
      updateBadge(items.length);
    } catch {
      updateBadge(0);
    }
  }

  async function load() {
    const list = listEl();
    if (!list) return;
    list.innerHTML = '<div style="color:var(--text-muted);font-size:var(--font-size-sm);padding:12px;text-align:center;">Загрузка корзины...</div>';

    try {
      const items = await API.listTrash();
      list.innerHTML = '';

      if (items.length === 0) {
        list.innerHTML = '<div style="color:var(--text-muted);font-size:var(--font-size-sm);padding:24px;text-align:center;">Корзина пуста</div>';
        updateBadge(0);
        return;
      }

      updateBadge(items.length);

      const fragment = document.createDocumentFragment();
      items.forEach(item => {
        const itemRow = Utils.el('div', {
          className: 'trash-item-row',
          style: 'display:flex;align-items:center;gap:12px;padding:8px;border-bottom:1px solid var(--border-subtle);'
        }, [
          // Previews
          Utils.el('img', {
            src: item.thumbnail ? Utils.base64Src(item.thumbnail) : '',
            style: 'width:40px;height:40px;object-fit:cover;border-radius:var(--radius-sm);background:var(--bg-primary);'
          }),
          // Info
          Utils.el('div', { style: 'flex:1;min-width:0;' }, [
            Utils.el('div', {
              textContent: item.filename,
              style: 'font-size:var(--font-size-sm);font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text-primary);'
            }),
            Utils.el('div', {
              textContent: `Из: ${item.original_path}`,
              style: 'font-size:var(--font-size-xs);color:var(--text-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'
            })
          ]),
          // Actions
          Utils.el('div', { style: 'display:flex;gap:6px;' }, [
            Utils.el('button', {
              className: 'btn btn-secondary btn-sm',
              textContent: 'Восстановить',
              style: 'padding:4px 8px;font-size:11px;height:24px;',
              onClick: () => restore(item.filename)
            }),
            Utils.el('button', {
              className: 'btn btn-danger btn-sm',
              textContent: 'Удалить',
              style: 'padding:4px 8px;font-size:11px;height:24px;background:var(--color-danger);color:#fff;',
              onClick: () => deletePermanently(item.path, item.filename)
            })
          ])
        ]);
        fragment.appendChild(itemRow);
      });
      list.appendChild(fragment);
    } catch (err) {
      list.innerHTML = `<div style="color:var(--color-danger);font-size:var(--font-size-sm);padding:12px;text-align:center;">Ошибка: ${err}</div>`;
    }
  }

  async function restore(filename) {
    try {
      await API.restoreFromTrash(filename);
      Utils.toast('Файл восстановлен', 'success');
      
      await load();

      // Trigger tree & gallery reload
      if (typeof Sidebar !== 'undefined' && typeof App !== 'undefined' && App.currentFolder) {
        Sidebar.loadFolderTree(App.currentFolder);
        const recursive = document.getElementById('checkbox-recursive')?.checked ?? true;
        const images = await API.scanFolder(App.currentFolder, recursive);
        Gallery.setImages(images);
      }
    } catch (err) {
      Utils.toast(`Ошибка восстановления: ${err}`, 'error');
    }
  }

  async function deletePermanently(path, filename) {
    const confirm = await API.askConfirm(`Удалить файл ${filename} навсегда? Это действие необратимо.`);
    if (!confirm) return;

    try {
      await API.deletePermanently([path]);
      Utils.toast('Файл удален навсегда', 'success');
      await load();
    } catch (err) {
      Utils.toast(`Ошибка удаления: ${err}`, 'error');
    }
  }

  async function empty() {
    const confirm = await API.askConfirm('Очистить корзину полностью? Все удаленные файлы будут стерты навсегда.');
    if (!confirm) return;

    try {
      await API.emptyTrash();
      Utils.toast('Корзина очищена', 'success');
      await load();
    } catch (err) {
      Utils.toast(`Ошибка очистки корзины: ${err}`, 'error');
    }
  }

  function updateBadge(count) {
    const badge = document.getElementById('badge-trash');
    if (badge) {
      badge.textContent = count;
    }
  }

  return { init, open, close, load };
})();

window.Trash = Trash;
