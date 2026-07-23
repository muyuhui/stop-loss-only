$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$env:PYTHONDONTWRITEBYTECODE = '1'
$projectTemp = Join-Path $root '.tmp\verify'
New-Item -ItemType Directory -Path $projectTemp -Force | Out-Null
$env:TEMP = $projectTemp
$env:TMP = $projectTemp
$env:STOP_LOSS_TEMP_DIR = $projectTemp
Push-Location (Join-Path $root 'backend')
try { & python -m pytest -p no:cacheprovider -q; if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' } } finally { Pop-Location }
Push-Location (Join-Path $root 'frontend')
try {
    & npm test; if ($LASTEXITCODE -ne 0) { throw 'Frontend tests failed.' }
    & npm run build; if ($LASTEXITCODE -ne 0) { throw 'Frontend build or bundle budget failed.' }
} finally { Pop-Location }
& python (Join-Path $root 'scripts\smoke.py'); if ($LASTEXITCODE -ne 0) { throw 'End-to-end smoke test failed.' }
& openspec validate --changes --strict --no-interactive; if ($LASTEXITCODE -ne 0) { throw 'OpenSpec validation failed.' }
Write-Host 'All quality gates passed. Live-provider checks are opt-in and excluded from hermetic gates.' -ForegroundColor Green
