from __future__ import annotations

from src.service.市场指数.market_index_service import MarketIndexService


class _FakeDb:
    def __init__(self):
        self.insert_many_calls = []
        self.query_rows = []

    def insert_many(self, sql, params_list):
        self.insert_many_calls.append((sql, list(params_list)))
        return len(params_list)

    def execute_query(self, sql, params=None):
        return list(self.query_rows)


def test_backfill_heat_score_history_batch_uses_one_year_series(monkeypatch):
    service = MarketIndexService.__new__(MarketIndexService)
    service._db = _FakeDb()

    captured = {}

    def _fake_get_index_money_flow(user, index_code, range_type="n"):
        captured["index_code"] = index_code
        captured["range_type"] = range_type
        return [
            {
                "PDATE": "2026-10-20",
                "PERCENTPRICE": 1234.56,
                "CHGRT": 1.23,
                "XLFLOW_SCORE": 45.6,
            },
            {
                "PDATE": "2026-10-21",
                "PERCENTPRICE": 1236.78,
                "CHGRT": 0.18,
                "XLFLOW_SCORE": None,
            },
            {
                "PDATE": "2026-10-22",
                "PERCENTPRICE": 1240.11,
                "CHGRT": 0.27,
                "XLFLOW_SCORE": 48.2,
            },
        ]

    monkeypatch.setattr(
        "src.API.市场指数.指数资金流向.get_index_money_flow",
        _fake_get_index_money_flow,
    )

    result = service.backfill_heat_score_history_batch(
        user=object(),
        index_code="930997",
        range_type="n",
    )

    assert captured == {"index_code": "930997", "range_type": "n"}
    assert result == {"rows": 3, "total_points": 3, "heat_points": 2}
    assert len(service._db.insert_many_calls) == 1

    sql, params = service._db.insert_many_calls[0]
    assert "heat_score = COALESCE(VALUES(heat_score), heat_score)" in sql
    assert params == [
        ("930997", "2026-10-20", 1234.56, 1.23, 45.6),
        ("930997", "2026-10-21", 1236.78, 0.18, None),
        ("930997", "2026-10-22", 1240.11, 0.27, 48.2),
    ]


def test_backfill_daily_valuation_percentiles_uses_expanding_history():
    service = MarketIndexService.__new__(MarketIndexService)
    service._db = _FakeDb()
    service._db.query_rows = [
        {"trade_date": "2026-10-20", "pe_ttm": 10.0, "pb": 1.0},
        {"trade_date": "2026-10-21", "pe_ttm": 20.0, "pb": 2.0},
        {"trade_date": "2026-10-22", "pe_ttm": 15.0, "pb": 1.5},
        {"trade_date": "2026-10-23", "pe_ttm": None, "pb": 3.0},
    ]

    result = service.backfill_daily_valuation_percentiles("930997")

    assert result == {"rows": 4, "total_points": 4, "pe_points": 3, "pb_points": 4}
    assert len(service._db.insert_many_calls) == 1

    sql, params = service._db.insert_many_calls[0]
    assert "pe_pct = COALESCE(VALUES(pe_pct), pe_pct)" in sql
    assert "pb_pct = COALESCE(VALUES(pb_pct), pb_pct)" in sql
    assert params == [
        ("930997", "2026-10-20", 100.0, 100.0),
        ("930997", "2026-10-21", 100.0, 100.0),
        ("930997", "2026-10-22", 66.6667, 66.6667),
        ("930997", "2026-10-23", None, 100.0),
    ]
