param(
    [ValidateRange(1, 65535)][int]$BackendPort = 8001,
    [ValidateRange(1, 65535)][int]$FrontendPort = 5173
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
. (Join-Path $root 'scripts\process_identity.ps1')

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

function Test-ProjectProcessCommand([string]$Kind, [int]$ProcessId, [int]$Port) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
    $command = [string]$process.CommandLine
    if (-not $command) { return $false }

    $portPattern = "--port(?:=|\s+)$Port(?:\s|`"|$)"
    if ($command -notmatch $portPattern) { return $false }

    if ($Kind -eq 'backend') {
        return $command -match '(?i)\buvicorn(?:\.exe)?\b.*\bmain:app\b'
    }

    $rootPattern = [regex]::Escape($root)
    return ($command -match '(?i)(?:\b|[/\\])vite(?:\.js|\.mjs|\.cmd|\.exe)?(?:\b|[/\\])') -and
        ($command -match $rootPattern)
}

function Test-ProjectService([string]$Kind, [int]$Port) {
    try {
        if ($Kind -eq 'backend') {
            $openApi = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/openapi.json" -TimeoutSec 2
            $pathNames = @($openApi.paths.PSObject.Properties.Name)
            return ($pathNames -contains '/api/holdings') -and
                ($pathNames -contains '/api/prices/refresh')
        }

        $page = Invoke-WebRequest -Uri "http://127.0.0.1:$Port" -UseBasicParsing -TimeoutSec 2
        return ($page.StatusCode -eq 200) -and ($page.Content -match '/@vite/client')
    } catch {
        return $false
    }
}

function Wait-PortReleased([int]$Port) {
    for ($attempt = 1; $attempt -le 20; $attempt++) {
        $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
        if (-not $listener) { return $true }
        Start-Sleep -Milliseconds 100
    }
    return $false
}

function Stop-OrphanedProjectListener([string]$Kind, [int]$Port) {
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
    if ($listeners.Count -eq 0) { return $true }

    $ownerPids = @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)
    if ($ownerPids.Count -ne 1) {
        Write-Warning "Port $Port could not be verified as this project's $Kind service; no listener was terminated."
        return $false
    }

    $ownerPid = [int]$ownerPids[0]
    $commandConfirmed = Test-ProjectProcessCommand $Kind $ownerPid $Port
    $serviceConfirmed = Test-ProjectService $Kind $Port
    if (-not ($commandConfirmed -and $serviceConfirmed)) {
        Write-Warning "PID $ownerPid on port $Port could not be verified as this project's $Kind service; it was not terminated."
        return $false
    }

    Write-Host "Recovering orphaned $Kind service on port $Port (PID $ownerPid)." -ForegroundColor Yellow
    Stop-VerifiedTree $ownerPid
    if (-not (Wait-PortReleased $Port)) {
        Write-Warning "Verified $Kind service PID $ownerPid was stopped, but port $Port is still in use."
        return $false
    }
    return $true
}

function Stop-OwnedProcess([string]$RecordName) {
    $recordPath = Join-Path $root $RecordName
    if (-not (Test-Path -LiteralPath $recordPath)) { return }
    $record = Get-Content -LiteralPath $recordPath -Encoding UTF8 -Raw | ConvertFrom-Json
    $process = Get-Process -Id $record.pid -ErrorAction SilentlyContinue
    if (-not $process) { Remove-Item -LiteralPath $recordPath -Force; return }
    $startMatches = Test-RecordedProcessStart -RecordedStart $record.started_at -ActualStart $process.StartTime
    if ($record.root -ne $root -or -not $startMatches) {
        Write-Warning "PID $($record.pid) ownership check failed; it was not terminated."
        return
    }
    $portListener = Get-NetTCPConnection -State Listen -LocalPort $record.port -ErrorAction SilentlyContinue | Select-Object -First 1
    $listener = $portListener | Where-Object { $_.OwningProcess -eq $record.pid }
    $command = (Get-CimInstance Win32_Process -Filter "ProcessId=$($record.pid)" -ErrorAction SilentlyContinue).CommandLine
    # The root/start-time check above is the durable ownership proof. Command
    # line and listener inspection can be denied on locked-down Windows hosts,
    # so they are supporting diagnostics rather than a second hard gate.
    # Descendants are selected by verified parentage, so npm/node helpers are
    # cleaned up without touching unrelated listeners.
    $serviceConfirmed = $false
    try {
        if ($record.kind -eq 'backend') {
            $openApi = Invoke-RestMethod -Uri "http://127.0.0.1:$($record.port)/openapi.json" -TimeoutSec 2
            $pathNames = @($openApi.paths.PSObject.Properties.Name)
            $serviceConfirmed = ($pathNames -contains '/api/holdings') -and ($pathNames -contains '/api/prices/refresh')
        } else {
            $page = Invoke-WebRequest -Uri "http://127.0.0.1:$($record.port)" -UseBasicParsing -TimeoutSec 2
            $serviceConfirmed = $page.StatusCode -eq 200 -and $page.Content -match '/@vite/client'
        }
    } catch { }
    Stop-VerifiedTree ([int]$record.pid)
    if ($serviceConfirmed -and $portListener -and $portListener.OwningProcess -ne $record.pid) {
        Stop-Process -Id $portListener.OwningProcess -Force -ErrorAction SilentlyContinue
    }
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
$backendStopped = Stop-OrphanedProjectListener 'backend' $BackendPort
$frontendStopped = Stop-OrphanedProjectListener 'frontend' $FrontendPort
if (-not $backendStopped -or -not $frontendStopped) {
    throw 'One or more configured ports are still occupied by processes that were not safely verified.'
}
Write-Host 'Verified project processes stopped; logs and unrelated processes were preserved.' -ForegroundColor Green
