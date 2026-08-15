# Test Infrastructure Documentation (WiPhoto v5.1.4)

## 1. Overview & Test Philosophy
WiPhoto использует двухуровневую автоматизированную систему тестирования (Frontend + Backend), спроектированную по строгим стандартам надежности, скорости и изоляции:
* **AAA-Pattern (Arrange — Act — Assert):** Каждый тестовый сценарий изолированно подготавливает данные, выполняет ровно одно действие и валидирует наблюдаемые контракты без побочных эффектов.
* **Hermetic Execution:** Нулевая зависимость от внешних сетевых сервисов. Все сетевые операции, ONNX-модели и Tauri IPC мокируются в изолированных песочницах (`node:vm` для JS, `tempfile` и in-memory структуры для Rust).
* **Adversarial & Stress Hardening:** Наличие специализированных стресс-сьютов на 10,000+ элементов, 500-цикловые перезапуски, поврежденные бинарные файлы и обрывы соединений.

---

## 2. Frontend Test Architecture (Node.js Test Runner)

### 2.1 Движок и окружение
- **Test Runner**: Встроенный высокопроизводительный раннер Node.js (`node --test`).
- **Assertion Engine**: `node:assert/strict`.
- **Изолированная песочница**: `node:vm` для создания чистого контекста выполнения ES5/ES6 модулей без необходимости тяжелых браузерных эмуляторов.
- **Mock DOM & Event Engine**: Легковесная модель DOM (Window, Document, CustomEvent, Element, classList, style) с эмуляцией очередей событий и асинхронных таймеров.

### 2.2 Структура тестовых сюит фронтенда (`src/js/*.test.cjs`)

| Файл теста | Назначение и охват | Количество тестов |
|---|---|---|
| `updater_e2e.test.cjs` | 4-уровневый E2E сьют OTA-обновлений: прогресс-бар, стриминг байт, обработка сетевых сбоев, восстановление | 24 |
| `updater_m2_challenger_stress.test.cjs` | Стресс-тест модального окна OTA: 500 циклов открытия/ошибки/закрытия, поведение клавиши ESC в разных состояниях | 8 |
| `updater.test.cjs` | Модульные тесты парсера версий, Markdown-рендерера заметок к релизу, форматирования размеров | 18 |
| `virtualgrid_stress.test.cjs` | Стресс-тест виртуальной сетки: 50,000 элементов, поддержание <60 активных DOM-узлов, 50 циклов загрузки без утечек | 3 |
| `spatial_stress.test.cjs` | Бенчмарк гео-пространственной кластеризации Leaflet/Supercluster на тысячах GPS-координат | 6 |
| `compare.test.cjs` | Стейт-менеджер режима сравнения Split View, синхронизация зума/панорамирования | 6 |
| `gpu-worker.test.cjs` | Проверка протокола сообщений Web Worker и интерфейса WebGPU WGSL шейдеров | 4 |
| `m1_challenger_stress.test.cjs` | Стресс-тестирование дедупликации, сопоставления лиц и тяжелых массивов | 10 |
| `tier1_tier2_features.test.cjs` | Базовые сценарии и граничные условия ключевых модулей фронтенда | 18 |
| `tier3_cross_features.test.cjs` | Кросс-модульное взаимодействие (Command Palette + Updater + Gallery) | 6 |
| `tier4_e2e_scenarios.test.cjs` | Комплексные пользовательские сценарии от импорта до экспорта | 4 |
| `utils.test.cjs` | Модульные тесты утилит (formatSize, starsHtml, getExtension, getFilename, assetUrl) | 10 |
| **ИТОГО ФРОНТЕНД** | **12 тестовых файлов** | **117 тестов** |

---

## 3. Backend Test Architecture (Rust Cargo Test)

### 3.1 Окружение бэкенда
- **Раннер**: `cargo test --manifest-path src-tauri/Cargo.toml`.
- **Изоляция**: Создание уникальных временных папок `tempfile::TempDir` для каждого теста.
- **Многопоточность**: Использование `rayon` и `tokio` для проверки конкурентности базы данных SQLite и кэша миниатюр.

