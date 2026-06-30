// ═══ Centralized Logger Module ═══

const Logger = (() => {
  const Levels = {
    TRACE: 0,
    DEBUG: 1,
    INFO: 2,
    WARN: 3,
    ERROR: 4,
  };

  let currentLevel = Levels.INFO;

  // Check if we are in debug mode
  try {
    if (localStorage.getItem('wiphoto-debug') === 'true') {
      currentLevel = Levels.DEBUG;
    }
  } catch (e) {
    // Ignore localStorage errors
  }

  function setLevel(levelName) {
    const lvl = Levels[levelName.toUpperCase()];
    if (lvl !== undefined) {
      currentLevel = lvl;
    }
  }

  function getLevelName(lvl) {
    return Object.keys(Levels).find(key => Levels[key] === lvl) || 'INFO';
  }

  function formatMessage(level, module, message, err) {
    const timestamp = new Date().toISOString();
    let errStr = '';
    if (err) {
      if (err instanceof Error) {
        errStr = `\nStack: ${err.stack}`;
      } else {
        errStr = `\nDetails: ${JSON.stringify(err)}`;
      }
    }
    return `[${timestamp}] [${getLevelName(level)}] [${module}] ${message}${errStr}`;
  }

  function log(level, module, message, err) {
    if (level < currentLevel) return;

    const formatted = formatMessage(level, module, message, err);

    // Call native log if available
    if (window.API && typeof window.API.logJs === 'function') {
      window.API.logJs(formatted);
    } else {
      if (level >= Levels.ERROR) {
        console.error(formatted);
      } else if (level === Levels.WARN) {
        console.warn(formatted);
      } else {
        console.log(formatted);
      }
    }
  }

  return {
    setLevel,
    trace: (module, message) => log(Levels.TRACE, module, message),
    debug: (module, message) => log(Levels.DEBUG, module, message),
    info: (module, message) => log(Levels.INFO, module, message),
    warn: (module, message, err) => log(Levels.WARN, module, message, err),
    error: (module, message, err) => log(Levels.ERROR, module, message, err),
    isDebug: () => currentLevel <= Levels.DEBUG
  };
})();

window.Logger = Logger;
