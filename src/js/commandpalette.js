// ═══ Command Palette Module (⌘K / Ctrl+K) ═══

const CommandPalette = (() => {
  let isOpen = false;
  let selectedIndex = 0;
  let filteredCommands = [];
  let previousFocusedElement = null;
  let isInitialized = false;

  const commands = [

    // Pro Operations & Compare
    { id: 'compare-photos', name: 'Сравнить выбранные фотографии (Compare Mode)', group: 'Инструменты', shortcut: 'C', action: () => {
        const sel = Gallery.getSelectedImages();
        if (sel.length >= 2) {
          CompareMode.open(Gallery.getFilteredImages(), sel[0].path, sel[1].path);
        } else {
          Utils.toast('Выберите как минимум 2 фотографии для сравнения', 'warning');
        }
    }},

    // Ratings & Flags
    { id: 'rate-5', name: 'Установить рейтинг: 5 звёзд (★★★★★)', group: 'Оценки и метки', shortcut: '5', action: () => {
        Gallery.setRating(5);
        Utils.toast('Установлен рейтинг: 5 звёзд', 'info');
    }},
    { id: 'rate-4', name: 'Установить рейтинг: 4 звезды (★★★★☆)', group: 'Оценки и метки', shortcut: '4', action: () => {
        Gallery.setRating(4);
        Utils.toast('Установлен рейтинг: 4 звезды', 'info');
    }},
    { id: 'rate-3', name: 'Установить рейтинг: 3 звезды (★★★☆☆)', group: 'Оценки и метки', shortcut: '3', action: () => {
        Gallery.setRating(3);
        Utils.toast('Установлен рейтинг: 3 звезды', 'info');
    }},
    { id: 'rate-0', name: 'Снять рейтинг (0 звёзд)', group: 'Оценки и метки', shortcut: '0', action: () => {
        Gallery.setRating(0);
        Utils.toast('Рейтинг сброшен', 'info');
    }},
    { id: 'flag-pick', name: 'Отметить как отобранное (Pick)', group: 'Оценки и метки', shortcut: 'P', action: () => {
        Gallery.setFlagStatus('picked');
        Utils.toast('Флаг: Выбранные', 'info');
    }},
    { id: 'flag-reject', name: 'Отклонить / брак (Reject)', group: 'Оценки и метки', shortcut: 'X', action: () => {
        Gallery.setFlagStatus('rejected');
        Utils.toast('Флаг: Отклонённые', 'info');
    }},
    { id: 'flag-clear', name: 'Снять флаг отбора', group: 'Оценки и метки', shortcut: 'U', action: () => {
        Gallery.setFlagStatus('');
        Utils.toast('Флаг снят', 'info');
    }},

    // Selection
    { id: 'select-all', name: 'Выделить все изображения', group: 'Выделение', shortcut: 'Ctrl+A', action: () => Gallery.selectAll() },
    { id: 'clear-selection', name: 'Снять выделение со всех фото', group: 'Выделение', shortcut: 'Esc', action: () => Gallery.clearSelection() },
    { id: 'invert-selection', name: 'Инвертировать выделение', group: 'Выделение', shortcut: '', action: () => Gallery.invertSelection() },

    // Navigation & Zoom
    { id: 'focus-search', name: 'Поиск по фото (CLIP / имя / тег)', group: 'Навигация', shortcut: 'Ctrl+F', action: () => {
        const el = document.getElementById('search-input');
        if (el) { el.focus(); el.select(); }
    }},
    { id: 'view-fullscreen', name: 'Полноэкранный просмотр', group: 'Вид', shortcut: 'F', action: () => {
        const sel = Gallery.getSelectedImages();
        if (sel.length > 0) Viewer.open(sel[0]);
        else Utils.toast('Выберите фото для просмотра', 'warning');
    }},
    { id: 'toggle-inspector', name: 'Свернуть/развернуть панель инспектора', group: 'Вид', shortcut: 'Ctrl+I', action: () => {
        const rightSidebar = document.getElementById('right-sidebar');
        if (rightSidebar) rightSidebar.classList.toggle('collapsed');
    }},
    { id: 'zoom-in', name: 'Увеличить размер миниатюр', group: 'Вид', shortcut: 'Ctrl++', action: () => {
        const slider = document.getElementById('zoom-slider');
        if (slider) {
          slider.value = Math.min(320, parseInt(slider.value, 10) + 20);
          slider.dispatchEvent(new Event('input'));
        }
    }},
    { id: 'zoom-out', name: 'Уменьшить размер миниатюр', group: 'Вид', shortcut: 'Ctrl+-', action: () => {
        const slider = document.getElementById('zoom-slider');
        if (slider) {
          slider.value = Math.max(100, parseInt(slider.value, 10) - 20);
          slider.dispatchEvent(new Event('input'));
        }
    }},

    // Files
    { id: 'select-folder', name: 'Выбрать папку для сканирования', group: 'Файлы', shortcut: 'Ctrl+O', action: () => Welcome.selectFolder() },
    { id: 'settings', name: 'Открыть настройки', group: 'Файлы', shortcut: 'Ctrl+,', action: () => Settings.open() },
    { id: 'about', name: 'О программе WiPhoto', group: 'Файлы', shortcut: '', action: () => Settings.showAbout() },
    { id: 'check-updates', name: 'Проверить обновления (OTA)', group: 'Файлы', shortcut: '', action: () => {
        if (typeof UpdaterAPI !== 'undefined') {
          Utils.toast('Проверка наличия обновлений...', 'info');
          UpdaterAPI.checkForUpdates({ isManual: true }).then(res => {
            if (res && res.success) {
              if (res.available && typeof showUpdateModal === 'function') {
                showUpdateModal(res);
              } else {
                Utils.toast('У вас установлена актуальная версия WiPhoto', 'success');
              }
            }
          });
        }
    }},
    
    // View
    { id: 'view-gallery', name: 'Перейти в режим: Галерея', group: 'Вид', shortcut: 'G', action: () => App.switchView('gallery') },
    { id: 'view-map', name: 'Перейти в режим: Карта', group: 'Вид', shortcut: 'M', action: () => App.switchView('map') },
    { id: 'view-timeline', name: 'Перейти в режим: Таймлайн', group: 'Вид', shortcut: 'T', action: () => App.switchView('timeline') },
    { id: 'toggle-left-sidebar', name: 'Свернуть/развернуть левый сайдбар', group: 'Вид', shortcut: 'Ctrl+[', action: () => document.getElementById('toggle-left')?.click() },
    { id: 'toggle-right-sidebar', name: 'Свернуть/развернуть правый сайдбар', group: 'Вид', shortcut: 'Ctrl+]', action: () => document.getElementById('toggle-right')?.click() },
    { id: 'slideshow', name: 'Запустить слайдшоу', group: 'Вид', shortcut: 'F8', action: () => document.getElementById('btn-slideshow')?.click() },

    // Edit
    { id: 'edit-photo', name: 'Редактировать выбранное изображение', group: 'Редактирование', shortcut: 'Enter', action: () => {
        const sel = Gallery.getSelectedImages();
        if (sel.length > 0) App.openEditor(sel[0]);
        else Utils.toast('Выберите фотографию для редактирования', 'warning');
    }},
    { id: 'undo-edit', name: 'Отменить действие в редакторе (Undo)', group: 'Редактирование', shortcut: 'Ctrl+Z', action: () => {
        if (document.getElementById('view-editor').classList.contains('active')) Editor.undo();
        else Utils.toast('Редактор не активен', 'warning');
    }},
    { id: 'redo-edit', name: 'Повторить действие в редакторе (Redo)', group: 'Редактирование', shortcut: 'Ctrl+Y', action: () => {
        if (document.getElementById('view-editor').classList.contains('active')) Editor.redo();
        else Utils.toast('Редактор не активен', 'warning');
    }},
    { id: 'preset-cinematic', name: 'Применить пресет: Cinematic', group: 'Редактирование', shortcut: '', action: () => {
        if (document.getElementById('view-editor').classList.contains('active')) document.getElementById('btn-preset-cinematic')?.click();
        else Utils.toast('Редактор не активен', 'warning');
    }},
    { id: 'preset-bw', name: 'Применить пресет: BW Classic', group: 'Редактирование', shortcut: '', action: () => {
        if (document.getElementById('view-editor').classList.contains('active')) document.getElementById('btn-preset-bw')?.click();
        else Utils.toast('Редактор не активен', 'warning');
    }},
    { id: 'preset-vibrant', name: 'Применить пресет: Vibrant', group: 'Редактирование', shortcut: '', action: () => {
        if (document.getElementById('view-editor').classList.contains('active')) document.getElementById('btn-preset-vibrant')?.click();
        else Utils.toast('Редактор не активен', 'warning');
    }},
    { id: 'preset-moody', name: 'Применить пресет: Moody', group: 'Редактирование', shortcut: '', action: () => {
        if (document.getElementById('view-editor').classList.contains('active')) document.getElementById('btn-preset-moody')?.click();
        else Utils.toast('Редактор не активен', 'warning');
    }},

    // Tools & Operations
    { id: 'find-duplicates', name: 'Поиск дубликатов', group: 'Инструменты', shortcut: '', action: () => {
        if (typeof Settings !== 'undefined' && typeof Settings.showDuplicateFinder === 'function') {
          Settings.showDuplicateFinder();
        } else if (typeof App !== 'undefined' && typeof App.showDuplicateFinder === 'function') {
          App.showDuplicateFinder();
        }
    }},
    { id: 'batch-rename', name: 'Пакетное переименование', group: 'Инструменты', shortcut: 'F2', action: () => {
        if (typeof BatchOps !== 'undefined' && typeof BatchOps.showRenameModal === 'function') {
          BatchOps.showRenameModal();
        }
    }},
    { id: 'batch-export', name: 'Пакетный экспорт', group: 'Инструменты', shortcut: 'Ctrl+E', action: () => {
        if (typeof BatchOps !== 'undefined' && typeof BatchOps.showExportModal === 'function') {
          BatchOps.showExportModal();
        }
    }},
    { id: 'nav-trash', name: 'Открыть корзину удалённых файлов', group: 'Инструменты', shortcut: 'Del', action: () => {
        if (typeof Trash !== 'undefined') Trash.open();
    }},

    // Navigation / Filters
    { id: 'filter-all', name: 'Фильтр: Показать все файлы', group: 'Фильтры', shortcut: '', action: () => document.querySelector('.filter-btn[data-filter="all"]')?.click() },
    { id: 'filter-best', name: 'Фильтр: Показать только лучшие (★)', group: 'Фильтры', shortcut: '', action: () => document.querySelector('.filter-btn[data-filter="best"]')?.click() },
    { id: 'filter-duplicates', name: 'Фильтр: Показать дубликаты', group: 'Фильтры', shortcut: '', action: () => document.querySelector('.filter-btn[data-filter="duplicates"]')?.click() },
    { id: 'filter-picked', name: 'Фильтр: Показать отмеченные (Picked)', group: 'Фильтры', shortcut: '', action: () => document.querySelector('.filter-btn[data-filter="picked"]')?.click() },
    { id: 'filter-rejected', name: 'Фильтр: Показать отклоненные (Rejected)', group: 'Фильтры', shortcut: '', action: () => document.querySelector('.filter-btn[data-filter="rejected"]')?.click() }
  ];

  const palette = () => document.getElementById('command-palette');
  const input = () => document.getElementById('command-palette-input');
  const list = () => document.getElementById('command-palette-list');

  function init() {
    if (isInitialized) return;
    isInitialized = true;
    // Global keyboard listener for Cmd+K / Ctrl+K
    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        toggle();
      }
    });

    // Close on backdrop click
    palette()?.querySelector('.command-palette__backdrop')?.addEventListener('click', hide);

    // Search input filtering
    input()?.addEventListener('input', (e) => {
      filter(e.target.value);
    });

    // Keyboard navigation inside input
    input()?.addEventListener('keydown', (e) => {
      if (!isOpen) return;

      switch (e.key) {
        case 'Escape':
          e.preventDefault();
          hide();
          break;
        case 'ArrowDown':
          e.preventDefault();
          navigate(1);
          break;
        case 'ArrowUp':
          e.preventDefault();
          navigate(-1);
          break;
        case 'Enter':
          e.preventDefault();
          executeSelected();
          break;
      }
    });
  }

  function toggle() {
    if (isOpen) hide();
    else show();
  }

  function show() {
    isOpen = true;
    selectedIndex = 0;
    previousFocusedElement = document.activeElement;
    palette()?.classList.remove('hidden');
    const inputEl = input();
    if (inputEl) {
      inputEl.value = '';
      inputEl.focus();
    }
    filter('');
  }

  function hide() {
    isOpen = false;
    palette()?.classList.add('hidden');
    if (previousFocusedElement && typeof previousFocusedElement.focus === 'function') {
      try {
        previousFocusedElement.focus();
      } catch {
        // Ignore focus errors
      }
    }
  }

  function filterPaletteItems(items, query) {
    if (!Array.isArray(items)) return [];
    if (!query || typeof query !== 'string' || query.trim() === '') return items;
    const q = query.toLowerCase().trim();
    return items.filter(item => {
      const nameMatch = item.name && item.name.toLowerCase().includes(q);
      const titleMatch = item.title && item.title.toLowerCase().includes(q);
      const groupMatch = item.group && item.group.toLowerCase().includes(q);
      const catMatch = item.category && item.category.toLowerCase().includes(q);
      const shortcutMatch = item.shortcut && item.shortcut.toLowerCase().includes(q);
      return nameMatch || titleMatch || groupMatch || catMatch || shortcutMatch;
    });
  }

  function clampSelectedIndex(index, totalItems) {
    if (totalItems <= 0) return -1;
    if (index < 0) return 0;
    if (index >= totalItems) return totalItems - 1;
    return index;
  }

  function filter(query) {
    filteredCommands = filterPaletteItems(commands, query);
    selectedIndex = clampSelectedIndex(0, filteredCommands.length);
    render();
  }

  function render() {
    const container = list();
    if (!container) return;
    container.innerHTML = '';

    if (filteredCommands.length === 0) {
      container.appendChild(Utils.el('div', {
        className: 'command-palette__empty',
        textContent: 'Команды не найдены'
      }));
      return;
    }

    let currentGroup = '';
    const fragment = document.createDocumentFragment();

    filteredCommands.forEach((cmd, index) => {
      if (cmd.group !== currentGroup) {
        currentGroup = cmd.group;
        fragment.appendChild(Utils.el('div', {
          className: 'command-palette__group-title',
          textContent: currentGroup
        }));
      }

      const shortcutText = cmd.shortcut || getShortcutLabel(cmd.id);

      const item = Utils.el('div', {
        className: `command-palette__item${index === selectedIndex ? ' active' : ''}`,
        onClick: () => {
          selectedIndex = index;
          executeSelected();
        }
      }, [
        Utils.el('span', { className: 'command-palette__item-name', textContent: cmd.name }),
        shortcutText ? Utils.el('span', { className: 'command-palette__item-shortcut', textContent: shortcutText }) : document.createTextNode('')
      ]);

      fragment.appendChild(item);
    });

    container.appendChild(fragment);

    // Scroll active item into view
    const activeItem = container.querySelector('.command-palette__item.active');
    if (activeItem) {
      activeItem.scrollIntoView({ block: 'nearest' });
    }
  }

  function navigate(direction) {
    if (filteredCommands.length === 0) return;
    selectedIndex = (selectedIndex + direction + filteredCommands.length) % filteredCommands.length;
    render();
  }

  function executeSelected() {
    const cmd = filteredCommands[selectedIndex];
    if (cmd) {
      hide();
      cmd.action();
    }
  }

  function getShortcutLabel(id) {
    const shortcuts = {
      'compare-photos': 'C',
      'rate-5': '5',
      'rate-4': '4',
      'rate-3': '3',
      'rate-0': '0',
      'flag-pick': 'P',
      'flag-reject': 'X',
      'flag-clear': 'U',
      'select-all': 'Ctrl+A',
      'clear-selection': 'Esc',
      'focus-search': 'Ctrl+F',
      'view-fullscreen': 'F',
      'toggle-inspector': 'Ctrl+I',
      'zoom-in': 'Ctrl++',
      'zoom-out': 'Ctrl+-',
      'select-folder': 'Ctrl+O',
      'settings': 'Ctrl+,',
      'view-gallery': 'G',
      'view-map': 'M',
      'view-timeline': 'T',
      'toggle-left-sidebar': 'Ctrl+[',
      'toggle-right-sidebar': 'Ctrl+]',
      'slideshow': 'F8',
      'undo-edit': 'Ctrl+Z',
      'redo-edit': 'Ctrl+Y',
      'edit-photo': 'Enter',
      'batch-rename': 'F2',
      'batch-export': 'Ctrl+E',
      'nav-trash': 'Del'
    };
    return shortcuts[id] || '';
  }

  return { init, show, hide, toggle, filterPaletteItems, clampSelectedIndex, getCommands: () => commands };
})();

window.CommandPalette = CommandPalette;