### 3.2 Структура тестовых сюит бэкенда (`src-tauri/tests/` + `src-tauri/src/`)

| Модуль / Сьют | Файл | Описание проверок | Тестов |
|---|---|---|---|
| **Unit Tests (Core & Commands)** | `src-tauri/src/lib.rs`, `db.rs`, `onnx.rs`, `commands/*` | Кастомный asset-протокол, Range-запросы, SQLite r2d2 пул, ONNX косинусное сходство, XMP sidecar, pHash | 39 |
| **Backend Stress Suite** | `tests/backend_stress_suite.rs` | Многопоточный скан папок, конкурентность кэша миниатюр, 10,000 элементов в BK-Tree, стресс БД | 4 |
| **E2E Integration Suite** | `tests/e2e_v500_tests.rs` | Проверка регистрации плагинов Tauri, OTA-конфигурации и 4-уровневых сценариев | 5 |
| **R1 ML & Challenger** | `tests/r1_challenger_stress.rs` | Оффлайн-инференс, устойчивость pHash, конкурентное индексирование лиц | 5 |
| **R1 ONNX Mock Execution** | `tests/r1_onnx_test.rs` | Загрузка и исполнение оффлайн dummy ONNX графа без внешних зависимостей | 1 |
| **R1 Vector Edge Cases** | `tests/r1_vector_edge_cases_stress.rs` | Ортогональные/противоположные векторы, нулевые векторы, пустые пути | 5 |
| **R4 Batch Export Suite** | `tests/r4_batch_export_test.rs` | Конвертация PNG/AVIF/JPEG, масштабирование, пайплайн удаления EXIF | 2 |
| **R4 Challenger Stress** | `tests/r4_challenger_stress_test.rs` | Обработка поврежденных JXL, неквадратные пропорции, масштабирование вверх/вниз | 5 |
| **R4 EXIF Stripping Stress** | `tests/r4_exif_stripping_challenger_stress.rs` | Удаление EXIF из не-JPEG, усеченных файлов, файлов с множественными APP1 маркерами | 5 |
| **XMP Roundtrip Stress** | `tests/xmp_roundtrip_stress.rs` | Экранирование XML-спецсимволов, большие XMP-пакеты, 1000 последовательных итераций обновления | 3 |
| **ИТОГО БЭКЕНД** | **10 тестовых таргетов** | **Полный охват ядра и команд Rust** | **74 теста** |

---

## 4. 4-Уровневая методология тестирования (4-Tier Methodology)

1. **Tier 1: Feature Coverage (Покрытие функций)**: Проверка позитивных сценариев работы всех компонентов (Happy Path).
2. **Tier 2: Boundary & Edge Cases (Граничные условия)**: Проверка нулевых размеров, деления на ноль, некорректных байтов, поврежденных заголовков и переполнений.
3. **Tier 3: Cross-Feature Interactions (Кросс-модульная интеграция)**: Проверка совместной работы компонентов при возникновении исключений и асинхронных прерываний.
4. **Tier 4: Real-World Scenarios (Реальные пользовательские сценарии)**: Сквозное моделирование полных жизненных циклов приложения.

---

## 5. Запуск тестов

```bash
# 1. Запуск всех тестов фронтенда:
npm test

# 2. Запуск отдельного тестового файла фронтенда:
node --test src/js/updater_e2e.test.cjs
node --test src/js/virtualgrid_stress.test.cjs

# 3. Запуск линтера (ESLint 9):
npm run lint

# 4. Запуск всех тестов бэкенда Rust:
cargo test --manifest-path src-tauri/Cargo.toml

# 5. Запуск конкретного интеграционного сьюта Rust:
cargo test --manifest-path src-tauri/Cargo.toml --test xmp_roundtrip_stress
```
