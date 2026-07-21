param([switch]$Dev)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Push-Location (Join-Path $root 'backend')
try {
    $requirements = if ($Dev) { 'requirements-dev.txt' } else { 'requirements.txt' }
    & python -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
} finally { Pop-Location }
Push-Location (Join-Path $root 'frontend')
try {
    & npm ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
} finally { Pop-Location }
Write-Host 'Dependencies installed.' -ForegroundColor Green
