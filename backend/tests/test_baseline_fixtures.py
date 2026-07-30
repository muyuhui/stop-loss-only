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
    unpriced = api["unpriced_holding"]
    assert unpriced["current_price"] is None
    assert unpriced["profit_loss_pct"] is None
    assert unpriced["stop_loss_distance_pct"] is None
    assert unpriced["quote_state"] == "unpriced"
    assert api["monitoring_status"]["quote_coverage_pct"] is None
    assert api["alert_query"]["parameters"] == ["search", "unread", "disposition", "page", "size"]
    assert schema["risk_policy"]["portfolio_equity"] == "100000.0000"
    assert api["runtime_capabilities"]["capabilities"]["risk_plan_previews"] is True
    assert api["runtime_capabilities"]["capabilities"]["risk_covered_position_creation"] is False
    assert api["risk_plan_preview"]["plan_kind"] == "new"
    assert api["risk_plan_preview"]["recommended_quantity"] == "400"
    assert api["risk_add_on_preview"]["plan_kind"] == "add_on"
    assert api["risk_add_on_preview"]["holding"]["stop_loss_price"] == "9.0000"
    stored_unpriced = next(row for row in schema["holdings"] if row["id"] == 103)
    assert stored_unpriced["current_price"] == "0.0000"
    assert stored_unpriced["quote_state"] == "unpriced"
    serialized = json.dumps({"schema": schema, "api": api}, ensure_ascii=False)
    for forbidden in ("password", "token", "secret", "cookie", "authorization"):
        assert forbidden not in serialized.lower()


def test_mandatory_network_sentinel_rejects_dns_and_socket_access():
    with pytest.raises(NetworkAccessBlocked, match="DNS lookup"):
        socket.getaddrinfo("example.com", 443)
    with pytest.raises(NetworkAccessBlocked, match="connection"):
        socket.create_connection(("203.0.113.1", 443), timeout=0.01)
