import pytest
from unittest.mock import patch, MagicMock
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from API.银行卡信息.CashBag import getCashBagAvailableShareV2
from domain.bank.bank import HqbBank
from common.constant import DEFAULT_USER

@pytest.fixture
def mock_success_response():
    """成功响应的模拟数据"""
    return {
        "Data": {
            "HqbBanks": [
                {
                    "PayPlusDesc": None,
                    "IsPayPlus": False,
                    "AccountNo": "cf02a8b1e52c458b9638555e23fb6911#020#hasbranch",
                    "BankCode": "020",
                    "ShowBankCode": "020",
                    "BankName": "平安银行",
                    "BankCardNo": "6230***********3400",
                    "BankCardType": "0",
                    "BankState": True,
                    "AccountState": 0,
                    "BankAvaVol": "1000.00",
                    "CurrentRealBalance": 1000.00,
                    "P1CRBalance": 0,
                    "P2CRBalance": 0,
                    "P3CRBalance": 0,
                    "P4CRBalance": 0,
                    "OpenTime": None,
                    "CreateTime": None,
                    "HasBranch": True,
                    "CanPayment": True,
                    "EnableTips": False,
                    "Tips": "",
                    "EnableChannelTips": False,
                    "ChannelTips": None,
                    "RechargeTitle": "余额不足别担心，银行卡充值后一键支付",
                    "Title": "银行卡充值活期宝，当日即可买基金",
                    "FontColor": "#FFFFFF",
                    "BgColor": "#FF6434",
                    "FastAvaVol": None,
                    "TradeFlow": "default",
                    "AmountCondition": None,
                    "HqbPayModeInfos": []
                }
            ]
        },
        "Success": True,
        "ErrorCode": 0
    }

@pytest.mark.parametrize("mock_response,expected_length", [
    ({"Success": True, "Data": {"HqbBanks": []}}, 0),
    ({"Success": False, "FirstError": "请求失败"}, 0),
    ({"Success": True, "Data": None}, 0),
])
@patch('requests.post')
def test_get_cash_bag_available_share_edge_cases(mock_post, mock_response, expected_length):
    """测试各种边界情况"""
    # 配置mock响应
    mock_resp = MagicMock()
    mock_resp.json.return_value = mock_response
    mock_post.return_value = mock_resp

    # 使用默认用户调用测试函数
    result = getCashBagAvailableShareV2(DEFAULT_USER)

    # 验证结果
    assert isinstance(result, list)
    assert len(result) == expected_length

def test_get_cash_bag_available_share_success():
    """测试成功获取活期宝银行卡列表"""
    result = getCashBagAvailableShareV2(DEFAULT_USER)

    # 验证结果
    assert isinstance(result, list)
    if len(result) > 0:
        bank = result[0]
        assert isinstance(bank, HqbBank)
        assert bank.BankName  # 验证银行名称不为空
        assert bank.BankCardNo  # 验证银行卡号不为空
        assert bank.BankCode  # 验证银行代码不为空
        assert isinstance(bank.BankState, bool)  # 验证银行状态是布尔值
        assert isinstance(bank.HasBranch, bool)  # 验证分行信息是布尔值
        
        print(f"\n获取到的银行卡信息：")
        print(f"银行名称: {bank.BankName}")
        print(f"银行卡号: {bank.BankCardNo}")
        print(f"账户号: {bank.AccountNo}")
        print(f"可用余额: {bank.BankAvaVol}")
        print(f"银行代码: {bank.BankCode}")
        print(f"银行状态: {bank.BankState}")
        print(f"是否有分行: {bank.HasBranch}")
    # assert len(result) == 1
    # assert isinstance(result[0], HqbBank)
    
    bank = result[0]
    assert bank.BankName == "工商银行"
    assert bank.BankCardNo == "6222***********8882"
    assert bank.AccountNo == "f12a70addec7458dae41369ac1005e5a#002#hasbranch"
    assert bank.BankState is True
    assert bank.HasBranch is True

@patch('requests.post')
def test_get_cash_bag_available_share_network_error(mock_post):
    """测试网络请求异常"""
    # 配置mock抛出异常
    mock_post.side_effect = Exception("网络连接错误")

    # 使用默认用户调用测试函数
    result = getCashBagAvailableShareV2(DEFAULT_USER)

    # 验证结果
    assert isinstance(result, list)
    assert len(result) == 0

@patch('requests.post')
def test_get_cash_bag_available_share_invalid_json(mock_post):
    """测试返回无效JSON数据"""
    # 配置mock响应抛出JSON解析异常
    mock_resp = MagicMock()
    mock_resp.json.side_effect = ValueError("Invalid JSON")
    mock_post.return_value = mock_resp

    # 使用默认用户调用测试函数
    result = getCashBagAvailableShareV2(DEFAULT_USER)

    # 验证结果
    assert isinstance(result, list)
    assert len(result) == 0