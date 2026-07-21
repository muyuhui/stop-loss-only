param(
    [ValidateRange(1, 65535)][int]$BackendPort = 8001,
    [ValidateRange(1, 65535)][int]$FrontendPort = 5173,
    [switch]$Restart
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$logDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Assert-PortAvailable([int]$Port) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($listener) {
        $owner = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
        throw "Port $Port is owned by PID $($listener.OwningProcess) ($($owner.ProcessName)); it was not terminated."
    }
}
function Save-ProcessRecord($Process, [string]$Kind, [int]$Port, [string]$Path) {
    $record = @{ pid = $Process.Id; kind = $Kind; port = $Port; root = $root; started_at = $Process.StartTime.ToUniversalTime().ToString('o') }
    $record | ConvertTo-Json | Set-Content -LiteralPath $Path -Encoding UTF8
}

if ($Restart) {
    & (Join-Path $root 'stop.ps1') -BackendPort $BackendPort -FrontendPort $FrontendPort
    if (-not $?) { throw 'Failed to stop the previous project services.' }
}

& python -c "import fastapi, sqlalchemy, apscheduler, akshare" 2>$null
if ($LASTEXITCODE -ne 0) { throw 'Backend dependencies are missing. Run .\setup.ps1 first.' }
if (-not (Test-Path -LiteralPath (Join-Path $root 'frontend\node_modules'))) { throw 'Frontend dependencies are missing. Run .\setup.ps1 first.' }
Assert-PortAvailable $BackendPort
Assert-PortAvailable $FrontendPort

Push-Location (Join-Path $root 'backend')
try {
    & python db_admin.py upgrade
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
} finally { Pop-Location }

$backend = Start-Process -WindowStyle Hidden -FilePath 'python' -ArgumentList @('-m','uvicorn','main:app','--host','127.0.0.1','--port',"$BackendPort",'--workers','1') -WorkingDirectory (Join-Path $root 'backend') -RedirectStandardOutput (Join-Path $logDir 'backend.log') -RedirectStandardError (Join-Path $logDir 'backend.err.log') -PassThru
Save-ProcessRecord $backend 'backend' $BackendPort (Join-Path $root '.backend.process.json')
$npm = (Get-Command npm.cmd -ErrorAction Stop).Source
$frontend = Start-Process -WindowStyle Hidden -FilePath $npm -ArgumentList @('run','dev','--','--host','127.0.0.1','--port',"$FrontendPort",'--strictPort') -WorkingDirectory (Join-Path $root 'frontend') -RedirectStandardOutput (Join-Path $logDir 'frontend.log') -RedirectStandardError (Join-Path $logDir 'frontend.err.log') -PassThru
Save-ProcessRecord $frontend 'frontend' $FrontendPort (Join-Path $root '.frontend.process.json')

$ready = $false
for ($attempt = 1; $attempt -le 20; $attempt++) {
    try {
        $status = Invoke-RestMethod -Uri "http://127.0.0.1:$BackendPort/api/health/ready" -TimeoutSec 2
        if ($status.status -eq 'ok' -and (Get-NetTCPConnection -State Listen -LocalPort $FrontendPort -ErrorAction SilentlyContinue)) { $ready = $true; break }
    } catch { }
    Start-Sleep -Seconds 1
}
if (-not $ready) {
    & (Join-Path $root 'stop.ps1')
    throw "Services did not become ready. Check $logDir"
}
Write-Host "Backend: http://127.0.0.1:$BackendPort  Frontend: http://127.0.0.1:$FrontendPort" -ForegroundColor Green
