param(
    [ValidateRange(1, 65535)][int]$BackendPort = 8001,
    [ValidateRange(1, 65535)][int]$FrontendPort = 5173
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

function Get-ProcessDescendants([int]$RootPid) {
    $descendants = @()
    $pending = @($RootPid)
    while ($pending.Count -gt 0) {
        $parent = $pending[0]
        $pending = @($pending | Select-Object -Skip 1)
        $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$parent" -ErrorAction SilentlyContinue)
        foreach ($child in $children) {
            $descendants += [int]$child.ProcessId
            $pending += [int]$child.ProcessId
        }
    }
    return @($descendants)
}

function Stop-VerifiedTree([int]$RootPid) {
    $descendants = @(Get-ProcessDescendants $RootPid)
    foreach ($childId in @($descendants | Sort-Object -Descending)) {
        Stop-Process -Id $childId -Force -ErrorAction SilentlyContinue
    }
    Stop-Process -Id $RootPid -Force -ErrorAction SilentlyContinue
}

function Stop-OwnedProcess([string]$RecordName) {
    $recordPath = Join-Path $root $RecordName
    if (-not (Test-Path -LiteralPath $recordPath)) { return }
    $record = Get-Content -LiteralPath $recordPath -Encoding UTF8 -Raw | ConvertFrom-Json
    $process = Get-Process -Id $record.pid -ErrorAction SilentlyContinue
    if (-not $process) { Remove-Item -LiteralPath $recordPath -Force; return }
    $actualStart = $process.StartTime.ToUniversalTime().ToString('o')
    if ($record.root -ne $root -or $actualStart -ne $record.started_at) {
        Write-Warning "PID $($record.pid) ownership check failed; it was not terminated."
        return
    }
    $listener = Get-NetTCPConnection -State Listen -LocalPort $record.port -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -eq $record.pid }
    $command = (Get-CimInstance Win32_Process -Filter "ProcessId=$($record.pid)" -ErrorAction SilentlyContinue).CommandLine
    if (-not $listener -and $command -notmatch [regex]::Escape([string]$record.port)) {
        Write-Warning "PID $($record.pid) command/port check failed; it was not terminated."
        return
    }
    # Descendants are selected by verified parentage, so npm/node helpers are
    # cleaned up without touching unrelated listeners.
    Stop-VerifiedTree ([int]$record.pid)
    Remove-Item -LiteralPath $recordPath -Force
}

function Stop-LegacyRecordedProcess([string]$PidFile, [string]$Kind, [int]$Port) {
    $path = Join-Path $root $PidFile
    if (-not (Test-Path -LiteralPath $path)) { return }
    $rawPid = (Get-Content -LiteralPath $path -Raw).Trim()
    if ($rawPid -notmatch '^\d+$') {
        Write-Warning "Legacy PID file $PidFile is invalid; it was not trusted."
        return
    }
    $legacyPid = [int]$rawPid
    $process = Get-Process -Id $legacyPid -ErrorAction SilentlyContinue
    if (-not $process) {
        Remove-Item -LiteralPath $path -Force
        return
    }
    $cim = Get-CimInstance Win32_Process -Filter "ProcessId=$legacyPid" -ErrorAction SilentlyContinue
    $command = [string]$cim.CommandLine
    $serviceMarker = if ($Kind -eq 'backend') { 'uvicorn' } else { 'npm' }
    $rootMatch = $command -match [regex]::Escape($root)
    $markerMatch = $command -match $serviceMarker
    $portListener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
    $ownsPort = $null -ne ($portListener | Where-Object { $_.OwningProcess -eq $legacyPid })
    $serviceConfirmed = $false
    if ($Kind -eq 'backend' -and $portListener) {
        try {
            $openApi = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/openapi.json" -TimeoutSec 2
            $pathNames = @($openApi.paths.PSObject.Properties.Name)
            $serviceConfirmed = ($pathNames -contains '/api/holdings') -and ($pathNames -contains '/api/prices/refresh')
        } catch { }
    }
    if (-not (($rootMatch -and $markerMatch) -or $ownsPort -or $serviceConfirmed)) {
        Write-Warning "Legacy PID $legacyPid could not be verified as this project's $Kind service; it was not terminated."
        return
    }
    Stop-VerifiedTree $legacyPid
    if ($serviceConfirmed -and $portListener -and $portListener.OwningProcess -ne $legacyPid) {
        Stop-Process -Id $portListener.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $path -Force
}

Stop-OwnedProcess '.backend.process.json'
Stop-OwnedProcess '.frontend.process.json'
Stop-LegacyRecordedProcess '.backend.pid' 'backend' $BackendPort
Stop-LegacyRecordedProcess '.frontend.pid' 'frontend' $FrontendPort
Write-Host 'Verified project processes stopped; logs and unrelated processes were preserved.' -ForegroundColor Green
