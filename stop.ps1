param(
    [ValidateRange(1, 65535)]
    [int]$BackendPort = 8001,
    [ValidateRange(1, 65535)]
    [int]$FrontendPort = 5173
)

$root = $PSScriptRoot
$logDir = Join-Path $root "logs"

function Stop-RecordedProcess([string]$PidFile) {
    $path = Join-Path $root $PidFile
    if (-not (Test-Path $path)) { return }

    $processId = (Get-Content $path -Raw).Trim()
    if ($processId -match '^\d+$' -and (Get-Process -Id $processId -ErrorAction SilentlyContinue)) {
        Write-Host "  Stopping recorded process (PID: $processId)" -ForegroundColor Yellow
        taskkill /F /T /PID $processId 2>$null | Out-Null
    }
}

function Stop-PortListener([int]$Port) {
    $listeners = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    foreach ($listener in $listeners) {
        Write-Host "  Stopping port $Port (PID: $($listener.OwningProcess))" -ForegroundColor Yellow
        taskkill /F /T /PID $listener.OwningProcess 2>$null | Out-Null
    }
}

function Test-PortListening([int]$Port) {
    return $null -ne (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Stop Loss Only - stopping..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Stop-RecordedProcess ".backend.pid"
Stop-RecordedProcess ".frontend.pid"
Stop-PortListener $BackendPort
Stop-PortListener $FrontendPort

Remove-Item (Join-Path $root ".backend.pid"), (Join-Path $root ".frontend.pid") -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1
Remove-Item (Join-Path $logDir "*.log") -Force -ErrorAction SilentlyContinue

$remainingPorts = @($BackendPort, $FrontendPort) |
    Select-Object -Unique |
    Where-Object { Test-PortListening $_ }
if ($remainingPorts.Count -gt 0) {
    Write-Host "`n  Ports still listening: $($remainingPorts -join ', ')" -ForegroundColor Red
    exit 1
}

Write-Host "`n  Services stopped and logs cleared." -ForegroundColor Green
