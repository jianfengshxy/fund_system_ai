from types import SimpleNamespace
import pytest
from src.service.交易管理.赎回基金 import sell_low_fee_shares, sell_usable_non_zero_fee_shares
from src.common.constant import DEFAULT_USER
from src.common.errors import RetriableError, ValidationError

def test_sell_low_fee_shares_bridge(monkeypatch):
    monkeypatch.setattr("src.service.交易管理.赎回基金.is_trading_time", lambda u: True)
    share = SimpleNamespace(availableVol=10.0, shareId="SID")
    # get_all_fund_info minimal
    class _Fund:
        fund_name = "FN"
    monkeypatch.setattr("src.service.基金信息.基金信息.get_all_fund_info", lambda u, c: _Fund())
    # 低费率份额设置为正值，避免 amount==0 早退
    monkeypatch.setattr("src.service.交易管理.赎回基金.get_low_fee_shares", lambda u, c: 5.0)
    # super_transfer retirable -> None path
    def _raise(*args, **kwargs):
        raise RetriableError("net")
    monkeypatch.setattr("src.service.交易管理.赎回基金.super_transfer", _raise)
    # SFT1Transfer validation -> None path
    monkeypatch.setattr("src.service.交易管理.赎回基金.SFT1Transfer", lambda *a, **k: None)
    # hqbMakeRedemption success mock
    monkeypatch.setattr("src.service.交易管理.赎回基金.hqbMakeRedemption", lambda *a, **k: SimpleNamespace(status=1))
    assert sell_low_fee_shares(DEFAULT_USER, "SUBNO", "000001", [share]) is not None

def test_sell_non_zero_fee_shares_bridge(monkeypatch):
    monkeypatch.setattr("src.service.交易管理.赎回基金.is_trading_time", lambda u: True)
    share = SimpleNamespace(availableVol=10.0, shareId="SID")
    class _Fund:
        fund_name = "FN"
    monkeypatch.setattr("src.service.基金信息.基金信息.get_all_fund_info", lambda u, c: _Fund())
    # fee usable shares
    monkeypatch.setattr("src.service.交易管理.赎回基金.get_usable_non_zero_fee_shares", lambda u, c: 5.0)
    # super_transfer failure then SFT1Transfer success
    monkeypatch.setattr("src.service.交易管理.赎回基金.super_transfer", lambda *a, **k: None)
    monkeypatch.setattr("src.service.交易管理.赎回基金.SFT1Transfer", lambda *a, **k: SimpleNamespace(status=1))
    assert sell_usable_non_zero_fee_shares(DEFAULT_USER, "SUBNO", "000001", [share]) is not None

def test_redeem_logging_extras_safe_without_mobile_phone(monkeypatch):
    monkeypatch.setattr("src.service.交易管理.赎回基金.is_trading_time", lambda u: True)
    # 构造无 mobile_phone 的用户
    user = SimpleNamespace(account="ACC001", customer_name="CN")
    share = SimpleNamespace(availableVol=10.0, shareId="SID")
    class _Fund:
        fund_name = "FN"
    monkeypatch.setattr("src.service.基金信息.基金信息.get_all_fund_info", lambda u, c: _Fund())
    monkeypatch.setattr("src.service.交易管理.赎回基金.get_low_fee_shares", lambda u, c: 5.0)
    # 直接成功路径，验证不会因缺少 mobile_phone 抛异常
    monkeypatch.setattr("src.service.交易管理.赎回基金.super_transfer", lambda *a, **k: SimpleNamespace(status=1))
    assert sell_low_fee_shares(user, "SUBNO", "000001", [share]) is not None
