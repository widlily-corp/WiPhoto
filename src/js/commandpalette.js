// ═══ Command Palette Module (⌘K / Ctrl+K) ═══

const CommandPalette = (() => {
  let isOpen = false;
  let selectedIndex = 0;
  let filteredCommands = [];

  const commands = [
    // Files
    { id: 'select-folder', name: 'Выбрать папку для сканирования', group: 'Файлы', action: () => Welcome.selectFolder() },
    { id: 'settings', name: 'Открыть настройки', group: 'Файлы', action: () => Settings.open() },
    { id: 'about', name: 'О программе WiPhoto', group: 'Файлы', action: () => Settings.showAbout() },
    
    // View
    { id: 'view-gallery', name: 'Перейти в режим: Галерея', group: 'Вид', action: () => App.switchView('gallery') },
    { id: 'view-map', name: 'Перейти в режим: Карта', group: 'Вид', action: () => App.switchView('map') },
    { id: 'view-timeline', name: 'Перейти в режим: Таймлайн', group: 'Вид', action: () => App.switchView('timeline') },
    { id: 'toggle-left-sidebar', name: 'Свернуть/развернуть левый сайдбар', group: 'Вид', action: () => document.getElementById('toggle-left')?.click() },
    { id: 'toggle-right-sidebar', name: 'Свернуть/развернуть правый сайдбар', group: 'Вид', action: () => document.getElementById('toggle-right')?.click() },
    
    // Edit
    { id: 'edit-photo', name: 'Редактировать выбранное изображение', group: 'Редактирование', action: () => {
        const sel = Gallery.getSelectedImages();
        if (sel.length > 0) App.openEditor(sel[0]);
        else Utils.toast('Выберите фотографию для редактирования', 'warning');
    }},
    { id: 'undo-edit', name: 'Отменить действие в редакторе (Undo)', group: 'Редактирование', action: () => {
        if (document.getElementById('view-editor').classList.contains('active')) Editor.undo();
        else Utils.toast('Редактор не активен', 'warning');
    }},
    { id: 'redo-edit', name: 'Повторить действие в редакторе (Redo)', group: 'Редактирование', action: () => {
        if (document.getElementById('view-editor').classList.contains('active')) Editor.redo();
        else Utils.toast('Редактор не активен', 'warning');
    }},
    { id: 'preset-cinematic', name: 'Применить пресет: Cinematic', group: 'Редактирование', action: () => {
        if (document.getElementById('view-editor').classList.contains('active')) document.getElementById('btn-preset-cinematic')?.click();
        else Utils.toast('Редактор не активен', 'warning');
    }},
    { id: 'preset-bw', name: 'Применить пресет: BW Classic', group: 'Редактирование', action: () => {
        if (document.getElementById('view-editor').classList.contains('active')) document.getElementById('btn-preset-bw')?.click();
        else Utils.toast('Редактор не активен', 'warning');
    }},
    { id: 'preset-vibrant', name: 'Применить пресет: Vibrant', group: 'Редактирование', action: () => {
        if (document.getElementById('view-editor').classList.contains('active')) document.getElementById('btn-preset-vibrant')?.click();
        else Utils.toast('Редактор не активен', 'warning');
    }},

    // Navigation / Filters
    { id: 'filter-all', name: 'Фильтр: Показать все файлы', group: 'Навигация', action: () => document.querySelector('.filter-btn[data-filter="all"]')?.click() },
    { id: 'filter-best', name: 'Фильтр: Показать только лучшие (★)', group: 'Навигация', action: () => document.querySelector('.filter-btn[data-filter="best"]')?.click() },
    { id: 'filter-duplicates', name: 'Фильтр: Показать дубликаты', group: 'Навигация', action: () => document.querySelector('.filter-btn[data-filter="duplicates"]')?.click() },
    { id: 'filter-picked', name: 'Фильтр: Показать отмеченные (Picked)', group: 'Навигация', action: () => document.querySelector('.filter-btn[data-filter="picked"]')?.click() },
    { id: 'filter-rejected', name: 'Фильтр: Показать отклоненные (Rejected)', group: 'Навигация', action: () => document.querySelector('.filter-btn[data-filter="rejected"]')?.click() },
    { id: 'nav-trash', name: 'Открыть корзину', group: 'Навигация', action: () => {
        if (typeof Trash !== 'undefined') Trash.open();
    }},
  ];

  const palette = () => document.getElementById('command-palette');
  const input = () => document.getElementById('command-palette-input');
  const list = () => document.getElementById('command-palette-list');

  function init() {
    // Keyboard listener for Cmd+K / Ctrl+K
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
  }

  function filter(query) {
    const q = query.toLowerCase().trim();
    if (!q) {
      filteredCommands = [...commands];
    } else {
      filteredCommands = commands.filter(cmd => 
        cmd.name.toLowerCase().includes(q) || cmd.group.toLowerCase().includes(q)
      );
    }
    selectedIndex = 0;
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

      const item = Utils.el('div', {
        className: `command-palette__item${index === selectedIndex ? ' active' : ''}`,
        onClick: () => {
          selectedIndex = index;
          executeSelected();
        }
      }, [
        Utils.el('span', { className: 'command-palette__item-name', textContent: cmd.name }),
        Utils.el('span', { className: 'command-palette__item-shortcut', textContent: getShortcutLabel(cmd.id) })
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
      'select-folder': 'Ctrl+O',
      'settings': 'Ctrl+,',
      'view-gallery': 'G',
      'view-map': 'M',
      'view-timeline': 'T',
      'undo-edit': 'Ctrl+Z',
      'redo-edit': 'Ctrl+Y',
      'edit-photo': 'Enter',
      'nav-trash': '🗑️'
    };
    return shortcuts[id] || '';
  }

  return { init, show, hide, toggle };
})();

window.CommandPalette = CommandPalette;
