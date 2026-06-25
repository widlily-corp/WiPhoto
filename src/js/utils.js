// ═══ Utility Functions ═══

const Utils = {
  /** Format file size */
  formatSize(bytes) {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    let s = bytes;
    while (s >= 1024 && i < units.length - 1) { s /= 1024; i++; }
    return `${s.toFixed(1)} ${units[i]}`;
  },

  /** Debounce function */
  debounce(fn, ms = 250) {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), ms);
    };
  },

  /** Throttle function */
  throttle(fn, ms = 100) {
    let last = 0;
    return (...args) => {
      const now = Date.now();
      if (now - last >= ms) { last = now; fn(...args); }
    };
  },

  /** Generate stars HTML */
  starsHtml(rating) {
    return '★'.repeat(rating) + '☆'.repeat(5 - rating);
  },

  /** Escape HTML */
  escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  },

  /** Parse date from EXIF format */
  parseExifDate(dateStr) {
    if (!dateStr) return null;
    // Format: "2024:01:15 14:30:00" or "2024-01-15T14:30:00"
    const cleaned = dateStr.replace(/^"(.*)"$/, '$1').replace(/(\d{4}):(\d{2}):(\d{2})/, '$1-$2-$3');
    const d = new Date(cleaned);
    return isNaN(d.getTime()) ? null : d;
  },

  /** Format date */
  formatDate(date) {
    if (!date) return '';
    const d = date instanceof Date ? date : new Date(date);
    if (isNaN(d.getTime())) return '';
    return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' });
  },

  /** Format date for grouping */
  formatDateGroup(dateStr) {
    const d = Utils.parseExifDate(dateStr);
    if (!d) return 'Без даты';
    return d.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' });
  },

  /** Get file extension */
  getExtension(path) {
    const parts = path.split('.');
    return parts.length > 1 ? parts.pop().toLowerCase() : '';
  },

  /** Get filename from path */
  getFilename(path) {
    return path.split(/[/\\]/).pop() || '';
  },

  /** Create element shorthand */
  el(tag, attrs = {}, children = []) {
    const elem = document.createElement(tag);
    for (const [key, val] of Object.entries(attrs)) {
      if (key === 'className') elem.className = val;
      else if (key === 'textContent') elem.textContent = val;
      else if (key === 'innerHTML') elem.innerHTML = val;
      else if (key.startsWith('on')) elem.addEventListener(key.slice(2).toLowerCase(), val);
      else elem.setAttribute(key, val);
    }
    children.forEach(child => {
      if (typeof child === 'string') elem.appendChild(document.createTextNode(child));
      else if (child) elem.appendChild(child);
    });
    return elem;
  },

  /** Show toast notification */
  toast(message, type = 'info', duration = 4000) {
    let container = document.querySelector('.toast-container');
    if (!container) {
      container = Utils.el('div', { className: 'toast-container' });
      document.body.appendChild(container);
    }
    const toast = Utils.el('div', { className: `toast ${type}` }, [
      document.createTextNode(message),
      Utils.el('button', { className: 'toast-close', textContent: '✕', onClick: () => toast.remove() }),
    ]);
    container.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); }, duration);
  },

  /** Clone selected images paths */
  getSelectedPaths() {
    const selected = document.querySelectorAll('.thumb-card.selected');
    return Array.from(selected).map(el => el.dataset.path);
  },

  /** Base64 to image src */
  base64Src(b64) {
    return `data:image/jpeg;base64,${b64}`;
  },
};

window.Utils = Utils;
