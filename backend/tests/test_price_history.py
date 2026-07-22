from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from models import Holding, PriceHistory
from services.market_clock import MARKET_TZ
from services.price_history import HistoryUnavailable, holding_history


NOW = datetime(2026, 7, 22, 12, 0, tzinfo=MARKET_TZ)


def make_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_holding(method="fixed", value="9", code="000001"):
    return Holding(
        code=code, name="测试", type="stock", buy_price=Decimal("10"), quantity=100,
        buy_date=date(2026, 5, 1), current_price=Decimal("12"), highest_price=Decimal("12"),
        stop_loss_method=method, stop_loss_value=Decimal(value), stop_loss_price=Decimal("9"), status="holding",
    )


def rows():
    return [
        {"trade_date": date(2026, 7, 18), "price": Decimal("10"), "source": "fixture-history"},
        {"trade_date": date(2026, 7, 19), "price": Decimal("12"), "source": "fixture-history"},
        {"trade_date": date(2026, 7, 20), "price": Decimal("10.5"), "source": "fixture-history"},
    ]


def test_history_cache_is_deduplicated_and_shared(monkeypatch):
    db = make_db()
    first, second = make_holding(), make_holding()
    db.add_all([first, second])
    db.commit()
    calls = []
    monkeypatch.setattr("services.price_history.local_now", lambda: NOW)
    monkeypatch.setattr("services.price_history.fetch_price_history", lambda *args: calls.append(args) or [
        {"trade_date": args[2], "price": Decimal("10"), "source": "fixture-history"}, *rows(),
    ])
    holding_history(db, first, "3m")
    holding_history(db, second, "3m")
    assert len(calls) == 1
    assert db.query(PriceHistory).count() == 4


def test_expanding_range_fetches_the_earlier_gap(monkeypatch):
    db = make_db()
    item = make_holding()
    db.add(item)
    db.commit()
    calls = []
    monkeypatch.setattr("services.price_history.local_now", lambda: NOW)

    def loader(code, asset_type, start, end):
        calls.append((start, end))
        return [{"trade_date": start, "price": Decimal("10"), "source": "fixture-history"}]

    monkeypatch.setattr("services.price_history.fetch_price_history", loader)
    holding_history(db, item, "1m")
    holding_history(db, item, "3m")
    assert len(calls) == 2
    assert calls[1][0] < calls[0][0]
    assert db.query(PriceHistory).count() == 2


def test_stop_loss_series_fixed_percentage_and_trailing(monkeypatch):
    monkeypatch.setattr("services.price_history.local_now", lambda: NOW)
    for method, value, expected in (
        ("fixed", "9", [9, 9, 9]),
        ("percentage", "10", [9, 9, 9]),
        ("trailing", "10", [9, 10.8, 10.8]),
    ):
        db = make_db()
        item = make_holding(method, value)
        db.add(item)
        db.commit()
        monkeypatch.setattr("services.price_history.fetch_price_history", lambda *args: rows())
        result = holding_history(db, item, "3m")
        assert [point["stop_loss_price"] for point in result["points"]] == expected
        assert result["points"][-1]["triggered"] is (method == "trailing")


def test_history_failure_uses_cache_or_raises(monkeypatch):
    db = make_db()
    item = make_holding()
    db.add(item)
    db.add(PriceHistory(
        code=item.code, asset_type=item.type, trade_date=date(2026, 7, 20),
        price=Decimal("10"), source="cache", fetched_at=datetime(2026, 7, 20, 12, 0),
    ))
    db.commit()
    monkeypatch.setattr("services.price_history.local_now", lambda: NOW)
    monkeypatch.setattr("services.price_history.fetch_price_history", lambda *args: (_ for _ in ()).throw(RuntimeError("offline")))
    result = holding_history(db, item, "1m")
    assert result["stale"] is True and result["points"]

    empty_db = make_db()
    empty = make_holding(code="000002")
    empty_db.add(empty)
    empty_db.commit()
    try:
        holding_history(empty_db, empty, "1m")
        assert False, "expected HistoryUnavailable"
    except HistoryUnavailable as exc:
        assert exc.correlation_id
