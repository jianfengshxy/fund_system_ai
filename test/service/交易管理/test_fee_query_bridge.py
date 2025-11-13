from src.service.交易管理.费率查询 import get_0_fee_shares
from src.common.errors import RetriableError, ValidationError
from src.common.constant import DEFAULT_USER
import pytest

def test_get_0_fee_shares_retriable(monkeypatch):
    from src.service.交易管理 import 费率查询 as mod
    def _raise(*args, **kwargs):
        raise RetriableError("net")
    monkeypatch.setattr(mod, "getFee", _raise)
    assert get_0_fee_shares(DEFAULT_USER, "000001") == 0.0

def test_get_0_fee_shares_validation(monkeypatch):
    from src.service.交易管理 import 费率查询 as mod
    def _raise(*args, **kwargs):
        raise ValidationError("bad")
    monkeypatch.setattr(mod, "getFee", _raise)
    assert get_0_fee_shares(DEFAULT_USER, "000001") == 0.0
