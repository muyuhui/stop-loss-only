param(
    [ValidateRange(1, 65535)]
    [int]$BackendPort = 8001,
    [ValidateRange(1, 65535)]
    [int]$FrontendPort = 5173,
    [switch]$Restart
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$logDir = Join-Path $root "logs"

function Test-PortListening([int]$Port) {
    return $null -ne (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

function Stop-PortListener([int]$Port) {
    $listeners = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    foreach ($listener in $listeners) {
        Write-Host "  Releasing port $Port (PID: $($listener.OwningProcess))" -ForegroundColor Yellow
        taskkill /F /T /PID $listener.OwningProcess 2>$null | Out-Null
    }
}

function Install-Dependencies {
    Write-Host "  Installing backend dependencies..." -ForegroundColor Cyan
    Push-Location (Join-Path $root "backend")
    try {
        & python -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw "Backend dependency installation failed (exit code $LASTEXITCODE)." }
    } finally {
        Pop-Location
    }

    Write-Host "  Installing frontend dependencies..." -ForegroundColor Cyan
    Push-Location (Join-Path $root "frontend")
    try {
        & npm install
        if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed (exit code $LASTEXITCODE)." }
    } finally {
        Pop-Location
    }
}

function Show-StartupLog([string]$Name) {
    $path = Join-Path $logDir "$Name.log"
    if (Test-Path $path) {
        Write-Host "`n  $Name log (last 40 lines):" -ForegroundColor Yellow
        Get-Content $path -Tail 40
    }
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Stop Loss Only - starting..." -ForegroundColor Cyan
Write-Host "  Backend: $BackendPort  Frontend: $FrontendPort  Logs: $logDir" -ForegroundColor Cyan
if ($Restart) { Write-Host "  Mode: restart" -ForegroundColor Yellow }
Write-Host "========================================" -ForegroundColor Cyan

try {
    if ($Restart) {
        Write-Host "  Stopping previous services and clearing logs..." -ForegroundColor Yellow
        & (Join-Path $root "stop.ps1") -BackendPort $BackendPort -FrontendPort $FrontendPort
        if (-not $?) { throw "Failed to stop previous services." }
    }

    Install-Dependencies

    Stop-PortListener $BackendPort
    Stop-PortListener $FrontendPort

    $backendLog = Join-Path $logDir "backend.log"
    $frontendLog = Join-Path $logDir "frontend.log"

    Write-Host "  Starting backend..." -ForegroundColor Cyan
    $backendCommand = 'set PYTHONIOENCODING=utf-8 && python -u -m uvicorn main:app --reload --port {0} --host 0.0.0.0 >> "{1}" 2>&1' -f $BackendPort, $backendLog
    $backend = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $backendCommand -WorkingDirectory (Join-Path $root "backend") -WindowStyle Hidden -PassThru
    $backend.Id | Set-Content -Path (Join-Path $root ".backend.pid") -Encoding ASCII

    Write-Host "  Starting frontend..." -ForegroundColor Cyan
    $frontendCommand = 'set "VITE_API_PROXY_TARGET=http://localhost:{0}" && npm run dev -- --host 127.0.0.1 --port {1} --strictPort >> "{2}" 2>&1' -f $BackendPort, $FrontendPort, $frontendLog
    $frontend = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $frontendCommand -WorkingDirectory (Join-Path $root "frontend") -WindowStyle Hidden -PassThru
    $frontend.Id | Set-Content -Path (Join-Path $root ".frontend.pid") -Encoding ASCII

    Write-Host "  Waiting for services..." -ForegroundColor Gray
    $ready = $false
    for ($attempt = 1; $attempt -le 15; $attempt++) {
        if ((Test-PortListening $BackendPort) -and (Test-PortListening $FrontendPort)) {
            $ready = $true
            break
        }
        Start-Sleep -Seconds 1
    }

    if (-not $ready) {
        Write-Host "`nStartup failed: backend or frontend did not listen within 15 seconds." -ForegroundColor Red
        Show-StartupLog "backend"
        Show-StartupLog "frontend"
        exit 1
    }

    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  Startup complete!" -ForegroundColor Green
    Write-Host "  Backend : http://localhost:$BackendPort" -ForegroundColor White
    Write-Host "  Frontend: http://localhost:$FrontendPort" -ForegroundColor White
    Write-Host "  API     : http://localhost:$BackendPort/docs" -ForegroundColor White
    Write-Host "  Stop: .\stop.ps1  Restart: .\start.ps1 -Restart" -ForegroundColor White
    Write-Host "========================================" -ForegroundColor Cyan
} catch {
    Write-Host "`nStartup failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
