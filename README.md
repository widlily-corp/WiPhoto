# WiPhoto (v4.0.0)

[![WiPhoto CI](https://github.com/widlily-corp/WiPhoto/actions/workflows/ci.yml/badge.svg)](https://github.com/widlily-corp/WiPhoto/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-4.0.0-blue.svg)](package.json)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)](src-tauri/tauri.conf.json)

Профессиональный, высокопроизводительный менеджер и редактор фотографий для десктопа. Построен на базе **Tauri v2**, **Rust** (высокопроизводительный многопоточный бэкенд) и **Vanilla JS / CSS** (фронтенд с ультра-минималистичной дизайн-системой Refined Minimal).

В версии **v4.0.0** полностью переработан интерфейс, внедрена контекстная панель действий, добавлено гибридное тестирование и настроен кроссплатформенный CI/CD пайплайн.

---

## 🚀 Быстрый старт

### Требования к окружению
* **Node.js** (LTS v18+)
* **Rust & Cargo** (1.75+)
* Системные библиотеки для Tauri (подробнее см. на [tauri.app](https://tauri.app/start/prerequisites/))

### Установка зависимостей
Запустите в корневой директории проекта:
```bash
npm install
```

### Запуск в режиме разработки (Hot Reload)
```bash
npm run dev
# или
npx tauri dev
```

### Запуск тестов (CI / Локально)
```bash
# Тесты фронтенда (Node.js built-in runner)
npm run test

# Тесты бэкенда (Rust Cargo test)
cargo test --manifest-path src-tauri/Cargo.toml
```

### Сборка финального дистрибутива
```bash
npx tauri build
```

---

## 📂 Структура проекта

```text
wiphoto/
├── .github/workflows/      # CI/CD автоматизация (GitHub Actions)
│   └── ci.yml              # Единый пайплайн тестирования и сборки
├── src/                    # Фронтенд-приложение (HTML, CSS, JS)
│   ├── index.html          # Главная точка входа разметки (включает сетку и панели)
│   ├── js/                 # Модули логики (IIFE-компоненты на window)
│   │   ├── utils.js        # Утилиты форматирования, DOM-генераторы
│   │   ├── utils.test.cjs  # [NEW] Тесты утилит на Node.js test runner
│   │   ├── virtualgrid.js  # Сверхбыстрая виртуальная сетка (Virtual Scroll)
│   │   ├── gallery.js      # Менеджер галереи и состояния выделения
│   │   └── ...             # Дополнительные скрипты (editor, maps, settings)
│   └── styles/             # Стилизация (дизайн-система HSL)
│       ├── variables.css   # Палитра темных нейтралей, анимации, границы
│       ├── main.css        # Разметка 3-х колоночной сетки и экранов
│       └── components.css  # Стили кнопок, модалок и контекстной панели
├── src-tauri/              # Бэкенд на Rust
│   ├── src/
│   │   ├── commands/       # Tauri-команды (сканирование, EXIF, XMP, экспорт)
│   │   ├── models/         # Модели данных
│   │   │   └── image_info.rs # Модели + [NEW] Модули юнит-тестов бэкенда
│   │   └── lib.rs          # Регистрация Tauri-команд и инициализация
│   ├── Cargo.toml          # Зависимости Rust
│   └── tauri.conf.json     # Конфигурация Tauri v2
└── package.json            # Зависимости Node.js и скрипты
```

---

## 🛠️ Архитектура и Ключевые Оптимизации

### 1. Виртуальная Сетка с DOM Diffing (Virtual Grid)
Для обработки библиотек объемом 10,000+ медиафайлов без утечек памяти и зависаний DOM используется кастомный алгоритм [virtualgrid.js](file:///c:/Users/Widlily/Documents/projects/wiphoto/src/js/virtualgrid.js):
* Отрисовывается только видимое окно просмотра с небольшим буфером.
* При скролле карточки не пересоздаются с нуля (`innerHTML = ''`), а точечно добавляются/удаляются/перемещаются в зависимости от их индекса и координат.

### 2. Контекстная Панель Действий (Contextual Action Bar)
Для разгрузки интерфейса внедрена контекстная панель в нижней части экрана. Она плавно скользит вверх только при выборе одной или нескольких фотографий, концентрируя операции:
* **Флаги:** Pick / Reject
* **Рейтинг:** Выбор 1-5 звезд
* **Действия:** Переименование, экспорт, удаление

### 3. Гибридная Архитектура Тестирования (AAA Pattern)
Каждый тест написан в строгой структуре **Arrange-Act-Assert**:
* **Backend:** Юнит-тесты Rust (`cargo test`) покрывают методы разбора расширений, конструкторы моделей и конфигурацию настроек.
* **Frontend:** Использование встроенного в Node.js 20+ быстрого тест-раннера (`node --test`). JS-код тестируется в изолированной виртуальной машине (`node:vm`), что исключает конфликты импорта CommonJS/ESM в Node и гарантирует независимость браузерного кода.

### 4. Автоматизированный CI/CD пайплайн (GitHub Actions)
В репозитории настроен рабочий процесс `.github/workflows/ci.yml`:
1. На каждый Push и Pull Request в ветках `main` и `beta-rust+tuari` запускаются тесты JS и Rust.
2. При публикации тегов `v*` (например, `v4.0.0`) автоматически собираются дистрибутивы под Windows (`.msi`) и Linux (`.deb` / `.AppImage`), после чего формируется готовый черновик релиза в GitHub.

---

## 🎨 Стандарты разработки и кодстайл

###Conventional Commits
История изменений Git должна быть кристально чистой:
* `feat(ui): ...` — внедрение новой визуальной функциональности
* `fix(scanner): ...` — исправление багов
* `test(backend): ...` — добавление или изменение тестовых сценариев
* `refactor(layout): ...` — рефакторинг стилей и верстки

### Чистота кода
* **Плоские условия (Early Returns):** Избегайте вложенных блоков `if-else`. Выходите из функций как можно раньше.
* **Анимации:** Анимируйте только `transform` и `opacity` (рендеринг на GPU).
* **Никаких `any` или скрытых ошибок:** Пишите строгие типы, всегда логгируйте перехваченные исключения через `Logger.error(...)`.

---

## 🔑 Подпись установщика для Windows (Code Signing)

Для того чтобы Windows SmartScreen не блокировал установщик (`.msi`) с предупреждением «Неизвестный издатель», бинарные файлы необходимо подписать цифровым сертификатом разработчика.

Рекомендуется использовать один из двух вариантов в CI/CD пайплайне:

### Вариант 1. Использование PFX-сертификата (Локального или через секреты)
1. Экспортируйте ваш сертификат в формате `.pfx` и преобразуйте его в Base64. Сохраните его в Secrets репозитория как `SIGNING_CERT_BASE64`, а пароль как `SIGNING_CERT_PASSWORD`.
2. Добавьте конфигурацию `signCommand` в блок `bundle` вашего [tauri.conf.json](file:///c:/Users/Widlily/Documents/projects/wiphoto/src-tauri/tauri.conf.json):
   ```json
   "bundle": {
     "active": true,
     "targets": "all",
     "windows": {
       "signCommand": "signtool sign /f certificate.pfx /p %SIGNING_CERT_PASSWORD% /tr http://timestamp.digicert.com /td sha256 /fd sha256 $1"
     }
   }
   ```
3. В `.github/workflows/ci.yml` перед шагом сборки Tauri добавьте декодирование сертификата:
   ```yaml
   - name: Import Certificate
     shell: pwsh
     run: |
       $certBytes = [System.Convert]::FromBase64String("${{ secrets.SIGNING_CERT_BASE64 }}")
       [System.IO.File]::WriteAllBytes("src-tauri/certificate.pfx", $certBytes)
   ```

### Вариант 2. Azure Trusted Signing (Рекомендуемый для корпоративной сборки)
1. Настройте службу Azure Trusted Signing в вашей панели Azure.
2. Пропишите команду `signCommand` в [tauri.conf.json](file:///c:/Users/Widlily/Documents/projects/wiphoto/src-tauri/tauri.conf.json) с использованием утилиты `dotnet sign`:
   ```json
   "bundle": {
     "windows": {
       "signCommand": "dotnet sign --sha256 --timestamp http://timestamp.digicert.com --azure-key-vault-url %AZURE_VAULT_URL% --azure-client-id %AZURE_CLIENT_ID% --azure-tenant-id %AZURE_TENANT_ID% --azure-client-secret %AZURE_CLIENT_SECRET% --azure-certificate-name %AZURE_CERT_NAME% $1"
     }
   }
   ```
3. Передайте секретные переменные в шаге сборки в `.github/workflows/ci.yml` из Secrets вашего репозитория.

---

## 💖 Поддержка проекта

Если вам нравится WiPhoto и вы хотите поддержать его развитие, вот реквизиты:
* **[Укажите вашу ссылку или реквизиты для поддержки (YoMoney, Boosty, СБП и т.д.)]**


