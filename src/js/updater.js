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

/**
 * Classifies raw updater errors into structured error types with human-readable Russian messages.
 * @param {Error|string|Object} err 
 * @returns {{ code: string, message: string }}
 */
function classifyError(err) {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) {
    return {
      code: 'OFFLINE',
      message: 'Отсутствует подключение к интернету. Проверьте сетевое соединение.'
    };
  }

  const errStr = String(err?.message || err || '').toLowerCase();

  if (errStr.includes('timeout') || errStr.includes('timed out') || errStr.includes('etimedout')) {
    return {
      code: 'TIMEOUT',
      message: 'Превышено время ожидания ответа от сервера обновлений.'
    };
  }

  if (errStr.includes('500') || errStr.includes('502') || errStr.includes('503') || errStr.includes('504') || errStr.includes('server error')) {
    return {
      code: 'SERVER_ERROR',
      message: 'Ошибка сервера обновлений (5xx). Попробуйте позже.'
    };
  }

  if (errStr.includes('signature') || errStr.includes('checksum') || errStr.includes('verify') || errStr.includes('hash')) {
    return {
      code: 'SIGNATURE_ERROR',
      message: 'Ошибка проверки подлинности или целостности пакета обновления.'
    };
  }

  if (errStr.includes('offline') || errStr.includes('failed to fetch') || errStr.includes('connect') || errStr.includes('network') || errStr.includes('internet')) {
    return {
      code: 'OFFLINE',
      message: 'Сбой сети при скачивании обновления. Проверьте подключение к интернету.'
    };
  }

  return {
    code: 'UNKNOWN',
    message: typeof err === 'string' ? err : (err?.message || 'Произошла ошибка при работе с автообновлением.')
  };
}

const UPDATER_STATES = Object.freeze({
  IDLE: 'IDLE',
  CHECKING: 'CHECKING',
  UPDATE_AVAILABLE: 'UPDATE_AVAILABLE',
  DOWNLOADING: 'DOWNLOADING',
  VERIFYING: 'VERIFYING',
  RESTARTING: 'RESTARTING',
  ERROR: 'ERROR'
});

let currentUpdaterState = UPDATER_STATES.IDLE;
let downloadedBytes = 0;
let totalBytes = 0;
let activeUpdateObject = null;

function getUpdaterState() {
  return currentUpdaterState;
}

function setUpdaterState(newState, details = {}) {
  currentUpdaterState = newState;

  if (typeof Logger !== 'undefined') {
    Logger.info('Updater', `State transition -> ${newState}`, details);
  }

  const btnInstall = typeof document !== 'undefined' ? document.getElementById('btn-updater-install') : null;
  const btnPostpone = typeof document !== 'undefined' ? document.getElementById('btn-updater-postpone') : null;
  const closeBtns = typeof document !== 'undefined' ? document.querySelectorAll('[data-close="modal-updater"]') : [];
  const progressContainer = typeof document !== 'undefined' ? document.getElementById('updater-progress-container') : null;
  const statusMsg = typeof document !== 'undefined' ? document.getElementById('updater-status-message') : null;
  const errContainer = typeof document !== 'undefined' ? document.getElementById('updater-error-container') : null;
  const errMsgEl = typeof document !== 'undefined' ? document.getElementById('updater-error-message') : null;

  switch (newState) {
    case UPDATER_STATES.DOWNLOADING:
      if (btnInstall) btnInstall.disabled = true;
      if (btnPostpone) btnPostpone.disabled = true;
      closeBtns.forEach(btn => { if (btn) btn.disabled = true; });
      if (progressContainer) progressContainer.classList.remove('hidden');
      if (errContainer) errContainer.classList.add('hidden');
      if (statusMsg) {
        statusMsg.classList.remove('hidden', 'updater-status-error');
        statusMsg.textContent = 'Загрузка и установка обновления...';
      }
      break;

    case UPDATER_STATES.VERIFYING:
      if (btnInstall) btnInstall.disabled = true;
      if (btnPostpone) btnPostpone.disabled = true;
      closeBtns.forEach(btn => { if (btn) btn.disabled = true; });
      if (progressContainer) progressContainer.classList.remove('hidden');
      if (errContainer) errContainer.classList.add('hidden');
      if (statusMsg) {
        statusMsg.classList.remove('hidden', 'updater-status-error');
        statusMsg.textContent = 'Проверка целостности пакета...';
      }
      break;

    case UPDATER_STATES.RESTARTING:
      if (btnInstall) btnInstall.disabled = true;
      if (btnPostpone) btnPostpone.disabled = true;
      closeBtns.forEach(btn => { if (btn) btn.disabled = true; });
      if (errContainer) errContainer.classList.add('hidden');
      if (statusMsg) {
        statusMsg.classList.remove('hidden', 'updater-status-error');
        statusMsg.textContent = 'Обновление успешно установлено! Перезапуск приложения...';
      }
      break;

    case UPDATER_STATES.ERROR:
      if (btnInstall) {
        btnInstall.disabled = false;
        btnInstall.textContent = 'Повторить';
        btnInstall.classList.add('btn-retry');
      }
      if (btnPostpone) btnPostpone.disabled = false;
      closeBtns.forEach(btn => { if (btn) btn.disabled = false; });
      if (progressContainer) progressContainer.classList.add('hidden');

      const classifiedMsg = details.classified?.message || details.message || (details.error ? String(details.error.message || details.error) : 'Ошибка при установке обновления. Попробуйте позже.');

      if (errContainer && errMsgEl) {
        errContainer.classList.remove('hidden');
        errMsgEl.textContent = classifiedMsg;
      }
      if (statusMsg) {
        statusMsg.classList.remove('hidden');
        statusMsg.classList.add('updater-status-error');
        statusMsg.textContent = classifiedMsg;
      }
      break;

    case UPDATER_STATES.IDLE:
    case UPDATER_STATES.UPDATE_AVAILABLE:
    default:
      if (btnInstall) btnInstall.disabled = false;
      if (btnPostpone) btnPostpone.disabled = false;
      closeBtns.forEach(btn => { if (btn) btn.disabled = false; });
      if (errContainer) errContainer.classList.add('hidden');
      if (statusMsg) statusMsg.classList.remove('updater-status-error');
      break;
  }
}

