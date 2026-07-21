param(
    [int]$BackendPort = 8001,
    [int]$FrontendPort = 5173,
    [switch]$Restart
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  止损不止盈 - 启动中..." -ForegroundColor Cyan
Write-Host "  后端: $BackendPort  前端: $FrontendPort" -ForegroundColor Cyan
if ($Restart) { Write-Host "  模式: 重启（先关闭旧进程）" -ForegroundColor Yellow }
Write-Host "========================================" -ForegroundColor Cyan

# ---- 重启模式：先停旧进程 ----
if ($Restart) {
    Write-Host "`n[0/4] 停止旧进程..." -ForegroundColor Yellow
    & "$PSScriptRoot\stop.ps1" -BackendPort $BackendPort -FrontendPort $FrontendPort
    Start-Sleep 2
}

# ---- 检查并处理端口占用 ----
Write-Host "`n[1/4] 检查端口..." -ForegroundColor Yellow

function Stop-PortProcess($port) {
    $lines = netstat -ano | Select-String ":$port " | Select-String "LISTENING"
    if (-not $lines) { return $false }
    foreach ($line in $lines) {
        $parts = $line.ToString().Trim() -split '\s+'
        $procId = $parts[-1]
        if ($procId -and $procId -match '^\d+$') {
            Write-Host "  终止端口 $port (PID: $procId)..." -ForegroundColor Yellow
            taskkill /F /T /PID $procId 2>&1 | Out-Null
        }
    }
    return $true
}

$backendBlocked = Stop-PortProcess $BackendPort
$frontendBlocked = Stop-PortProcess $FrontendPort
if ($backendBlocked -or $frontendBlocked) { Start-Sleep 2 }

# ---- 检查后端依赖 ----
Write-Host "`n[2/4] 检查后端依赖..." -ForegroundColor Yellow
$backendOk = $true
$requiredModules = @("fastapi", "uvicorn", "sqlalchemy", "pydantic", "apscheduler")
foreach ($mod in $requiredModules) {
    python -c "import $mod" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { $backendOk = $false; break }
}
if (-not $backendOk) {
    Write-Host "  安装缺失的后端依赖..." -ForegroundColor Yellow
    Push-Location "$root\backend"
    pip install -r requirements.txt -q 2>&1 | Out-Null
    Pop-Location
    Write-Host "  后端依赖安装完成" -ForegroundColor Green
} else {
    Write-Host "  后端依赖 OK" -ForegroundColor Green
}

# ---- 检查前端依赖 ----
Write-Host "`n[3/4] 检查前端依赖..." -ForegroundColor Yellow
if (Test-Path "$root\frontend\node_modules\.package-lock.json") {
    Write-Host "  前端依赖 OK" -ForegroundColor Green
} else {
    Write-Host "  安装前端依赖..." -ForegroundColor Yellow
    Push-Location "$root\frontend"
    npm install --silent 2>&1 | Out-Null
    Pop-Location
    Write-Host "  前端依赖安装完成" -ForegroundColor Green
}

# ---- 自动更新 vite proxy ----
$viteConfig = "$root\frontend\vite.config.js"
if (Test-Path $viteConfig) {
    $content = Get-Content $viteConfig -Raw
    $newContent = $content -replace "localhost:\d+", "localhost:$BackendPort"
    if ($content -ne $newContent) {
        Set-Content -Path $viteConfig -Value $newContent -NoNewline
        Write-Host "  已更新前端代理 -> localhost:$BackendPort" -ForegroundColor Gray
    }
}

# ---- 启动服务 ----
Write-Host "`n[4/4] 启动服务..." -ForegroundColor Yellow

Write-Host "  启动后端..." -ForegroundColor Cyan
$procBackend = Start-Process -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "main:app", "--reload", "--port", "$BackendPort", "--host", "0.0.0.0" `
    -WorkingDirectory "$root\backend" `
    -WindowStyle Minimized `
    -PassThru
$procBackend.Id | Out-File -FilePath "$root\.backend.pid" -Encoding ASCII
Write-Host "    后端 PID: $($procBackend.Id)" -ForegroundColor Green

Write-Host "  启动前端..." -ForegroundColor Cyan
$procFrontend = Start-Process -FilePath "cmd" `
    -ArgumentList "/c", "npm run dev -- --port $FrontendPort" `
    -WorkingDirectory "$root\frontend" `
    -WindowStyle Minimized `
    -PassThru
$procFrontend.Id | Out-File -FilePath "$root\.frontend.pid" -Encoding ASCII
Write-Host "    前端 PID: $($procFrontend.Id)" -ForegroundColor Green

Start-Sleep 4

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  启动完成!" -ForegroundColor Green
Write-Host "  后端:  http://localhost:$BackendPort" -ForegroundColor White
Write-Host "  前端:  http://localhost:$FrontendPort" -ForegroundColor White
Write-Host "  API:   http://localhost:$BackendPort/docs" -ForegroundColor White
Write-Host "  停止:  .\stop.ps1" -ForegroundColor White
Write-Host "  重启:  .\start.ps1 -Restart" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
