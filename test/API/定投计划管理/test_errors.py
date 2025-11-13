import pytest
import requests
from src.API.定投计划管理.SmartPlan import getFundRations, getFundPlanList
from src.common.constant import DEFAULT_USER
from src.common.errors import RetriableError, ValidationError

def test_getFundRations_request_error_raises_retriable(monkeypatch):
    def _raise(*args, **kwargs):
        raise requests.exceptions.RequestException("net")
    monkeypatch.setattr("requests.post", _raise)
    with pytest.raises(RetriableError):
        getFundRations(DEFAULT_USER, page_index=1, page_size=10, planTypes=[1])

class _Resp:
    def __init__(self, data):
        self._d = data
    def json(self):
        return self._d
    def raise_for_status(self):
        return None

def test_getFundPlanList_data_empty_raises_validation(monkeypatch):
    def _ok(*args, **kwargs):
        return _Resp({"Success": True, "Data": None})
    monkeypatch.setattr("requests.get", _ok)
    with pytest.raises(ValidationError):
        getFundPlanList("000001", DEFAULT_USER)
