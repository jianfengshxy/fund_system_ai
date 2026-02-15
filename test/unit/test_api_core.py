import pytest
import requests

from src.API._core.auth import build_auth_fields
from src.API._core.client import ApiClient
from src.API._core.normalize import error_code, error_message, is_auth_error, is_empty_ok, is_success
from src.common.errors import RetriableError, ValidationError


def test_build_auth_fields_includes_expected_keys():
    class U:
        c_token = "c"
        u_token = "u"
        customer_no = "cust"
        passport_id = "pid"

    d = build_auth_fields(U(), include_passport=True, include_lowercase=True)
    assert d["CToken"] == "c"
    assert d["UToken"] == "u"
    assert d["CustomerNo"] == "cust"
    assert d["Passportid"] == "pid"
    assert d["ctoken"] == "c"
    assert d["utoken"] == "u"
    assert d["customerNo"] == "cust"
    assert d["deviceid"]


def test_normalize_helpers():
    payload = {"success": True, "errorCode": 0, "firstError": None}
    assert is_success(payload) is True
    assert is_empty_ok(payload) is True
    assert error_code(payload) == 0
    assert error_message(payload) == ""
    assert is_auth_error(payload) is False
    assert is_auth_error({"success": False, "firstError": "请登录"}) is True


def test_api_client_request_json_parses_json():
    class Sess:
        def request(self, **kwargs):
            r = requests.Response()
            r.status_code = 200
            r._content = b'{"ok": true}'
            return r

    c = ApiClient(session=Sess())
    assert c.get_json("https://example.com")["ok"] is True


def test_api_client_request_json_invalid_json_raises_validation():
    class Sess:
        def request(self, **kwargs):
            r = requests.Response()
            r.status_code = 200
            r._content = b"not json"
            return r

    c = ApiClient(session=Sess())
    with pytest.raises(ValidationError):
        c.get_json("https://example.com")


def test_api_client_request_network_error_raises_retriable():
    class Sess:
        def request(self, **kwargs):
            raise requests.exceptions.Timeout("t")

    c = ApiClient(session=Sess())
    with pytest.raises(RetriableError):
        c.get_json("https://example.com")

