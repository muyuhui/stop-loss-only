param(
    [int]$BackendPort = 8001,
    [int]$FrontendPort = 5173,
    [switch]$Restart
)

$root = $PSScriptRoot
$logDir = "$root\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  止损不止盈 - 启动中..." -ForegroundColor Cyan
Write-Host "  后端:$BackendPort  前端:$FrontendPort  日志:$logDir\" -ForegroundColor Cyan
if ($Restart) { Write-Host "  模式: 重启" -ForegroundColor Yellow }
Write-Host "========================================" -ForegroundColor Cyan

if ($Restart) {
    Write-Host "  停止旧进程..." -ForegroundColor Yellow
    & "$root\stop.ps1" -BackendPort $BackendPort -FrontendPort $FrontendPort
    Start-Sleep 1
    Remove-Item "$logDir\*.log" -Force -ErrorAction SilentlyContinue
}

# 释放端口
function Free-Port($port) {
    netstat -ano | Select-String ":$port " | Select-String "LISTENING" | ForEach-Object {
        $p = ($_ -split '\s+')[-1]
        if ($p -match '^\d+$') { taskkill /F /T /PID $p 2>&1 | Out-Null }
    }
}
Free-Port $BackendPort
Free-Port $FrontendPort

# 启动后端
Write-Host "  启动后端..." -ForegroundColor Cyan
$be = Start-Process -FilePath "cmd" `
    -ArgumentList "/c", "set PYTHONIOENCODING=utf-8 && python -u -m uvicorn main:app --reload --port $BackendPort --host 0.0.0.0 >> `"$logDir\backend.log`" 2>&1" `
    -WorkingDirectory "$root\backend" `
    -WindowStyle Hidden `
    -PassThru
$be.Id | Out-File -FilePath "$root\.backend.pid" -Encoding ASCII
Write-Host "    后端 PID: $($be.Id)" -ForegroundColor Green

# 启动前端
Write-Host "  启动前端..." -ForegroundColor Cyan
$fe = Start-Process -FilePath "cmd" `
    -ArgumentList "/c", "npm run dev -- --port $FrontendPort >> `"$logDir\frontend.log`" 2>&1" `
    -WorkingDirectory "$root\frontend" `
    -WindowStyle Hidden `
    -PassThru
$fe.Id | Out-File -FilePath "$root\.frontend.pid" -Encoding ASCII
Write-Host "    前端 PID: $($fe.Id)" -ForegroundColor Green

Write-Host "  等待服务就绪..." -ForegroundColor Gray
Start-Sleep 3

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  启动完成!" -ForegroundColor Green
Write-Host "  后端 : http://localhost:$BackendPort" -ForegroundColor White
Write-Host "  前端 : http://localhost:$FrontendPort" -ForegroundColor White
Write-Host "  API  : http://localhost:$BackendPort/docs" -ForegroundColor White
Write-Host "  停止 : .\stop.ps1  重启 : .\start.ps1 -Restart" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
