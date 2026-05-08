# START_DEMO.ps1 - One-command startup for LearningPath agent portal demo
# Location: src/agents/learningpath/START_DEMO.ps1
# Usage: .\START_DEMO.ps1

$ErrorActionPreference = "Stop"
$LearningPathDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $LearningPathDir))
$CloudflaredExe = "$env:TEMP\cloudflared.exe"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "LearningPath Agent Portal Demo Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Activate venv
Write-Host "[1/3] Activating Python virtual environment..." -ForegroundColor Yellow
& (Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1")

# Step 2: Start local MCP server
Write-Host "[2/3] Starting local MCP server on port 8002..." -ForegroundColor Yellow
Write-Host "      Transport: streamable-http (HTTP polling, tunnel-compatible)" -ForegroundColor Gray
Start-Process -FilePath "python.exe" `
    -ArgumentList (Join-Path $LearningPathDir "server.py"), "--transport", "streamable-http", "--host", "127.0.0.1", "--port", "8002", "--public" `
    -WorkingDirectory $LearningPathDir `
    -WindowStyle Normal `
    -PassThru | Out-Null

Start-Sleep -Seconds 3

# Step 3: Start cloudflare tunnel
Write-Host "[3/3] Starting Cloudflare tunnel..." -ForegroundColor Yellow
Write-Host "      Forwarding http://127.0.0.1:8002 to public HTTPS..." -ForegroundColor Gray
Start-Process -FilePath $CloudflaredExe `
    -ArgumentList "tunnel", "--url", "http://127.0.0.1:8002", "--no-autoupdate" `
    -WindowStyle Normal `
    -PassThru | Out-Null

Start-Sleep -Seconds 5

# Step 4: Display next steps
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Startup complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Copy the Cloudflare public URL from the tunnel window that just opened" -ForegroundColor White
Write-Host "   Example: https://example-tunnel.trycloudflare.com" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Update the env file with the new tunnel URL:" -ForegroundColor White
Write-Host "   File: src/agents/.env" -ForegroundColor Gray
Write-Host "   Set:  LEARNING_PATH_MCP_SERVER_URL=https://YOUR-TUNNEL-URL/mcp" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Re-register the portal agent (run from project root with venv active):" -ForegroundColor White
Write-Host "   python src/agents/learningpath/agent.py" -ForegroundColor Gray
Write-Host ""
Write-Host "4. Open Foundry portal and test LearningPathAgent playground." -ForegroundColor White
Write-Host "   Query: Create a learning path for user-123 targeting Azure Administrator with a moderate pace and 5 hours per week." -ForegroundColor Gray
Write-Host ""
Write-Host "RUNNING SERVICES:" -ForegroundColor Cyan
Write-Host "  [*] Local MCP Server : http://127.0.0.1:8002" -ForegroundColor Green
Write-Host "  [*] Cloudflare Tunnel : see tunnel window for public URL" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C in either window to stop." -ForegroundColor Yellow
Write-Host ""
