<#
.SYNOPSIS
Automated generation and setup of Tauri OTA keys.

.DESCRIPTION
This script eliminates human error during Tauri update configuration.
It automatically:
1. Generates new OTA keys without a password.
2. Securely uploads the private key to GitHub Secrets via gh CLI (no manual copy/paste!).
3. Updates tauri.conf.json with the new public key.
4. Enables updater artifacts creation (createUpdaterArtifacts: true).
5. Commits the changes.

.NOTES
Make sure you are logged into GitHub CLI (gh auth login) before running.
#>

Write-Host "Starting automated Tauri OTA keys setup..." -ForegroundColor Cyan

# 1. Check for GitHub CLI
if (-not (Get-Command "gh" -ErrorAction SilentlyContinue)) {
    Write-Host "Error: GitHub CLI (gh) is not installed." -ForegroundColor Red
    Write-Host "Please install it from https://cli.github.com/ or run 'winget install --id GitHub.cli'" -ForegroundColor Yellow
    exit 1
}

# 2. Check GitHub CLI auth status
$ghAuthStatus = gh auth status 2>&1
if ($ghAuthStatus -match "You are not logged into any GitHub hosts") {
    Write-Host "Error: You are not logged into GitHub CLI." -ForegroundColor Red
    Write-Host "Please run 'gh auth login' and follow the instructions." -ForegroundColor Yellow
    exit 1
}

# 3. Generate Tauri Keys
Write-Host "Generating new OTA keys..." -ForegroundColor Cyan
if (Test-Path ".tauri.key") { Remove-Item ".tauri.key" -Force }
if (Test-Path ".tauri.key.pub") { Remove-Item ".tauri.key.pub" -Force }

Write-Host "WARNING: The tool will ask for a password next." -ForegroundColor Yellow
Write-Host "Just press ENTER TWICE to leave it empty (recommended for CI)!" -ForegroundColor Green
Start-Sleep -Seconds 3

npx tauri signer generate -w .tauri.key

if (-not (Test-Path ".tauri.key")) {
    Write-Host "Error: Keys were not generated. Aborting." -ForegroundColor Red
    exit 1
}

# 4. Upload key to GitHub Secrets
Write-Host "Securely uploading private key to GitHub Secrets..." -ForegroundColor Cyan
$privateKey = Get-Content ".tauri.key" -Raw
gh secret set TAURI_SIGNING_PRIVATE_KEY --body "$privateKey"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Failed to upload secret to GitHub. Make sure you have repository write access." -ForegroundColor Red
    exit 1
}
Write-Host "Private key successfully uploaded to GitHub Secrets!" -ForegroundColor Green

# Remove the private key locally for security
Remove-Item ".tauri.key" -Force
Write-Host "Local private key deleted for security." -ForegroundColor Gray

# 5. Update tauri.conf.json
Write-Host "Updating Tauri configuration..." -ForegroundColor Cyan
$pubKey = Get-Content ".tauri.key.pub" -Raw
$pubKeyLines = $pubKey -split "`n"
$base64PubKey = ""
foreach ($line in $pubKeyLines) {
    if (-not $line.StartsWith("untrusted comment") -and $line.Trim() -ne "") {
        $base64PubKey = $line.Trim()
        break
    }
}

if ($base64PubKey -eq "") {
    Write-Host "Error: Could not read public key from .tauri.key.pub" -ForegroundColor Red
    exit 1
}

$confPath = "src-tauri/tauri.conf.json"
$confContent = Get-Content $confPath -Raw
$confJson = $confContent | ConvertFrom-Json -Depth 10

if ($null -eq $confJson.plugins.updater) {
    Write-Host "Error: plugins.updater block not found in tauri.conf.json." -ForegroundColor Red
    exit 1
}
$confJson.plugins.updater.pubkey = $base64PubKey

if ($null -ne $confJson.bundle) {
    $confJson.bundle.createUpdaterArtifacts = $true
}

$newConfContent = $confJson | ConvertTo-Json -Depth 10
Set-Content -Path $confPath -Value $newConfContent

Write-Host "tauri.conf.json updated successfully!" -ForegroundColor Green

# 6. Commit changes
Write-Host "Creating a commit with the new settings..." -ForegroundColor Cyan
git add $confPath
git commit -m "chore(ota): rotate OTA keys and re-enable updater artifacts"

Write-Host "DONE! Auto-updates infrastructure is fully configured." -ForegroundColor Green
Write-Host "Now you can run 'git push --tags' or make a new release, and it will work perfectly!" -ForegroundColor Cyan
