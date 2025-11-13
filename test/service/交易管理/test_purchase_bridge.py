import pytest
from src.service.交易管理.购买基金 import commit_order
from src.common.constant import DEFAULT_USER
from src.common.errors import RetriableError, ValidationError, TradePasswordError

def test_purchase_bridge_retriable(monkeypatch):
    def _raise(*args, **kwargs):
        raise RetriableError("net")
    monkeypatch.setattr("src.API.交易管理.buyMrg.commit_order", _raise)
    assert commit_order(DEFAULT_USER, "SUBNO", "000001", 100.0) is None

def test_purchase_bridge_validation(monkeypatch):
    def _raise(*args, **kwargs):
        raise ValidationError("bad")
    monkeypatch.setattr("src.API.交易管理.buyMrg.commit_order", _raise)
    assert commit_order(DEFAULT_USER, "SUBNO", "000001", 100.0) is None

def test_purchase_bridge_password(monkeypatch):
    def _raise(*args, **kwargs):
        raise TradePasswordError("pwd")
    monkeypatch.setattr("src.API.交易管理.buyMrg.commit_order", _raise)
    with pytest.raises(TradePasswordError):
        commit_order(DEFAULT_USER, "SUBNO", "000001", 100.0)
