from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from models import Holding
from routers import holdings


@pytest.fixture()
def api():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False)
    app = FastAPI()
    app.include_router(holdings.router, prefix="/api")

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app, raise_server_exceptions=False), session_factory


def holding_body(**overrides):
    body = {
        "code": "000001", "name": "测试股票", "type": "stock", "buy_price": 10,
        "quantity": 100, "buy_date": "2026-01-01", "stop_loss_method": "fixed", "stop_loss_value": 9,
    }
    body.update(overrides)
    return body


def create(client, **overrides):
    response = client.post("/api/holdings", json=holding_body(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def price(session_factory, holding_id: int, *, current, quote_state="live", status=None):
    """把持仓置为已定价状态；`status` 可覆盖生命周期以模拟已触发。"""
    session = session_factory()
    try:
        row = session.get(Holding, holding_id)
        row.current_price = Decimal(str(current))
        row.quote_state = quote_state
        row.quoted_at = datetime.now(timezone.utc)
        if status:
            row.status = status
        session.commit()
    finally:
        session.close()


def test_search_matches_name_and_code(api):
    client, _ = api
    create(client, code="000001", name="平安银行")
    create(client, code="000002", name="工商银行")
    create(client, code="600519", name="贵州茅台")
    by_name = client.get("/api/holdings", params={"search": "银行"}).json()
    assert [item["name"] for item in by_name["items"]] == ["工商银行", "平安银行"]
    assert by_name["total"] == 2
    by_code = client.get("/api/holdings", params={"search": "0000"}).json()
    assert [item["code"] for item in by_code["items"]] == ["000002", "000001"]
    assert by_code["total"] == 2


def test_search_escapes_like_wildcards(api):
    client, _ = api
    create(client, code="A_B", name="100%增长基金", type="fund")
    create(client, code="000001", name="测试股票")
    assert client.get("/api/holdings", params={"search": "100%"}).json()["total"] == 1
    assert client.get("/api/holdings", params={"search": "A_B"}).json()["total"] == 1
    assert client.get("/api/holdings", params={"search": "%"}).json()["total"] == 1
    assert client.get("/api/holdings", params={"search": "_"}).json()["total"] == 1


def test_search_blank_means_no_filter(api):
    client, _ = api
    create(client)
    create(client, code="000002", name="测试基金", type="fund")
    for value in ("", "   "):
        assert client.get("/api/holdings", params={"search": value}).json()["total"] == 2
    assert client.get("/api/holdings").json()["total"] == 2


def test_type_filter(api):
    client, _ = api
    create(client, type="stock")
    create(client, code="000002", name="测试基金", type="fund")
    stocks = client.get("/api/holdings", params={"type": "stock"}).json()
    assert [item["type"] for item in stocks["items"]] == ["stock"] and stocks["total"] == 1
    funds = client.get("/api/holdings", params={"type": "fund"}).json()
    assert [item["type"] for item in funds["items"]] == ["fund"] and funds["total"] == 1
    assert client.get("/api/holdings", params={"type": "etf"}).status_code == 422


def test_sort_newest_is_default_order(api):
    client, _ = api
    first = create(client, name="甲")
    second = create(client, name="乙")
    third = create(client, name="丙")
    page = client.get("/api/holdings").json()
    assert [item["id"] for item in page["items"]] == [third["id"], second["id"], first["id"]]
    explicit = client.get("/api/holdings", params={"sort": "newest"}).json()
    assert [item["id"] for item in explicit["items"]] == [third["id"], second["id"], first["id"]]


def test_sort_name_order(api):
    client, _ = api
    create(client, name="测试C")
    create(client, name="测试A")
    create(client, name="测试B")
    page = client.get("/api/holdings", params={"sort": "name"}).json()
    assert [item["name"] for item in page["items"]] == ["测试A", "测试B", "测试C"]


def test_sort_risk_orders_by_distance_with_unpriced_last(api):
    client, session_factory = api
    nearest = create(client, name="贵州茅台", code="600519", stop_loss_value=9.5)
    middle = create(client, name="平安银行", code="000001", stop_loss_value=9)
    farthest = create(client, name="工商银行", code="000002", stop_loss_value=8)
    unpriced = create(client, name="未定价股票", code="600000", stop_loss_value=9)
    for item in (nearest, middle, farthest):
        price(session_factory, item["id"], current=10)
    page = client.get("/api/holdings", params={"sort": "risk"}).json()
    assert [item["name"] for item in page["items"]] == ["贵州茅台", "平安银行", "工商银行", "未定价股票"]
    assert page["items"][-1]["stop_loss_distance_pct"] is None


def test_sort_risk_puts_triggered_negative_distance_first(api):
    client, session_factory = api
    safe = create(client, name="安全持仓", code="000001", stop_loss_value=8)
    triggered = create(client, name="已触发持仓", code="000002", stop_loss_value=9.5)
    price(session_factory, safe["id"], current=10)
    price(session_factory, triggered["id"], current=9, status="triggered")
    page = client.get("/api/holdings", params={"sort": "risk"}).json()
    assert [item["name"] for item in page["items"]] == ["已触发持仓", "安全持仓"]
    assert page["items"][0]["stop_loss_distance_pct"] < 0


def test_sort_risk_matches_displayed_distance(api):
    """SQL 排序结果必须与 holding_payload 展示距离的顺序一致（防列漂移）。"""
    client, session_factory = api
    created = []
    for index, (name, code, stop) in enumerate(
        [("测试A", "000001", 9), ("测试B", "000002", 8), ("测试C", "000003", 9.5), ("测试D", "000004", 7)], start=1
    ):
        item = create(client, name=name, code=code, stop_loss_value=stop)
        price(session_factory, item["id"], current=10)
        created.append(item)
    create(client, name="测试E", code="000005", stop_loss_value=9)  # 保持 unpriced
    page = client.get("/api/holdings", params={"sort": "risk", "size": 50}).json()
    expected = sorted(
        page["items"],
        key=lambda item: (item["stop_loss_distance_pct"] is None, item["stop_loss_distance_pct"], item["id"]),
    )
    assert [item["id"] for item in page["items"]] == [item["id"] for item in expected]
    distances = [item["stop_loss_distance_pct"] for item in page["items"]]
    valued = [value for value in distances if value is not None]
    assert valued == sorted(valued)
    assert all(value is None for value in distances[len(valued):])


def test_invalid_sort_returns_422(api):
    client, _ = api
    assert client.get("/api/holdings", params={"sort": "profit"}).status_code == 422


def test_combined_filters_sort_and_pagination(api):
    client, session_factory = api
    pingan = create(client, name="平安银行", code="000001", stop_loss_value=9)
    gongshang = create(client, name="工商银行", code="000002", stop_loss_value=8)
    jianshe = create(client, name="建设银行", code="000003", stop_loss_value=9.5)
    create(client, name="平安基金", code="000004", type="fund", stop_loss_value=9)
    create(client, name="工商基金", code="000005", type="fund", stop_loss_value=7)
    for item in (pingan, gongshang, jianshe):
        price(session_factory, item["id"], current=10)
    first = client.get("/api/holdings", params={
        "search": "银行", "status": "holding", "type": "stock", "sort": "risk", "page": 1, "size": 2,
    }).json()
    assert first["total"] == 3
    assert [item["name"] for item in first["items"]] == ["建设银行", "平安银行"]
    second = client.get("/api/holdings", params={
        "search": "银行", "status": "holding", "type": "stock", "sort": "risk", "page": 2, "size": 2,
    }).json()
    assert [item["name"] for item in second["items"]] == ["工商银行"]
    assert second["total"] == 3
