import pytest
import requests
from src.API.交易管理.buyMrg import commit_order
from src.API.交易管理.buyMrg import get_trace_id as real_get_trace_id
from src.common.constant import DEFAULT_USER
from src.common.errors import RetriableError, ValidationError

def test_commit_order_trace_id_empty_raises_validation(monkeypatch):
    monkeypatch.setattr("src.API.交易管理.buyMrg.get_trace_id", lambda u: None)
    with pytest.raises(ValidationError):
        commit_order(DEFAULT_USER, "SUBNO", "000001", 100.0)

class _Resp:
    def __init__(self, data):
        self._d = data
    def json(self):
        return self._d
    def raise_for_status(self):
        return None

def test_commit_order_request_exception_raises_retriable(monkeypatch):
    monkeypatch.setattr("src.API.交易管理.buyMrg.get_trace_id", lambda u: "trace")
    def _raise(*args, **kwargs):
        raise requests.exceptions.RequestException("net")
    monkeypatch.setattr("requests.post", _raise)
    with pytest.raises(RetriableError):
        commit_order(DEFAULT_USER, "SUBNO", "000001", 100.0)
