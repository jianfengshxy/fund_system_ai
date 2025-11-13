import pytest
import requests
from src.API.交易管理.trade import get_trades_list, get_bank_shares
from src.common.constant import DEFAULT_USER
from src.common.errors import RetriableError, ValidationError

class _Resp:
    def __init__(self, data):
        self._d = data
    def json(self):
        return self._d
    def raise_for_status(self):
        return None

def test_get_trades_list_request_error_raises_retriable(monkeypatch):
    def _raise(*args, **kwargs):
        raise requests.exceptions.RequestException("net")
    monkeypatch.setattr("requests.post", _raise)
    with pytest.raises(RetriableError):
        get_trades_list(DEFAULT_USER, "SUBNO", "000001", bus_type="buy", status="success")

def test_get_trades_list_api_fail_raises_validation(monkeypatch):
    def _ok(*args, **kwargs):
        return _Resp({"Success": False, "Data": None, "FirstError": "fail"})
    monkeypatch.setattr("requests.post", _ok)
    with pytest.raises(ValidationError):
        get_trades_list(DEFAULT_USER, "SUBNO", "000001", bus_type="buy", status="success")

def test_get_bank_shares_request_error_raises_retriable(monkeypatch):
    def _raise(*args, **kwargs):
        raise requests.exceptions.RequestException("net")
    monkeypatch.setattr("requests.post", _raise)
    with pytest.raises(RetriableError):
        get_bank_shares(DEFAULT_USER, "SUBNO", "000001")

def test_get_bank_shares_api_fail_raises_validation(monkeypatch):
    def _ok(*args, **kwargs):
        return _Resp({"Success": False, "Data": None})
    monkeypatch.setattr("requests.post", _ok)
    with pytest.raises(ValidationError):
        get_bank_shares(DEFAULT_USER, "SUBNO", "000001")
