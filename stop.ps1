param(
    [int]$BackendPort = 8001,
    [int]$FrontendPort = 5173
)

$root = $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  止损不止盈 - 关闭中..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

function Kill-Port($port) {
    $lines = netstat -ano | Select-String ":$port " | Select-String "LISTENING" 2>$null
    if (-not $lines) { return }
    foreach ($line in $lines) {
        $parts = $line.ToString().Trim() -split '\s+'
        $procId = $parts[-1]
        if ($procId -and $procId -match '^\d+$') {
            Write-Host "  终止端口 $port (PID: $procId)" -ForegroundColor Yellow
            taskkill /F /T /PID $procId 2>&1 | Out-Null
        }
    }
}

Kill-Port $BackendPort
Kill-Port $FrontendPort

# 清理 PID 文件
Remove-Item "$root\.backend.pid", "$root\.frontend.pid" -Force -ErrorAction SilentlyContinue

Start-Sleep 1

# 验证
$remaining = netstat -ano | Select-String ":(8001|5173) " | Select-String "LISTENING" 2>$null
if ($remaining) {
    Write-Host "`n  以下端口仍有残留:" -ForegroundColor Red
    $remaining | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
    Write-Host "  请手动运行: taskkill /F /PID <PID>" -ForegroundColor Yellow
} else {
    Write-Host "`n  已全部关闭" -ForegroundColor Green
}
