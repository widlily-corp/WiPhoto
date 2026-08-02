# Original User Request

## 2026-07-30T13:30:00Z

<USER_REQUEST>
Implement version 5.0.0 of WiPhoto, an advanced desktop photo manager and editor built with Tauri v2 (Rust) and Vanilla JS/CSS. Implement six major features: Smart Albums (local CLIP embeddings for semantic search), XMP Sidecar Sync, Geo-Map View (Leaflet + OpenStreetMap via Supercluster), Zero-Copy Architecture (tauri:// protocol), UI Refactoring (Refined Minimal design system, Command Palette), and OTA Updates (`tauri-plugin-updater`). After implementation, build, commit, and push the `v5.0.0` tag to trigger the GitHub Actions release workflow.

Working directory: `c:\Users\Widlily\Documents\projects\wiphoto`
Integrity mode: development

## Requirements

### R1. Интеллектуальный Семантический Поиск
Интегрировать локальную легковесную мультимодальную модель (например, CLIP). Обеспечить возможность текстового поиска на естественном языке (например, "собака на пляже") полностью оффлайн, без обращений к облачным API.

### R2. Неразрушающее Редактирование (XMP Sidecar)
Реализовать двустороннюю синхронизацию изменений (экспозиция, кроп, цвет) в `.xmp` файлы. Формат должен быть совместим со стандартными XMP-профилями для обеспечения переносимости.

### R3. Кластеризация на Карте (Leaflet)
Извлекать GPS-координаты из EXIF. Использовать Leaflet и OpenStreetMap для отображения тысяч фотографий на карте. Применить библиотеку Supercluster для обеспечения плавной работы без лагов при изменении масштаба (clustering).

### R4. Zero-Copy Architecture
Отказаться от передачи Base64-строк из Rust в JS. Использовать кастомный протокол Tauri (`tauri://`) для прямой загрузки изображений в теги `<img src="tauri://localhost/path">`.

### R5. Рефакторинг UI под "Refined Minimal"
Реализовать редизайн интерфейса: асимметричные панели, монохромная типографика (Inter / JetBrains Mono для метаданных), строгие hairline-разделители, и GPU-анимации (`transform`/`opacity`). Исключить использование `box-shadow` для выделения элементов. Добавить Command Palette (Ctrl+K).

### R6. Встроенное Автообновление
Интегрировать `tauri-plugin-updater` для проверки новых версий через GitHub Releases. При наличии обновления показывать модальное окно с Release Notes (срендеренными из Markdown) и кнопками «Обновить сейчас» / «Отложить».

### R7. Релизный Цикл
Зафиксировать изменения атомарными коммитами (в соответствии с Conventional Commits). Создать и запушить тег `v5.0.0` в удаленный репозиторий, чтобы сработал существующий GitHub Actions пайплайн (CI/CD).

## Acceptance Criteria

### Функциональность
- [ ] Поиск по произвольному текстовому запросу корректно находит релевантные фото, при этом сетевой трафик (к внешним API) отсутствует.
- [ ] При редактировании экспозиции/цвета создается валидный `.xmp` файл рядом с оригиналом. 
- [ ] Карта на базе Leaflet отображает кластеры фото, которые распадаются при зуме, без лагов при 1000+ элементов.
- [ ] В инспекторе элементов браузера Tauri фото загружаются через протокол `tauri://...`, а не как Base64-строки.
- [ ] Дизайн интерфейса строго соответствует правилам "Refined Minimal" (вместо теней используются hairline, скругления не более 6px). Command Palette открывается по сочетанию `Ctrl+K`.
- [ ] Код автообновления использует API `tauri-plugin-updater` и корректно рендерит Markdown Release Notes в модальном окне.
- [ ] Проект успешно собирается (`npm run build` / `cargo build`), все тесты проходят (`cargo test`, `npm run test`).
- [ ] В локальном Git есть коммиты с изменениями, и тег `v5.0.0` запушен в `origin`.
</USER_REQUEST>

## 2026-08-02T09:45:00Z

<USER_REQUEST>
You are the Project Orchestrator for WiPhoto. Your working directory is c:\Users\Widlily\Documents\projects\wiphoto\.agents\orchestrator.
The original user request is located at c:\Users\Widlily\Documents\projects\wiphoto\.agents\ORIGINAL_REQUEST.md.
Project workspace: c:\Users\Widlily\Documents\projects\wiphoto.

Your goals:
1. Fix thumbnail display issue (ARW/JPG) and perform a deep audit of the frontend and Rust backend.
2. Optimize GitHub Actions pipeline for fast OTA updates across Windows, macOS, and Linux.
3. Verify OTA update mechanism implementation in Tauri.
4. Prepare for and execute Release 5.0 on GitHub.

Follow standard teamwork orchestration protocols, maintain progress in .agents/orchestrator/progress.md, decompose tasks into milestones, dispatch specialists, and report completion to the sentinel when all acceptance criteria are met.
</USER_REQUEST>
