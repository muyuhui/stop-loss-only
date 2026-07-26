import json
import logging
import shutil
import subprocess
from pathlib import Path

from config import AppConfig
from observability import JsonFormatter
from models import MonitoringCycle


ROOT = Path(__file__).resolve().parents[2]


def test_local_defaults_are_safe():
    config = AppConfig()
    assert config.bind_host == "127.0.0.1"
    assert config.scheduler_enabled in (True, False)
    assert config.readiness_timeout_seconds > 0


def test_structured_log_ignores_sensitive_extra_fields():
    record = logging.LogRecord("monitor", logging.INFO, __file__, 1, "cycle_completed", (), None)
    record.correlation_id = "safe-id"
    record.cycle_id = "safe-cycle"
    record.price = 123.45
    record.quantity = 1000
    record.cost = 999
    record.raw_response = {"secret": "provider payload"}
    payload = json.loads(JsonFormatter().format(record))
    assert payload["correlation_id"] == "safe-id"
    assert payload["cycle_id"] == "safe-cycle"
    assert not {"price", "quantity", "cost", "raw_response"}.intersection(payload)


def test_monitoring_diagnostics_schema_contains_only_aggregate_counts():
    columns = {column.name for column in MonitoringCycle.__table__.columns}
    assert {"requested_count", "success_count", "failed_count", "coverage_pct"}.issubset(columns)
    assert not {"price", "current_price", "quantity", "cost", "raw_response"}.intersection(columns)


def test_start_script_never_kills_port_owner_and_stop_checks_ownership():
    start = (ROOT / "start.ps1").read_text(encoding="utf-8")
    stop = (ROOT / "stop.ps1").read_text(encoding="utf-8")
    assert "taskkill" not in start.lower()
    assert "Stop-Process" not in start
    assert "127.0.0.1" in start and "--reload" not in start
    assert "[switch]$Restart" in start and "stop.ps1" in start
    assert "if (-not $?)" in start
    assert "started_at" in stop and "root" in stop and "Stop-Process" in stop
    assert "Stop-LegacyRecordedProcess" in stop and "serviceMarker" in stop


def test_setup_is_separate_from_startup():
    start = (ROOT / "start.ps1").read_text(encoding="utf-8")
    setup = (ROOT / "setup.ps1").read_text(encoding="utf-8")
    assert "pip install" not in start and "npm install" not in start and "npm ci" not in start
    assert "pip install" in setup and "npm ci" in setup


def test_start_and_verify_use_config_independent_frontend_dependency_check():
    start = (ROOT / "start.ps1").read_text(encoding="utf-8")
    verify = (ROOT / "verify.ps1").read_text(encoding="utf-8")

    for script in (start, verify):
        assert "npm ls" not in script
        assert "check-dependencies.mjs" in script


def test_process_start_identity_handles_powershell_json_datetime_conversion():
    helper = (ROOT / "scripts" / "process_identity.ps1").as_posix()
    powershell = shutil.which("pwsh") or shutil.which("powershell.exe")
    assert powershell is not None
    command = f"""
. '{helper}'
$record = '{{"started_at":"2026-07-24T09:50:47.9172650Z"}}' | ConvertFrom-Json
$same = [DateTime]::Parse('2026-07-24T09:50:47.9172650Z')
$different = [DateTime]::Parse('2026-07-24T09:50:48.9172650Z')
if (-not (Test-RecordedProcessStart -RecordedStart $record.started_at -ActualStart $same)) {{ exit 1 }}
if (Test-RecordedProcessStart -RecordedStart $record.started_at -ActualStart $different) {{ exit 2 }}
"""

    result = subprocess.run(
        [powershell, "-NoProfile", "-Command", command],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_project_npm_config_avoids_windows_powershell_native_error():
    helper = (ROOT / "scripts" / "npm_environment.ps1").as_posix()
    frontend = (ROOT / "frontend").as_posix()
    test_state_parent = (ROOT / "backend" / "tests").as_posix()
    command = f"""
$ErrorActionPreference = 'Stop'
$testRoot = Join-Path '{test_state_parent}' ('npm-env-' + [Guid]::NewGuid().ToString('N'))
try {{
    New-Item -ItemType Directory -Path $testRoot | Out-Null
    $badUserConfig = Join-Path $testRoot 'bad-user.npmrc'
    Set-Content -LiteralPath $badUserConfig -Value 'python=python'
    $env:NPM_CONFIG_USERCONFIG = $badUserConfig
    . '{helper}'
    Initialize-ProjectNpmEnvironment -StateRoot (Join-Path $testRoot 'isolated')
    Set-Location '{frontend}'
    & npm ls --depth=0 --json 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {{ exit 1 }}
}} finally {{
    Remove-Item -LiteralPath $testRoot -Recurse -Force -ErrorAction SilentlyContinue
}}
"""

    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", command],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_all_project_entry_scripts_initialize_isolated_npm_config():
    for name in ("setup.ps1", "start.ps1", "verify.ps1"):
        script = (ROOT / name).read_text(encoding="utf-8")
        assert "Initialize-ProjectNpmEnvironment" in script


def test_project_entry_scripts_parse_in_windows_powershell():
    scripts = [
        (ROOT / name).as_posix()
        for name in ("setup.ps1", "start.ps1", "stop.ps1", "verify.ps1")
    ]
    script_literals = ", ".join(f"'{script}'" for script in scripts)
    command = f"""
$failed = $false
foreach ($script in @({script_literals})) {{
    $tokens = $null
    $errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile(
        $script,
        [ref]$tokens,
        [ref]$errors
    ) | Out-Null
    if ($errors.Count -gt 0) {{
        $errors | ForEach-Object {{ Write-Error "${{script}}: $($_.Message)" }}
        $failed = $true
    }}
}}
if ($failed) {{ exit 1 }}
"""

    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", command],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 0, result.stderr
