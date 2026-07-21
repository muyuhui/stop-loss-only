param([ValidateRange(1, 65535)][int]$BackendPort = 8001)
$env:STOP_LOSS_SCHEDULER_ENABLED = '0'
Write-Host 'Development reload mode: scheduled monitoring is disabled.' -ForegroundColor Yellow
Push-Location (Join-Path $PSScriptRoot 'backend')
try { & python -m uvicorn main:app --reload --host 127.0.0.1 --port $BackendPort } finally { Pop-Location }
