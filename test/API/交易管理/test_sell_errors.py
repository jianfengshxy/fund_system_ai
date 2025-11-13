import pytest
import requests
from src.API.交易管理.sellMrg import super_transfer, hqbMakeRedemption, SFT1Transfer
from src.common.constant import DEFAULT_USER
from src.common.errors import RetriableError, ValidationError

class _Resp:
    def __init__(self, data, json_raises=False):
        self._d = data
        self._raises = json_raises
    def json(self):
        if self._raises:
            raise ValueError("bad json")
        return self._d
    def raise_for_status(self):
        return None

def test_super_transfer_request_error_retriable(monkeypatch):
    def _raise(*args, **kwargs):
        raise requests.exceptions.RequestException("net")
    monkeypatch.setattr("requests.post", _raise)
    with pytest.raises(RetriableError):
        super_transfer(DEFAULT_USER, "SUBNO", "000001", 1.0, "SID")

def test_super_transfer_parse_error_validation(monkeypatch):
    def _ok(*args, **kwargs):
        return _Resp({"Success": True}, json_raises=True)
    monkeypatch.setattr("requests.post", _ok)
    with pytest.raises(ValidationError):
        super_transfer(DEFAULT_USER, "SUBNO", "000001", 1.0, "SID")
