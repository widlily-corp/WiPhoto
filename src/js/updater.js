// ═══ OTA Updater API Wrapper & Release Notes UI ═══

/**
 * Compares semver version strings to determine if targetVersion is strictly newer than currentVersion.
 * @param {string} currentVersion 
 * @param {string} targetVersion 
 * @returns {boolean}
 */
function isNewerVersion(currentVersion, targetVersion) {
  if (typeof currentVersion !== 'string' || typeof targetVersion !== 'string') return false;
  const parse = v => v.replace(/^v/, '').split('.').map(n => parseInt(n, 10) || 0);
  const cur = parse(currentVersion);
  const tar = parse(targetVersion);

  for (let i = 0; i < Math.max(cur.length, tar.length); i++) {
    const c = cur[i] || 0;
    const t = tar[i] || 0;
    if (t > c) return true;
    if (t < c) return false;
  }
  return false;
}

/**
 * Lightweight Markdown renderer for release notes.
 * Converts markdown headers, bold, italics, code blocks, lists, and line breaks to sanitized HTML.
 * @param {string} markdown 
 * @returns {string}
 */
function renderMarkdown(markdown) {
  if (!markdown || typeof markdown !== 'string') return '<p>Нет описания изменений.</p>';

  // HTML escaping to prevent XSS
  let html = markdown
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Code blocks ```code```
  html = html.replace(/```([\s\S]*?)```/g, (match, code) => {
    return `<pre><code>${code.trim()}</code></pre>`;
  });

  // Inline code `code`
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Links [text](url)
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

  // Headers (# H1, ## H2, ### H3)
  html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');

  // Bold **text** or __text__
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/__(.*?)__/g, '<strong>$1</strong>');

  // Italic *text* or _text_
  html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
  html = html.replace(/_(.*?)_/g, '<em>$1</em>');

  // Bullet lists (- item or * item)
  const lines = html.split('\n');
  let inList = false;
  const processedLines = [];

  for (let line of lines) {
    const listMatch = line.match(/^\s*[\-\*]\s+(.*)$/);
    if (listMatch) {
      if (!inList) {
        inList = true;
        processedLines.push('<ul>');
      }
      processedLines.push(`<li>${listMatch[1]}</li>`);
    } else {
      if (inList) {
        inList = false;
        processedLines.push('</ul>');
      }
      processedLines.push(line);
    }
  }
  if (inList) {
    processedLines.push('</ul>');
  }

  html = processedLines.join('\n');

  // Paragraphs for double newlines
  const blocks = html.split(/\n\n+/);
  html = blocks.map(block => {
    block = block.trim();
    if (!block) return '';
    if (block.startsWith('<h') || block.startsWith('<ul>') || block.startsWith('<pre>') || block.startsWith('<p>')) {
      return block;
    }
    return `<p>${block.replace(/\n/g, '<br>')}</p>`;
  }).filter(Boolean).join('\n');

  return html;
}

/**
 * Parses raw update response from Tauri updater or GitHub API.
 * @param {Object} payload 
 * @returns {Object} { available: boolean, version: string, date: string, body: string }
 */
function parseReleaseNotes(payload) {
  if (!payload) return { available: false, version: '', date: '', body: '' };
  const hasVersion = Boolean(payload.version || payload.tag_name);
  const available = payload.available !== undefined ? Boolean(payload.available) : hasVersion;
  return {
    available: available || hasVersion,
    version: payload.version || payload.tag_name || '',
    date: payload.date || payload.published_at || '',
    body: payload.body || payload.notes || 'Обновления и улучшения производительности.'
  };
}

let activeUpdateObject = null;

