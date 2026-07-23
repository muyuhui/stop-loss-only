from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
PROJECT_TEMP = ROOT / ".tmp" / "smoke"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def request(url: str, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=3) as response:
        return response.status, json.loads(response.read() or b"{}")


def main() -> int:
    PROJECT_TEMP.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="stop-loss-smoke-", dir=PROJECT_TEMP) as temp:
        database = Path(temp) / "smoke.db"
        log_path = Path(temp) / "backend.log"
        port = free_port()
        frontend_port = free_port()
        env = os.environ.copy()
        env.update({
            "STOP_LOSS_DATABASE_URL": f"sqlite:///{database.as_posix()}",
            "STOP_LOSS_SCHEDULER_ENABLED": "0", "STOP_LOSS_FIXTURE_PRICE": "8.8",
            "STOP_LOSS_LOG_FORMAT": "text", "PYTHONDONTWRITEBYTECODE": "1",
            "STOP_LOSS_TEMP_DIR": temp, "STOP_LOSS_NETWORK_SENTINEL": "1",
            "STOP_LOSS_NETWORK_ALLOW_LOOPBACK": "1",
        })
        subprocess.run([sys.executable, "db_admin.py", "upgrade"], cwd=BACKEND, env=env, check=True)
        frontend_dist = ROOT / "frontend" / "dist"
        if not (frontend_dist / "index.html").exists():
            raise RuntimeError("前端 dist 不存在，请先运行生产构建")
        with log_path.open("w", encoding="utf-8") as log, (Path(temp) / "frontend.log").open("w", encoding="utf-8") as frontend_log:
            process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port), "--workers", "1"],
                cwd=BACKEND, env=env, stdout=log, stderr=subprocess.STDOUT,
            )
            frontend_process = subprocess.Popen(
                [sys.executable, "-m", "http.server", str(frontend_port), "--bind", "127.0.0.1", "--directory", str(frontend_dist)],
                cwd=ROOT, env=env, stdout=frontend_log, stderr=subprocess.STDOUT,
            )
            try:
                base = f"http://127.0.0.1:{port}/api"
                for _ in range(30):
                    try:
                        if request(f"{base}/health/ready")[1]["status"] == "ok":
                            break
                    except (OSError, urllib.error.URLError):
                        time.sleep(0.2)
                else:
                    raise RuntimeError(f"后端未就绪：{log_path.read_text(encoding='utf-8')}")
                for _ in range(20):
                    try:
                        with urllib.request.urlopen(f"http://127.0.0.1:{frontend_port}/", timeout=2) as response:
                            if response.status == 200 and b'<div id="app"></div>' in response.read():
                                break
                    except (OSError, urllib.error.URLError):
                        time.sleep(0.1)
                else:
                    raise RuntimeError("前端静态服务未就绪")
                _, created = request(f"{base}/holdings", "POST", {
                    "code": "000001", "name": "冒烟测试", "type": "stock", "buy_price": 10,
                    "quantity": 100, "buy_date": "2026-01-01", "stop_loss_method": "fixed", "stop_loss_value": 9,
                })
                _, updated = request(f"{base}/holdings/{created['id']}", "PUT", {
                    "name": "冒烟测试已更新", "stop_loss_method": "percentage", "stop_loss_value": 5,
                })
                assert updated["name"] == "冒烟测试已更新"
                assert updated["stop_loss_method"] == "percentage"
                _, detail = request(f"{base}/holdings/{created['id']}")
                assert detail["stop_loss_price"] == 9.5
                _, refresh = request(f"{base}/prices/refresh", "POST")
                assert refresh["triggered"][0]["id"] == created["id"]
                _, alerts = request(f"{base}/alerts")
                assert alerts["items"][0]["holding_name"] == "冒烟测试已更新"
                request(f"{base}/alerts/{alerts['items'][0]['id']}/read", "PUT")
                _, unread = request(f"{base}/alerts/count")
                assert unread["count"] == 0
                _, settings = request(f"{base}/settings", "PUT", {
                    "poll_interval": 45, "monitor_interval": 7,
                })
                assert settings["poll_interval"] == 45 and settings["monitor_interval"] == 7
                request(f"{base}/holdings/{created['id']}/close", "POST", {"close_price": 8.7})
                _, dashboard = request(f"{base}/dashboard")
                assert dashboard["closed_count"] == 1
            finally:
                for owned_process in (process, frontend_process):
                    owned_process.terminate()
                    try:
                        owned_process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        owned_process.kill()
                        owned_process.wait(timeout=5)
            if process.poll() is None or frontend_process.poll() is None:
                raise RuntimeError("冒烟测试残留自有进程")
    print("端到端冒烟测试通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
