import pytest
import requests
from src.API.资产管理.AssetManager import GetMyAssetMainPartAsync
from src.common.constant import DEFAULT_USER
from src.common.errors import RetriableError, ValidationError

class _Resp:
    def __init__(self, data):
        self._d = data
    def json(self):
        return self._d
    def raise_for_status(self):
        return None

def test_asset_manager_request_error_raises_retriable(monkeypatch):
    def _raise(*args, **kwargs):
        raise requests.exceptions.RequestException("net")
    monkeypatch.setattr("requests.post", _raise)
    with pytest.raises(RetriableError):
        GetMyAssetMainPartAsync(DEFAULT_USER)

def test_asset_manager_parse_error_raises_validation(monkeypatch):
    def _ok(*args, **kwargs):
        return _Resp({"Success": True, "Data": None})
    monkeypatch.setattr("requests.post", _ok)
    with pytest.raises(ValidationError):
        GetMyAssetMainPartAsync(DEFAULT_USER)
