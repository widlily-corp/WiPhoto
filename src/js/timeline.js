// ═══ Timeline Module ═══

const Timeline = (() => {
  const container = () => document.getElementById('timeline-container');

  function init() {
    // Timeline is re-rendered whenever we switch to the timeline view
  }

  function render() {
    const parent = container();
    if (!parent) return;

    parent.innerHTML = '';
    const images = Gallery.getFilteredImages();

    if (images.length === 0) {
      parent.innerHTML = `
        <div class="gallery-empty">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" opacity="0.3">
            <rect x="3" y="3" width="18" height="18" rx="2"/>
            <circle cx="8.5" cy="8.5" r="1.5"/>
            <polyline points="21 15 16 10 5 21"/>
          </svg>
          <p>Нет файлов для отображения</p>
        </div>
      `;
      return;
    }

    // Group images by year and month
    const groups = {};

    images.forEach(img => {
      let year = 'Без даты';
      let monthKey = '00';
      let monthName = 'Без даты';

      const date = Utils.parseExifDate(img.date_taken);
      if (date) {
        year = date.getFullYear().toString();
        // Month indexes are 0-11, map to double digit string
        const mVal = date.getMonth();
        monthKey = mVal.toString().padStart(2, '0');
        monthName = date.toLocaleDateString('ru-RU', { month: 'long' });
      }

      if (!groups[year]) groups[year] = {};
      if (!groups[year][monthKey]) groups[year][monthKey] = { name: monthName, items: [] };
      groups[year][monthKey].items.push(img);
    });

    // Sort years descending
    const sortedYears = Object.keys(groups).sort((a, b) => {
      if (a === 'Без даты') return 1;
      if (b === 'Без даты') return -1;
      return b.localeCompare(a);
    });

    const fragment = document.createDocumentFragment();

    sortedYears.forEach(year => {
      const yearDiv = Utils.el('div', { className: 'timeline-year' });
      const yearTitle = Utils.el('div', { className: 'timeline-year-title', textContent: year });
      yearDiv.appendChild(yearTitle);

      // Sort months descending within year
      const months = groups[year];
      const sortedMonths = Object.keys(months).sort((a, b) => b.localeCompare(a));

      sortedMonths.forEach(mKey => {
        const monthInfo = months[mKey];
        const monthDiv = Utils.el('div', { className: 'timeline-month' });
        const monthTitle = Utils.el('div', {
          className: 'timeline-month-title',
          textContent: monthInfo.name.toUpperCase(),
        });
        const grid = Utils.el('div', { className: 'timeline-month-grid' });

        monthInfo.items.forEach(img => {
          const thumb = Utils.el('div', {
            className: 'timeline-thumb',
            title: img.filename,
          });

          const imgEl = Utils.el('img', {
            src: img.thumbnail ? Utils.base64Src(img.thumbnail) : '',
            alt: img.filename,
            loading: 'lazy',
          });

          thumb.appendChild(imgEl);

          // Click handler
          thumb.addEventListener('click', (e) => {
            // Select in the main gallery structure
            document.querySelectorAll('.timeline-thumb').forEach(t => t.style.outline = 'none');
            thumb.style.outline = '2px solid var(--accent-primary)';
            
            // Sync with sidebar preview
            Sidebar.showPreview(img);
            
            // Keep status bar updated
            document.getElementById('status-text').textContent = `Временная шкала │ ${img.filename} │ ${Utils.formatSize(img.file_size)}`;
          });

          // Double click handler
          thumb.addEventListener('dblclick', () => {
            Viewer.open(img);
          });

          grid.appendChild(thumb);
        });

        monthDiv.appendChild(monthTitle);
        monthDiv.appendChild(grid);
        yearDiv.appendChild(monthDiv);
      });

      fragment.appendChild(yearDiv);
    });

    parent.appendChild(fragment);
  }

  return { init, render };
})();

window.Timeline = Timeline;