const UpdaterAPI = {
  /**
   * Checks for application updates against GitHub Releases via Tauri updater plugin.
   * @returns {Promise<Object|null>}
   */
  checkForUpdates: async () => {
    try {
      if (window.__TAURI__?.updater?.check) {
        const update = await window.__TAURI__.updater.check();
        if (update && update.available) {
          activeUpdateObject = update;
          return {
            available: true,
            version: update.version,
            date: update.date || '',
            body: update.body || 'Новая версия WiPhoto готова к установке.'
          };
        }
      } else if (window.__TAURI__?.core?.invoke) {
        const updateInfo = await window.__TAURI__.core.invoke('plugin:updater|check');
        if (updateInfo && updateInfo.available) {
          activeUpdateObject = updateInfo;
          return parseReleaseNotes(updateInfo);
        }
      }
    } catch (err) {
      if (typeof Logger !== 'undefined') {
        Logger.error('Updater', 'Failed to check for updates', err);
      } else {
        console.error('Failed to check for updates:', err);
      }
    }
    return null;
  },

  /**
   * Downloads and installs the pending update.
   * @param {Object} updateObj 
   * @param {Function} onProgress 
   * @returns {Promise<boolean>}
   */
  installUpdate: async (updateObj, onProgress) => {
    const targetObj = updateObj || activeUpdateObject;
    try {
      if (targetObj && typeof targetObj.downloadAndInstall === 'function') {
        await targetObj.downloadAndInstall(onProgress);
        return true;
      } else if (window.__TAURI__?.core?.invoke) {
        await window.__TAURI__.core.invoke('plugin:updater|download_and_install');
        return true;
      }
    } catch (err) {
      if (typeof Logger !== 'undefined') {
        Logger.error('Updater', 'Failed to download and install update', err);
      } else {
        console.error('Failed to download and install update:', err);
      }
    }
    return false;
  },

  /**
   * Relaunches the application via tauri-plugin-process or fallback IPC.
   * @returns {Promise<boolean>}
   */
  relaunchApp: async () => {
    try {
      if (window.__TAURI__?.process?.relaunch) {
        await window.__TAURI__.process.relaunch();
        return true;
      } else if (window.__TAURI__?.core?.invoke) {
        await window.__TAURI__.core.invoke('plugin:process|relaunch');
        return true;
      } else if (window.__TAURI_PLUGIN_PROCESS__?.relaunch) {
        await window.__TAURI_PLUGIN_PROCESS__.relaunch();
        return true;
      }
    } catch (err) {
      if (typeof Logger !== 'undefined') {
        Logger.error('Updater', 'Failed to relaunch application', err);
      } else {
        console.error('Failed to relaunch application:', err);
      }
    }
    return false;
  }
};

/**
 * Display update modal with release notes rendered from Markdown.
 * @param {Object} updateInfo 
 */
function showUpdateModal(updateInfo) {
  const modal = document.getElementById('modal-updater');
  if (!modal) return;

  const versionTag = document.getElementById('updater-version-tag');
  const releaseNotesEl = document.getElementById('updater-release-notes');
  const statusMsg = document.getElementById('updater-status-message');

  const parsed = parseReleaseNotes(updateInfo);

  if (versionTag) {
    versionTag.textContent = `Новая версия: ${parsed.version ? 'v' + parsed.version.replace(/^v/, '') : 'Доступно обновление'}`;
  }

  if (releaseNotesEl) {
    releaseNotesEl.innerHTML = renderMarkdown(parsed.body);
  }

  if (statusMsg) {
    statusMsg.classList.add('hidden');
    statusMsg.textContent = '';
  }

  modal.classList.remove('hidden');
}

/**
 * Hides update modal.
 */
function hideUpdateModal() {
  const modal = document.getElementById('modal-updater');
  if (modal) {
    modal.classList.add('hidden');
  }
}

/**
 * Initializes Updater UI button handlers for "Update Now" ("Обновить сейчас") and "Postpone" ("Отложить").
 */
function initUpdaterUI() {
  const btnInstall = document.getElementById('btn-updater-install');
  const btnPostpone = document.getElementById('btn-updater-postpone');
  const closeBtns = document.querySelectorAll('[data-close="modal-updater"]');
  const statusMsg = document.getElementById('updater-status-message');

  if (btnInstall) {
    btnInstall.addEventListener('click', async () => {
      btnInstall.disabled = true;
      if (btnPostpone) btnPostpone.disabled = true;

      if (statusMsg) {
        statusMsg.classList.remove('hidden');
        statusMsg.textContent = 'Загрузка и установка обновления...';
      }

      const success = await UpdaterAPI.installUpdate(activeUpdateObject);
      if (success) {
        if (statusMsg) {
          statusMsg.textContent = 'Обновление успешно установлено! Перезапуск приложения...';
        }
        setTimeout(async () => {
          const relaunched = await UpdaterAPI.relaunchApp();
          if (!relaunched) {
            hideUpdateModal();
          }
        }, 1500);
      } else {
        if (statusMsg) {
          statusMsg.textContent = 'Ошибка при установке обновления. Попробуйте позже.';
        }
        btnInstall.disabled = false;
        if (btnPostpone) btnPostpone.disabled = false;
      }
    });
  }

  if (btnPostpone) {
    btnPostpone.addEventListener('click', () => {
      hideUpdateModal();
    });
  }

  closeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      hideUpdateModal();
    });
  });
}

// Auto-initialize UI on DOMContentLoaded if running in browser
if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initUpdaterUI);
  } else {
    initUpdaterUI();
  }
}

// Export for Node environment (tests) and window
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    isNewerVersion,
    renderMarkdown,
    parseReleaseNotes,
    UpdaterAPI,
    showUpdateModal,
    hideUpdateModal,
    initUpdaterUI
  };
}

if (typeof window !== 'undefined') {
  window.UpdaterAPI = UpdaterAPI;
  window.isNewerVersion = isNewerVersion;
  window.renderMarkdown = renderMarkdown;
  window.parseReleaseNotes = parseReleaseNotes;
  window.showUpdateModal = showUpdateModal;
  window.hideUpdateModal = hideUpdateModal;
}
