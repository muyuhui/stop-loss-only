param([Parameter(Mandatory=$true)][string]$Backup, [Parameter(Mandatory=$true)][string]$Manifest)
if ((Test-Path (Join-Path $PSScriptRoot '.backend.process.json'))) { throw 'Stop the backend before restoring a database.' }
Push-Location (Join-Path $PSScriptRoot 'backend')
try { & python db_admin.py restore $Backup $Manifest; exit $LASTEXITCODE } finally { Pop-Location }
