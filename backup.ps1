param([string]$Output = (Join-Path $PSScriptRoot 'backend\backups'))
Push-Location (Join-Path $PSScriptRoot 'backend')
try { & python db_admin.py backup --output $Output; exit $LASTEXITCODE } finally { Pop-Location }
