import json
import socket
from pathlib import Path

import pytest

from network_guard import NetworkAccessBlocked


FIXTURES = Path(__file__).with_name("fixtures")


def test_schema_v2_and_api_fixtures_are_privacy_safe_and_representative():
    schema = json.loads((FIXTURES / "schema_v2.json").read_text(encoding="utf-8"))
    api = json.loads((FIXTURES / "api_v2.json").read_text(encoding="utf-8"))
    assert schema["schema_version"] == 2
    assert {row["status"] for row in schema["holdings"]} == {"holding", "closed"}
    assert api["holding"]["code"] == "000001"
    serialized = json.dumps({"schema": schema, "api": api}, ensure_ascii=False)
    for forbidden in ("password", "token", "secret", "cookie", "authorization"):
        assert forbidden not in serialized.lower()


def test_mandatory_network_sentinel_rejects_dns_and_socket_access():
    with pytest.raises(NetworkAccessBlocked, match="DNS lookup"):
        socket.getaddrinfo("example.com", 443)
    with pytest.raises(NetworkAccessBlocked, match="connection"):
        socket.create_connection(("203.0.113.1", 443), timeout=0.01)