function formatBytes(bytes) {
  if (typeof Utils !== 'undefined' && typeof Utils.formatSize === 'function') {
    return Utils.formatSize(bytes);
  }
  if (!bytes || isNaN(bytes) || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  let s = bytes;
  while (s >= 1024 && i < units.length - 1) { s /= 1024; i++; }
  return `${s.toFixed(1)} ${units[i]}`;
}

function resetProgressUI() {
  downloadedBytes = 0;
  totalBytes = 0;
  const progressContainer = typeof document !== 'undefined' ? document.getElementById('updater-progress-container') : null;
  const barFill = typeof document !== 'undefined' ? document.getElementById('updater-progress-bar-fill') : null;
  const percentEl = typeof document !== 'undefined' ? document.getElementById('updater-progress-percentage') : null;
  const bytesEl = typeof document !== 'undefined' ? document.getElementById('updater-progress-bytes') : null;

  if (progressContainer) progressContainer.classList.add('hidden');
  if (barFill) barFill.style.width = '0%';
  if (percentEl) percentEl.textContent = '0%';
  if (bytesEl) bytesEl.textContent = '0 B / 0 B';
}

function handleProgressEvent(event) {
  if (!event || typeof event !== 'object') return null;

  const evtType = event.event;
  if (evtType === 'Started') {
    downloadedBytes = 0;
    totalBytes = Number(event.data?.contentLength) || 0;
    setUpdaterState(UPDATER_STATES.DOWNLOADING);
  } else if (evtType === 'Progress') {
    const chunk = Number(event.data?.chunkLength) || 0;
    downloadedBytes += Math.max(0, chunk);
  } else if (evtType === 'Finished') {
    if (totalBytes > 0) {
      downloadedBytes = totalBytes;
    }
    setUpdaterState(UPDATER_STATES.VERIFYING);
  }

  const percentage = totalBytes > 0
    ? Math.min(100, Math.max(0, Math.floor((downloadedBytes / totalBytes) * 100)))
    : 0;

  const barFill = typeof document !== 'undefined' ? document.getElementById('updater-progress-bar-fill') : null;
  const percentEl = typeof document !== 'undefined' ? document.getElementById('updater-progress-percentage') : null;
  const bytesEl = typeof document !== 'undefined' ? document.getElementById('updater-progress-bytes') : null;
  const progressContainer = typeof document !== 'undefined' ? document.getElementById('updater-progress-container') : null;

  if (progressContainer) progressContainer.classList.remove('hidden');
  if (barFill) barFill.style.width = `${percentage}%`;
  if (percentEl) percentEl.textContent = `${percentage}%`;
  if (bytesEl) {
    bytesEl.textContent = totalBytes > 0
      ? `${formatBytes(downloadedBytes)} / ${formatBytes(totalBytes)}`
      : formatBytes(downloadedBytes);
  }

  return {
    event: evtType,
    downloadedBytes,
    totalBytes,
    percentage,
    formattedDownloaded: formatBytes(downloadedBytes),
    formattedTotal: formatBytes(totalBytes)
  };
}

const UpdaterAPI = {
  /**
   * Checks for application updates against GitHub Releases via Tauri updater plugin.
   * @param {Object} [options] Options for checking updates (e.g. { isManual: boolean })
   * @returns {Promise<Object>} Structured result object
   */
  checkForUpdates: async (options = {}) => {
    const isManual = Boolean(options?.isManual);
    setUpdaterState(UPDATER_STATES.CHECKING);
    try {
      if (window.__TAURI__?.updater?.check) {
        const update = await window.__TAURI__.updater.check();
        if (update && update.available) {
          activeUpdateObject = update;
          setUpdaterState(UPDATER_STATES.UPDATE_AVAILABLE);
          return {
            success: true,
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
          setUpdaterState(UPDATER_STATES.UPDATE_AVAILABLE);
          const parsed = parseReleaseNotes(updateInfo);
          return { success: true, ...parsed };
        }
      }
      setUpdaterState(UPDATER_STATES.IDLE);
      return { success: true, available: false };
    } catch (err) {
      const classified = classifyError(err);
      setUpdaterState(UPDATER_STATES.ERROR, { error: err, classified });
      if (typeof Logger !== 'undefined') {
        Logger.error('Updater', 'Failed to check for updates', err);
      } else {
        console.error('Failed to check for updates:', err);
      }
      const toastFn = (typeof Utils !== 'undefined' && typeof Utils.toast === 'function')
        ? Utils.toast
        : (typeof window !== 'undefined' && typeof window.Utils !== 'undefined' && typeof window.Utils.toast === 'function')
          ? window.Utils.toast
          : null;

      if (isManual && toastFn) {
        toastFn(classified.message, 'error');
      }
      return {
        success: false,
        error: classified.code,
        message: classified.message
      };
    }
  },

  /**
   * Downloads and installs the pending update.
   * @param {Object} updateObj 
   * @param {Function} onProgress 
   * @returns {Promise<Object>} Structured result object { success: boolean, error?: string, message?: string }
   */
  installUpdate: async (updateObj, onProgress) => {
    const targetObj = updateObj || activeUpdateObject;
    setUpdaterState(UPDATER_STATES.DOWNLOADING);

    const progressWrapper = (event) => {
      const progressData = handleProgressEvent(event);
      if (typeof onProgress === 'function') {
        onProgress(event, progressData);
      }
    };

    try {
      if (targetObj && typeof targetObj.downloadAndInstall === 'function') {
        await targetObj.downloadAndInstall(progressWrapper);
        setUpdaterState(UPDATER_STATES.RESTARTING);
        return { success: true };
      } else if (window.__TAURI__?.core?.invoke) {
        await window.__TAURI__.core.invoke('plugin:updater|download_and_install');
        setUpdaterState(UPDATER_STATES.RESTARTING);
        return { success: true };
      }
    } catch (err) {
      const classified = classifyError(err);
      setUpdaterState(UPDATER_STATES.ERROR, { error: err, classified });
      if (typeof Logger !== 'undefined') {
        Logger.error('Updater', 'Failed to download and install update', err);
      } else {
        console.error('Failed to download and install update:', err);
      }
      return {
        success: false,
        error: classified.code,
        message: classified.message
      };
    }
    setUpdaterState(UPDATER_STATES.ERROR, { message: 'Объект обновления не найден.' });
    return {
      success: false,
      error: 'NO_UPDATE_OBJECT',
      message: 'Объект обновления не найден.'
    };
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
  const modal = typeof document !== 'undefined' ? document.getElementById('modal-updater') : null;
  if (!modal) return;

  resetProgressUI();

  const errContainer = typeof document !== 'undefined' ? document.getElementById('updater-error-container') : null;
  const errMsgEl = typeof document !== 'undefined' ? document.getElementById('updater-error-message') : null;
  const statusMsg = typeof document !== 'undefined' ? document.getElementById('updater-status-message') : null;

  if (errContainer) errContainer.classList.add('hidden');
  if (errMsgEl) errMsgEl.textContent = '';
  if (statusMsg) {
    statusMsg.classList.add('hidden');
    statusMsg.classList.remove('updater-status-error');
    statusMsg.textContent = '';
  }

  const btnInstall = typeof document !== 'undefined' ? document.getElementById('btn-updater-install') : null;
  if (btnInstall) {
    btnInstall.textContent = 'Обновить сейчас';
    btnInstall.classList.remove('btn-retry');
    btnInstall.disabled = false;
  }

  setUpdaterState(UPDATER_STATES.UPDATE_AVAILABLE);

  const versionTag = typeof document !== 'undefined' ? document.getElementById('updater-version-tag') : null;
  const releaseNotesEl = typeof document !== 'undefined' ? document.getElementById('updater-release-notes') : null;

  const parsed = parseReleaseNotes(updateInfo);

  if (versionTag) {
    versionTag.textContent = `Новая версия: ${parsed.version ? 'v' + parsed.version.replace(/^v/, '') : 'Доступно обновление'}`;
  }

  if (releaseNotesEl) {
    releaseNotesEl.innerHTML = renderMarkdown(parsed.body);
  }

  modal.classList.remove('hidden');
}

/**
 * Hides update modal and resets updater UI state.
 */
function hideUpdateModal() {
  const modal = typeof document !== 'undefined' ? document.getElementById('modal-updater') : null;
  if (modal) {
    modal.classList.add('hidden');
  }

  const errContainer = typeof document !== 'undefined' ? document.getElementById('updater-error-container') : null;
  const errMsgEl = typeof document !== 'undefined' ? document.getElementById('updater-error-message') : null;
  const statusMsg = typeof document !== 'undefined' ? document.getElementById('updater-status-message') : null;

  if (errContainer) {
    errContainer.classList.add('hidden');
  }
  if (errMsgEl) {
    errMsgEl.textContent = '';
  }
  if (statusMsg) {
    statusMsg.textContent = '';
    statusMsg.classList.add('hidden');
    statusMsg.classList.remove('updater-status-error');
  }

  const btnInstall = typeof document !== 'undefined' ? document.getElementById('btn-updater-install') : null;
  if (btnInstall) {
    btnInstall.textContent = 'Обновить сейчас';
    btnInstall.classList.remove('btn-retry');
    btnInstall.disabled = false;
  }

  const btnPostpone = typeof document !== 'undefined' ? document.getElementById('btn-updater-postpone') : null;
  if (btnPostpone) btnPostpone.disabled = false;

  const closeBtns = typeof document !== 'undefined' ? document.querySelectorAll('[data-close="modal-updater"]') : [];
  closeBtns.forEach(btn => { if (btn) btn.disabled = false; });

  resetProgressUI();
  setUpdaterState(UPDATER_STATES.IDLE);
}

/**
 * Initializes Updater UI button handlers for "Update Now" ("Обновить сейчас") and "Postpone" ("Отложить").
 */
function initUpdaterUI() {
  const btnInstall = typeof document !== 'undefined' ? document.getElementById('btn-updater-install') : null;
  const btnPostpone = typeof document !== 'undefined' ? document.getElementById('btn-updater-postpone') : null;
  const closeBtns = typeof document !== 'undefined' ? document.querySelectorAll('[data-close="modal-updater"]') : [];

  if (btnInstall) {
    btnInstall.addEventListener('click', async () => {
      if (currentUpdaterState === UPDATER_STATES.DOWNLOADING || currentUpdaterState === UPDATER_STATES.VERIFYING) {
        return;
      }
      setUpdaterState(UPDATER_STATES.DOWNLOADING);

      const res = await UpdaterAPI.installUpdate(activeUpdateObject, handleProgressEvent);
      if (res && res.success) {
        setUpdaterState(UPDATER_STATES.RESTARTING);
        setTimeout(async () => {
          const relaunched = await UpdaterAPI.relaunchApp();
          if (!relaunched) {
            hideUpdateModal();
          }
        }, 1500);
      }
    });
  }

  if (btnPostpone) {
    btnPostpone.addEventListener('click', () => {
      hideUpdateModal();
    });
  }

  closeBtns.forEach(btn => {
    if (btn) {
      btn.addEventListener('click', () => {
        hideUpdateModal();
      });
    }
  });

  if (typeof document !== 'undefined') {
    document.addEventListener('keydown', (evt) => {
      if (evt.key === 'Escape' || evt.code === 'Escape') {
        const modal = document.getElementById('modal-updater');
        if (modal && !modal.classList.contains('hidden')) {
          if (currentUpdaterState !== UPDATER_STATES.DOWNLOADING && currentUpdaterState !== UPDATER_STATES.VERIFYING) {
            hideUpdateModal();
          }
        }
      }
    });
  }
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
    UPDATER_STATES,
    getUpdaterState,
    setUpdaterState,
    handleProgressEvent,
    resetProgressUI,
    formatBytes,
    isNewerVersion,
    renderMarkdown,
    parseReleaseNotes,
    classifyError,
    UpdaterAPI,
    showUpdateModal,
    hideUpdateModal,
    initUpdaterUI
  };
}

if (typeof window !== 'undefined') {
  window.UPDATER_STATES = UPDATER_STATES;
  window.getUpdaterState = getUpdaterState;
  window.setUpdaterState = setUpdaterState;
  window.handleProgressEvent = handleProgressEvent;
  window.resetProgressUI = resetProgressUI;
  window.formatBytes = formatBytes;
  window.classifyError = classifyError;
  window.UpdaterAPI = UpdaterAPI;
  window.isNewerVersion = isNewerVersion;
  window.renderMarkdown = renderMarkdown;
  window.parseReleaseNotes = parseReleaseNotes;
  window.showUpdateModal = showUpdateModal;
  window.hideUpdateModal = hideUpdateModal;
  window.initUpdaterUI = initUpdaterUI;
}


