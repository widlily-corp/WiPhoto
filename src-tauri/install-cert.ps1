# Run as administrator to import the certificate
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Warning "This script must be run as Administrator to trust the certificate."
    Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

$certPath = Join-Path $PSScriptRoot "wiphoto-self-signed.pfx"
if (-not (Test-Path $certPath)) {
    Write-Error "wiphoto-self-signed.pfx not found at $certPath"
    exit 1
}

Write-Host "Trusting WiPhoto Self-Signed Certificate..."
$password = ConvertTo-SecureString "WiphotoPass123!" -AsPlainText -Force
Import-PfxCertificate -FilePath $certPath -CertStoreLocation "Cert:\LocalMachine\Root" -Password $password
Import-PfxCertificate -FilePath $certPath -CertStoreLocation "Cert:\LocalMachine\TrustedPublisher" -Password $password

Write-Host "`nSuccess! The certificate is now trusted on this machine. You can run the WiPhoto installer without SmartScreen warnings." -ForegroundColor Green
Read-Host "Press Enter to exit..."
