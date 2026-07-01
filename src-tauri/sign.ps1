param([string]$target)
if (-not $target) { Write-Error "Target file is required"; exit 1 }

# Find signtool.exe in standard Windows SDK locations
$signtool = (Resolve-Path "C:\Program Files (x86)\Windows Kits\10\bin\*\x64\signtool.exe" -ErrorAction SilentlyContinue | Select-Object -Last 1).Path
if (-not $signtool) {
    # Fallback to PATH
    $signtool = Get-Command signtool -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
}

if (-not $signtool) {
    Write-Warning "signtool.exe not found. Skipping signing of $target."
    exit 0
}

$pfx = Join-Path $PSScriptRoot "wiphoto-self-signed.pfx"
if (-not (Test-Path $pfx)) {
    Write-Warning "wiphoto-self-signed.pfx not found at $pfx. Skipping signing of $target."
    exit 0
}

Write-Host "Signing $target using $signtool..."
& $signtool sign /f $pfx /p "WiphotoPass123!" /tr http://timestamp.digicert.com /td sha256 /fd sha256 $target
if ($LASTEXITCODE -ne 0) {
    Write-Error "Signing failed for $target."
    exit $LASTEXITCODE
}
Write-Host "Successfully signed $target"
