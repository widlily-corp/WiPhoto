// ═══ Tags Module with Autocomplete ═══

const Tags = (() => {
  let activeImage = null;
  let activeAutocompleteIdx = -1;
  let autocompleteList = [];

  const listEl = () => document.getElementById('image-tags-list');
  const inputEl = () => document.getElementById('tag-input');
  const autocompleteEl = () => document.getElementById('tag-autocomplete');
  const globalListEl = () => document.getElementById('global-tags-list');

  function init() {
    const input = inputEl();
    if (!input) return;

    input.addEventListener('input', (e) => {
      showAutocomplete(e.target.value);
    });

    input.addEventListener('keydown', (e) => {
      const dropdown = autocompleteEl();
      if (!dropdown || dropdown.classList.contains('hidden')) {
        if (e.key === 'Enter' && input.value.trim()) {
          e.preventDefault();
          addTag(input.value.trim());
        }
        return;
      }

      const items = dropdown.querySelectorAll('.tag-autocomplete-item');
      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          navigateAutocomplete(1, items);
          break;
        case 'ArrowUp':
          e.preventDefault();
          navigateAutocomplete(-1, items);
          break;
        case 'Enter':
          e.preventDefault();
          if (activeAutocompleteIdx >= 0 && items[activeAutocompleteIdx]) {
            items[activeAutocompleteIdx].click();
          } else if (input.value.trim()) {
            addTag(input.value.trim());
          }
          break;
        case 'Escape':
          e.preventDefault();
          hideAutocomplete();
          break;
      }
    });

    // Hide autocomplete on click outside
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.tag-input-container')) {
        hideAutocomplete();
      }
    });
  }

  function updateSelectedImage(imageInfo) {
    activeImage = imageInfo;
    const input = inputEl();
    if (input) {
      input.value = '';
      input.removeAttribute('disabled');
    }
    renderImageTags();
    hideAutocomplete();
  }

  function clear() {
    activeImage = null;
    const list = listEl();
    if (list) list.innerHTML = '';
    const input = inputEl();
    if (input) {
      input.value = '';
      input.setAttribute('disabled', 'true');
    }
    hideAutocomplete();
  }

  function renderImageTags() {
    const list = listEl();
    if (!list) return;
    list.innerHTML = '';

    if (!activeImage) return;

    const tags = activeImage.tags || [];
    if (tags.length === 0) {
      list.innerHTML = '<span class="tags-placeholder">Нет тегов</span>';
      return;
    }

    tags.forEach(tag => {
      const chip = Utils.el('span', { className: 'tag-chip', textContent: tag }, [
        Utils.el('button', {
          className: 'tag-remove',
          textContent: '✕',
          onClick: (e) => {
            e.stopPropagation();
            removeTag(tag);
          }
        })
      ]);
      list.appendChild(chip);
    });
  }

  function showAutocomplete(query) {
    const dropdown = autocompleteEl();
    if (!dropdown) return;

    const val = query.toLowerCase().trim();
    if (!val) {
      hideAutocomplete();
      return;
    }

    // Get all unique global tags, excluding ones the active image already has
    const allTags = Gallery.getAllTags();
    const currentTags = activeImage ? (activeImage.tags || []) : [];
    
    autocompleteList = allTags.filter(tag => 
      tag.toLowerCase().includes(val) && !currentTags.includes(tag)
    );

    if (autocompleteList.length === 0) {
      hideAutocomplete();
      return;
    }

    dropdown.innerHTML = '';
    activeAutocompleteIdx = -1;

    autocompleteList.forEach((tag) => {
      const item = Utils.el('div', {
        className: 'tag-autocomplete-item',
        textContent: tag,
        onClick: () => {
          addTag(tag);
          hideAutocomplete();
        }
      });
      dropdown.appendChild(item);
    });

    dropdown.classList.remove('hidden');
  }

  function navigateAutocomplete(direction, items) {
    if (items.length === 0) return;

    if (activeAutocompleteIdx >= 0) {
      items[activeAutocompleteIdx].classList.remove('active');
    }

    activeAutocompleteIdx = (activeAutocompleteIdx + direction + items.length) % items.length;
    items[activeAutocompleteIdx].classList.add('active');
    items[activeAutocompleteIdx].scrollIntoView({ block: 'nearest' });
  }

  function hideAutocomplete() {
    const dropdown = autocompleteEl();
    if (dropdown) {
      dropdown.classList.add('hidden');
      dropdown.innerHTML = '';
    }
    activeAutocompleteIdx = -1;
    autocompleteList = [];
  }

  function addTag(tag) {
    if (!activeImage) return;
    const cleanTag = tag.trim();
    if (!cleanTag) return;

    Gallery.addTagToSelected(cleanTag);
    // Add locally to the active image object to update UI immediately
    if (!activeImage.tags) activeImage.tags = [];
    if (!activeImage.tags.includes(cleanTag)) {
      activeImage.tags.push(cleanTag);
    }

    const input = inputEl();
    if (input) input.value = '';

    renderImageTags();
    renderGlobalTags();
  }

  function removeTag(tag) {
    if (!activeImage) return;

    Gallery.removeTagFromSelected(tag);
    if (activeImage.tags) {
      activeImage.tags = activeImage.tags.filter(t => t !== tag);
    }

    renderImageTags();
    renderGlobalTags();
  }

  // Render unique global tags in the left sidebar
  let currentActiveFilterTag = '';
  function renderGlobalTags() {
    const container = globalListEl();
    if (!container) return;
    container.innerHTML = '';

    const allTags = Gallery.getAllTags();
    if (allTags.length === 0) {
      container.innerHTML = '<span class="tags-placeholder" style="padding: 4px 12px; display:block;">Нет тегов</span>';
      return;
    }

    allTags.forEach(tag => {
      const isActive = tag === currentActiveFilterTag;
      const btn = Utils.el('button', {
        className: `global-tag-btn${isActive ? ' active' : ''}`,
        onClick: () => {
          if (isActive) {
            currentActiveFilterTag = '';
            Gallery.clearTagFilter();
          } else {
            currentActiveFilterTag = tag;
            Gallery.filterByTag(tag);
          }
          renderGlobalTags();
        }
      }, [
        document.createTextNode(tag),
        isActive ? Utils.el('span', { className: 'clear-tag', textContent: ' ✕' }) : null
      ]);
      container.appendChild(btn);
    });
  }

  return { init, updateSelectedImage, clear, renderGlobalTags };
})();

window.Tags = Tags;
