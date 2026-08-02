<#
.SYNOPSIS
Автоматическая генерация и настройка ключей OTA для Tauri.

.DESCRIPTION
Этот скрипт устраняет человеческий фактор при настройке обновлений Tauri.
Он автоматически:
1. Генерирует новые ключи OTA без пароля.
2. Безопасно загружает приватный ключ напрямую в GitHub Secrets через утилиту gh (без ручного копирования!).
3. Обновляет tauri.conf.json новым публичным ключом.
4. Включает создание артефактов для автообновлений (createUpdaterArtifacts: true).
5. Создает коммит с изменениями конфигурации.

.NOTES
Перед запуском убедитесь, что вы залогинены в GitHub CLI (gh auth login).
#>

Write-Host "🚀 Начинаем автоматическую настройку OTA обновлений Tauri..." -ForegroundColor Cyan

# 1. Проверка наличия GitHub CLI
if (-not (Get-Command "gh" -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Ошибка: GitHub CLI (gh) не установлен." -ForegroundColor Red
    Write-Host "Пожалуйста, установите его с сайта https://cli.github.com/ или через 'winget install --id GitHub.cli'" -ForegroundColor Yellow
    exit 1
}

# 2. Проверка авторизации в GitHub CLI
$ghAuthStatus = gh auth status 2>&1
if ($ghAuthStatus -match "You are not logged into any GitHub hosts") {
    Write-Host "❌ Ошибка: Вы не авторизованы в GitHub CLI." -ForegroundColor Red
    Write-Host "Пожалуйста, выполните команду 'gh auth login' и следуйте инструкциям." -ForegroundColor Yellow
    exit 1
}

# 3. Генерация ключей Tauri
Write-Host "🔑 Генерируем новые ключи OTA..." -ForegroundColor Cyan
if (Test-Path ".tauri.key") { Remove-Item ".tauri.key" -Force }
if (Test-Path ".tauri.key.pub") { Remove-Item ".tauri.key.pub" -Force }

# Используем npx tauri signer generate (работает интерактивно, поэтому просто скажем пользователю нажать Enter)
Write-Host "⚠️ ВНИМАНИЕ: Сейчас утилита попросит ввести пароль." -ForegroundColor Yellow
Write-Host "Просто нажмите ENTER два раза, чтобы оставить ключ без пароля!" -ForegroundColor Green
Start-Sleep -Seconds 3

npx tauri signer generate -w .tauri.key

if (-not (Test-Path ".tauri.key")) {
    Write-Host "❌ Ошибка: Ключи не были сгенерированы. Прерываем работу." -ForegroundColor Red
    exit 1
}

# 4. Загрузка ключа в GitHub Secrets
Write-Host "☁️ Безопасная загрузка приватного ключа в GitHub Secrets..." -ForegroundColor Cyan
# Читаем ключ как сырой текст, чтобы избежать проблем с переносами строк
gh secret set TAURI_SIGNING_PRIVATE_KEY < .tauri.key
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Ошибка: Не удалось загрузить секрет в GitHub. Убедитесь, что у вас есть права на запись секретов в репозиторий." -ForegroundColor Red
    exit 1
}
Write-Host "✅ Приватный ключ успешно загружен в GitHub Secrets!" -ForegroundColor Green

# Очищаем приватный ключ локально ради безопасности
Remove-Item ".tauri.key" -Force
Write-Host "🗑️ Локальный приватный ключ удален для безопасности." -ForegroundColor Gray

# 5. Обновление tauri.conf.json
Write-Host "📝 Обновление конфигурации Tauri..." -ForegroundColor Cyan
$pubKey = Get-Content ".tauri.key.pub" -Raw
# Извлекаем только сам ключ (обычно вторая строка)
$pubKeyLines = $pubKey -split "`n"
$base64PubKey = ""
foreach ($line in $pubKeyLines) {
    if (-not $line.StartsWith("untrusted comment") -and $line.Trim() -ne "") {
        $base64PubKey = $line.Trim()
        break
    }
}

if ($base64PubKey -eq "") {
    Write-Host "❌ Ошибка: Не удалось прочитать публичный ключ из .tauri.key.pub" -ForegroundColor Red
    exit 1
}

$confPath = "src-tauri/tauri.conf.json"
$confContent = Get-Content $confPath -Raw
$confJson = $confContent | ConvertFrom-Json -Depth 10

# Устанавливаем новый публичный ключ
if ($null -eq $confJson.plugins.updater) {
    Write-Host "❌ Ошибка: Блок plugins.updater не найден в tauri.conf.json." -ForegroundColor Red
    exit 1
}
$confJson.plugins.updater.pubkey = $base64PubKey

# Включаем создание обновлений
if ($null -ne $confJson.bundle) {
    $confJson.bundle.createUpdaterArtifacts = $true
}

$newConfContent = $confJson | ConvertTo-Json -Depth 10
Set-Content -Path $confPath -Value $newConfContent

Write-Host "✅ tauri.conf.json обновлен!" -ForegroundColor Green

# 6. Фиксация изменений в Git
Write-Host "📦 Создание коммита с новыми настройками..." -ForegroundColor Cyan
git add $confPath
git commit -m "chore(ota): rotate OTA keys and re-enable updater artifacts"

Write-Host "🎉 ГОТОВО! Инфраструктура автообновлений полностью настроена." -ForegroundColor Green
Write-Host "Теперь просто выполните 'git push --tags' (или сделайте релиз), все пройдет автоматически без ошибок!" -ForegroundColor Cyan
