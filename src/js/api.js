// ═══ Tauri IPC API Wrapper ═══

const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;
const { open: openDialog, save: saveDialog, message: messageDialog, ask: askDialog } = window.__TAURI__.dialog;

const API = {
  // ─── Scanner ───
  scanFolder: (path, recursive) => invoke('scan_folder', { path, recursive }),
  countFiles: (path, recursive) => invoke('count_files', { path, recursive }),
  logJs: (message) => invoke('log_js', { message }),

  // ─── Thumbnails ───
  getThumbnail: (path) => invoke('get_thumbnail', { path }),
  loadFullImage: (path, maxSize) => invoke('load_full_image', { path, maxSize: maxSize || null }),
  clearThumbnailCache: () => invoke('clear_thumbnail_cache'),

  // ─── Metadata ───
  readExif: (path) => invoke('read_exif', { path }),
  updatePhotoMetadata: (path, rating, colorLabel, flagStatus, tags) =>
    invoke('update_photo_metadata', { path, rating: rating ?? null, colorLabel: colorLabel ?? null, flagStatus: flagStatus ?? null, tags: tags ?? null }),
  getGeotaggedPhotos: () => invoke('get_geotagged_photos'),

  // ─── File Operations ───
  deleteFiles: (paths) => invoke('delete_files', { paths }),
  copyFiles: (paths, destDir) => invoke('copy_files', { paths, destDir }),
  moveFiles: (paths, destDir) => invoke('move_files', { paths, destDir }),
  deletePermanently: (paths) => invoke('delete_permanently', { paths }),
  batchRename: (renameMap) => invoke('batch_rename', { renameMap }),
  getFolderTree: (rootPath) => invoke('get_folder_tree', { rootPath }),
  listTrash: () => invoke('list_trash'),
  restoreFromTrash: (filename) => invoke('restore_from_trash', { filename }),
  emptyTrash: () => invoke('empty_trash'),
  openInSystemPlayer: (path) => invoke('open_in_system_player', { path }),

  // ─── Duplicates ───
  findDuplicates: (paths, method, threshold) => invoke('find_duplicates', { paths, method, threshold }),
  getDuplicateStats: (groups) => invoke('get_duplicate_stats', { groups }),
  computePhash: (path) => invoke('compute_phash', { path }),

  // ─── Editor ───
  applyEdit: (path, operations, maxPreviewSize) => invoke('apply_edit', { path, operations, maxPreviewSize: maxPreviewSize || null }),
  saveEdited: (path, operations, outputPath, quality) => invoke('save_edited', { path, operations, outputPath: outputPath || null, quality: quality || null }),
  cropImage: (path, x, y, width, height) => invoke('crop_image', { path, x, y, width, height }),
  saveCroppedEditedImage: (path, cropRect, operations, outputPath, quality) =>
    invoke('save_cropped_edited_image', { path, cropRect: cropRect || null, operations, outputPath: outputPath || null, quality: quality || null }),
  getHistogram: (path) => invoke('get_histogram', { path }),
  getColorPalette: (path, count) => invoke('get_color_palette', { path, count: count || null }),

  // ─── Export ───
  exportFiles: (paths, destDir, format, quality, maxWidth, maxHeight, watermarkText) =>
    invoke('export_files', { paths, destDir, format, quality, maxWidth: maxWidth || null, maxHeight: maxHeight || null, watermarkText: watermarkText || null }),

  // ─── Settings ───
  loadSettings: () => invoke('load_settings'),
  saveSettings: (settings) => invoke('save_settings', { settings }),
  getAppVersion: () => invoke('get_app_version'),
  getAppInfo: () => invoke('get_app_info'),

  // ─── XMP ───
  readXmpSidecar: (path) => invoke('read_xmp_sidecar', { path }),
  writeXmpSidecar: (path, rating, colorLabel, flagStatus, tags, historyEntry) =>
    invoke('write_xmp_sidecar', { path, rating, colorLabel, flagStatus, tags, historyEntry: historyEntry || null }),

  // ─── Search ───
  searchClipSemantic: (query, limit) => invoke('search_clip_semantic', { query, limit: limit || 100 }),

  // ─── Events ───
  onScanProgress: (callback) => listen('scan-progress', (event) => callback(event.payload)),
  onDupProgress: (callback) => listen('dup-progress', (event) => callback(event.payload)),
  onScanFinished: (callback) => listen('scan-finished', (event) => callback(event.payload)),
  onImageScanned: (callback) => listen('image-scanned', (event) => callback(event.payload)),
  onFileDrop: (callback) => listen('tauri://drag-drop', (event) => callback(event.payload)),

  // ─── Dialogs ───
  openFolderDialog: () => openDialog({ directory: true, multiple: false, title: 'Выберите папку с фотографиями' }),
  openSaveDialog: (defaultPath) => saveDialog({ defaultPath, filters: [{ name: 'Images', extensions: ['jpg', 'jpeg', 'png', 'tiff', 'webp', 'bmp'] }] }),
  showMessage: (msg, title) => messageDialog(msg, { title: title || 'WiPhoto', kind: 'info' }),
  askConfirm: (msg, title) => askDialog(msg, { title: title || 'WiPhoto', kind: 'warning' }),
};

window.API = API;
