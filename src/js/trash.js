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
    } catch (err) {
      Logger.warn('Trash', "Failed to load badge count", err);
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
          className: 'trash-item-row'
        }, [
          // Previews
          Utils.el('img', {
            className: 'trash-item-thumb',
            src: item.thumbnail ? Utils.base64Src(item.thumbnail) : ''
          }),
          // Info
          Utils.el('div', { className: 'trash-item-info' }, [
            Utils.el('div', {
              className: 'trash-item-name',
              textContent: item.filename
            }),
            Utils.el('div', {
              className: 'trash-item-path',
              textContent: `Из: ${item.original_path}`
            })
          ]),
          // Actions
          Utils.el('div', { className: 'trash-item-actions' }, [
            Utils.el('button', {
              className: 'btn btn-secondary btn-sm btn-trash-action',
              textContent: 'Восстановить',
              onClick: () => restore(item.filename)
            }),
            Utils.el('button', {
              className: 'btn btn-danger btn-sm btn-trash-action btn-trash-delete-perm',
              textContent: 'Удалить',
              onClick: () => deletePermanently(item.path, item.filename)
            })
          ])
        ]);
        fragment.appendChild(itemRow);
      });
      list.appendChild(fragment);
    } catch (err) {
      list.innerHTML = `<div class="trash-error-msg">Ошибка: ${err}</div>`;
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
