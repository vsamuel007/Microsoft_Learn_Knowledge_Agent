# START_DEMO.ps1 - One-command startup for Teams channel demo
# Location: src/teams/START_DEMO.ps1
# Usage: .\START_DEMO.ps1

$ErrorActionPreference = "Stop"
$TeamsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $TeamsDir)
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$CloudflaredTemp = "$env:TEMP\cloudflared.exe"

function Get-CloudflaredPath {
    if (Test-Path $CloudflaredTemp) {
        return $CloudflaredTemp
    }

    $cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    return $null
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Teams Bot Channel Demo Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $VenvPython)) {
    throw "Virtual environment python not found at $VenvPython"
}

$CloudflaredExe = Get-CloudflaredPath
if (-not $CloudflaredExe) {
    Write-Host "cloudflared not found." -ForegroundColor Red
    Write-Host "Install it or place cloudflared.exe at: $CloudflaredTemp" -ForegroundColor Yellow
    Write-Host "Then re-run .\\START_DEMO.ps1" -ForegroundColor Yellow
    exit 1
}

# Step 1: Start Teams bot host
Write-Host "[1/3] Starting Teams bot host on port 3978..." -ForegroundColor Yellow
Start-Process -FilePath $VenvPython `
    -ArgumentList (Join-Path $TeamsDir "app.py") `
    -WorkingDirectory $TeamsDir `
    -WindowStyle Normal `
    -PassThru | Out-Null

Start-Sleep -Seconds 3

# Step 2: Start Cloudflare quick tunnel
Write-Host "[2/3] Starting Cloudflare tunnel..." -ForegroundColor Yellow
Write-Host "      Forwarding http://127.0.0.1:3978 to public HTTPS..." -ForegroundColor Gray
Start-Process -FilePath $CloudflaredExe `
    -ArgumentList "tunnel", "--url", "http://127.0.0.1:3978", "--no-autoupdate" `
    -WindowStyle Normal `
    -PassThru | Out-Null

Start-Sleep -Seconds 5

# Step 3: Display next steps
Write-Host "[3/3] Startup complete" -ForegroundColor Yellow
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "NEXT STEPS" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "1. In the cloudflared window, copy the public URL." -ForegroundColor White
Write-Host "   Example: https://example-tunnel.trycloudflare.com" -ForegroundColor Gray
Write-Host ""
Write-Host "2. In Azure Bot -> Settings -> Configuration, set Messaging endpoint to:" -ForegroundColor White
Write-Host "   https://YOUR-TUNNEL-URL/api/messages" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Keep both windows running and test in Teams channel:" -ForegroundColor White
Write-Host "   hello" -ForegroundColor Gray
Write-Host "   my skills" -ForegroundColor Gray
Write-Host "   create learning path for Azure Administrator" -ForegroundColor Gray
Write-Host ""
Write-Host "4. Optional local health check:" -ForegroundColor White
Write-Host "   Invoke-RestMethod http://localhost:3978/healthz" -ForegroundColor Gray
Write-Host ""
Write-Host "RUNNING SERVICES:" -ForegroundColor Cyan
Write-Host "  [*] Teams Bot Host   : http://127.0.0.1:3978" -ForegroundColor Green
Write-Host "  [*] Cloudflare Tunnel: see tunnel window for public URL" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C in the spawned windows to stop." -ForegroundColor Yellow