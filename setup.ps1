param([switch]$Dev)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

# 环境预检：Python 版本（3.12+）与 openspec CLI（验证门禁依赖）
try {
    $pythonVersion = & python --version 2>&1
} catch {
    throw '未找到 python。请安装 Python 3.12 或更高版本并确保 python 在 PATH 中。'
}
if ($LASTEXITCODE -ne 0 -or $pythonVersion -notmatch 'Python (\d+)\.(\d+)') {
    throw "无法识别 Python 版本（输出：$pythonVersion）。请安装 Python 3.12 或更高版本。"
}
$pythonMajor = [int]$Matches[1]
$pythonMinor = [int]$Matches[2]
if ($pythonMajor -lt 3 -or ($pythonMajor -eq 3 -and $pythonMinor -lt 12)) {
    throw "需要 Python 3.12 或更高版本，当前为 $pythonMajor.$pythonMinor。请升级后重新运行 .\setup.ps1。"
}
if (-not (Get-Command openspec -ErrorAction SilentlyContinue)) {
    throw '缺少 openspec CLI。请先运行 npm install -g @fission-ai/openspec，再重新运行 .\setup.ps1。'
}

. (Join-Path $root 'scripts\npm_environment.ps1')
Initialize-ProjectNpmEnvironment -StateRoot (Join-Path $root '.tmp\setup')
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
