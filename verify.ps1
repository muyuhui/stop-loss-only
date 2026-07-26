$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$env:PYTHONDONTWRITEBYTECODE = '1'
$runId = [Guid]::NewGuid().ToString('N')
$projectTemp = Join-Path $root ".tmp\verify\$runId"
New-Item -ItemType Directory -Path $projectTemp -Force | Out-Null
$env:TEMP = $projectTemp
$env:TMP = $projectTemp
$env:STOP_LOSS_TEMP_DIR = $projectTemp
. (Join-Path $root 'scripts\npm_environment.ps1')
Initialize-ProjectNpmEnvironment -StateRoot $projectTemp
Write-Host "[预检] 验证后端导入与前端依赖图"
& python -c "import fastapi, sqlalchemy, apscheduler, akshare, pytest"
if ($LASTEXITCODE -ne 0) { throw '后端依赖不完整，请运行 .\setup.ps1 -Dev。' }
Push-Location (Join-Path $root 'frontend')
try { & node scripts/check-dependencies.mjs; if ($LASTEXITCODE -ne 0) { throw '前端依赖不完整，请运行 .\setup.ps1 -Dev。' } } finally { Pop-Location }
Push-Location (Join-Path $root 'backend')
try { & python -m pytest -p no:cacheprovider --basetemp (Join-Path $projectTemp 'pytest') -q; if ($LASTEXITCODE -ne 0) { throw '后端测试失败。' } } finally { Pop-Location }
Push-Location (Join-Path $root 'frontend')
try {
    & npm test; if ($LASTEXITCODE -ne 0) { throw '前端行为测试失败。' }
    & npm run build; if ($LASTEXITCODE -ne 0) { throw '前端生产构建或包体预算失败。' }
    & npm run test:e2e; if ($LASTEXITCODE -ne 0) { throw '三视口浏览器 E2E 失败。' }
} finally { Pop-Location }
& python (Join-Path $root 'scripts\smoke.py'); if ($LASTEXITCODE -ne 0) { throw '离线 API/进程冒烟失败。' }
& python (Join-Path $root 'scripts\restore_drill.py'); if ($LASTEXITCODE -ne 0) { throw '备份恢复演练失败。' }
& openspec validate --all --strict --no-interactive; if ($LASTEXITCODE -ne 0) { throw 'OpenSpec 全量严格校验失败。' }
Write-Host "全部质量门禁通过。运行临时目录：$projectTemp。真实 provider 检查为可选项，不计入离线门禁。" -ForegroundColor Green
