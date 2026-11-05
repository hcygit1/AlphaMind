"""Trading API 测试：账户、决策列表、执行决策、订单。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.db.connection import init_db
from server.db.repositories import upsert_default_identity, upsert_report
from server.db.trading_repositories import create_decision
from server.main import create_app
from server.trading.extraction import DecisionRecord
from server.trading.judge import RuleJudge


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setenv("ALPHAMIND_DB_PATH", str(db_path))
    monkeypatch.setattr("server.api.trading.build_default_judge", lambda: RuleJudge())
    monkeypatch.setattr("server.api.trading._default_ref_price", lambda t, d: None)
    app = create_app()
    return TestClient(app, raise_server_exceptions=False), db_path


def _make_decision(db_path: Path, **record_kwargs) -> dict:
    report = upsert_report(
        db_path, ticker="600000", trade_date="2026-01-05", signal="Buy",
        summary="s", state_path="/tmp/state.json",
    )
    defaults = dict(
        rating="Buy", action="Buy", entry_price=10.0, stop_loss=9.0,
        price_target=12.0, position_pct=0.10, settlement_days=20,
    )
    defaults.update(record_kwargs)
    return create_decision(
        db_path, report_id=report["id"], ticker="600000",
        trade_date="2026-01-05", record=DecisionRecord(**defaults),
    )


def test_account_creates_default(client):
    test_client, db_path = client
    resp = test_client.get("/api/trading/account")
    assert resp.status_code == 200
    body = resp.json()
    assert body["account"]["name"] == "模拟账户"
    assert body["account"]["initial_cash"] == 1_000_000
    assert body["positions"] == []
    assert body["orders"] == []


def test_decisions_empty_then_listed(client):
    test_client, db_path = client
    assert test_client.get("/api/trading/decisions").json() == []
    decision = _make_decision(db_path)
    decisions = test_client.get("/api/trading/decisions").json()
    assert [d["id"] for d in decisions] == [decision["id"]]
    assert decisions[0]["ticker"] == "600000"


def test_execute_decision_creates_pending_order(client):
    test_client, db_path = client
    decision = _make_decision(db_path)

    resp = test_client.post(f"/api/trading/decisions/{decision['id']}/execute")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "executed"
    assert body["order"]["quantity"] == 10000
    assert body["order"]["status"] == "pending"

    orders = test_client.get("/api/trading/orders").json()
    assert len(orders) == 1
    assert orders[0]["decision_id"] == decision["id"]


def test_execute_decision_idempotent(client):
    test_client, db_path = client
    decision = _make_decision(db_path)
    first = test_client.post(f"/api/trading/decisions/{decision['id']}/execute").json()
    second = test_client.post(f"/api/trading/decisions/{decision['id']}/execute").json()
    assert second["status"] == "executed"
    assert [o["id"] for o in second["orders"]] == [first["order"]["id"]]
    assert len(test_client.get("/api/trading/orders").json()) == 1


def test_execute_decision_blocked_by_rule_judge(client):
    test_client, db_path = client
    # 止损高于入场价 → RuleJudge block
    decision = _make_decision(db_path, stop_loss=11.0)

    resp = test_client.post(f"/api/trading/decisions/{decision['id']}/execute")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "blocked"
    assert test_client.get("/api/trading/orders").json() == []


def test_execute_decision_not_found(client):
    test_client, _ = client
    resp = test_client.post("/api/trading/decisions/dec_missing/execute")
    assert resp.status_code == 404


def test_refresh_empty_account(client):
    test_client, _ = client
    resp = test_client.post("/api/trading/refresh")
    assert resp.status_code == 200
    body = resp.json()
    assert body["orders"] == {"filled": 0, "rejected": 0, "postponed": 0, "cancelled": 0}
    assert body["settlements"] == []
    assert body["equity"]["total_equity"] == 1_000_000


def test_refresh_settlements_equity_flow(client, monkeypatch):
    test_client, db_path = client
    # 数据源全部 stub，走 execute → refresh → settlements/equity 全链路
    decision = _make_decision(db_path, settlement_days=5)  # settle 2026-01-12
    test_client.post(f"/api/trading/decisions/{decision['id']}/execute")  # exec 2026-01-06

    monkeypatch.setattr(
        "server.trading.settlement.astock_quote_provider",
        lambda d, t: {"open": 10.0, "limit_up": 11.0, "limit_down": 9.0},
    )
    monkeypatch.setattr(
        "server.trading.settlement.astock_close_provider",
        lambda t, d: 11.0,
    )
    monkeypatch.setattr(
        "server.trading.settlement.yfinance_benchmark_provider",
        lambda s, e: (100.0, 102.0),
    )
    import pandas as pd

    monkeypatch.setattr(pd.Timestamp, "now", classmethod(lambda cls: cls("2026-01-12")))

    body = test_client.post("/api/trading/refresh").json()
    assert body["orders"]["filled"] == 1
    assert len(body["settlements"]) == 1
    assert body["settlements"][0]["excess_return"] == pytest.approx(0.08)
    # 净值 = 现金（100 万 - 10 万 - 佣金 25）+ 10,000 股 × 11 = 1,009,975
    assert body["equity"]["total_equity"] == pytest.approx(1_009_975)

    settlements = test_client.get("/api/trading/settlements").json()
    assert len(settlements) == 1
    assert settlements[0]["outcome"] == "跑赢基准"

    equity = test_client.get("/api/trading/equity").json()
    assert len(equity) == 1
    assert equity[0]["total_equity"] == pytest.approx(1_009_975)
