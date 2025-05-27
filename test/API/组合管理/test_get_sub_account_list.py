import pytest
import requests
from unittest.mock import patch, MagicMock
from API.组合管理.SubAccountMrg import getSubAccountList
from domain.user import ApiResponse
from domain.sub_account.sub_account import SubAccount
from common.constant import DEFAULT_USER
import sys
import os
from domain.sub_account.sub_account import SubAccount
from typing import List
# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
@pytest.fixture
def mock_success_response():
    return {
        "Success": True,
        "ErrorCode": None,
        "Data": {
            "SubAccounts": [
                {
                    "CustomerNo": "123456",
                    "SubAccountNo": "SA001",
                    "SubAccountName": "测试组合1",
                    "OpenFlag": 1,
                    "State": 0,
                    "AssetValue": "1000.00",
                    "SubAccountAlias": "测试别名",
                    "SubAccountStyle": "S1",
                    "CreateTime": "2023-01-01 12:00:00",
                    "FollowedCustomerNo": None,
                    "FollowedSubAccountNo": None,
                    "GroupType": "1",
                    "Score": "80",
                    "GroupTypes": [
                        {
                            "GroupTypeName": "稳健型",
                            "Color": "#FF0000"
                        }
                    ],
                    "IntervalProfitRate": "0.05",
                    "IntervalProfitRateName": "近一月",
                    "SubAccountExplain": "组合说明",
                    "OnWayTradeCount": 2,
                    "OnWayTradeDesc": "有在途交易",
                    "IsDissolving": False,
                    "TotalAmount": "1000.00",
                    "TotalProfit": "100.00",
                    "TotalProfitRate": "0.1"
                }
            ]
        },
        "FirstError": None,
        "DebugError": None
    }

@pytest.fixture
def mock_error_response():
    return {
        "Success": False,
        "ErrorCode": "E001",
        "Data": None,
        "FirstError": "请求失败",
        "DebugError": "网络错误"
    }

def test_get_sub_account_list_success():
    """测试获取子账户列表 - 成功场景"""
    print("开始测试获取子账户列表")
    
    result = getSubAccountList(user=DEFAULT_USER)
    print(f"API响应结果: {result}")
    
    assert isinstance(result, ApiResponse)
    assert result.Success == True
    assert isinstance(result.Data, list)
    print("基本响应数据验证通过")
    
    if len(result.Data) > 0:
        sub_account = result.Data[0]
        assert isinstance(sub_account, SubAccount)
        assert hasattr(sub_account, 'customer_no')
        assert hasattr(sub_account, 'sub_account_no')
        assert hasattr(sub_account, 'sub_account_name')
        print(f"子账户数据验证通过: sub_account_no={sub_account.sub_account_no}, name={sub_account.sub_account_name}")

def test_get_sub_account_list_http_error():
    """测试获取子账户列表 - HTTP错误场景"""
    with patch('requests.post') as mock_post:
        mock_post.side_effect = requests.exceptions.RequestException('网络错误')
        
        with pytest.raises(Exception) as exc_info:
            getSubAccountList(user=DEFAULT_USER)
        
        assert str(exc_info.value) == '请求失败: 网络错误'

def test_get_sub_account_list_parse_error(mock_success_response):
    """测试获取子账户列表 - 解析错误场景"""
    with patch('requests.post') as mock_post:
        # 返回无效的JSON数据结构
        mock_post.return_value.json.return_value = {"Success": True, "Data": None}
        mock_post.return_value.raise_for_status = MagicMock()
        
        with pytest.raises(Exception) as exc_info:
            getSubAccountList(user=DEFAULT_USER)
        
        assert '解析响应数据失败' in str(exc_info.value)

def test_get_sub_account_list_error_response(mock_error_response):
    """测试获取子账户列表 - 错误响应场景"""
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = mock_error_response
        mock_post.return_value.raise_for_status = MagicMock()
        
        result = getSubAccountList(user=DEFAULT_USER)
        
        assert isinstance(result, ApiResponse)
        assert result.Success == False
        assert result.ErrorCode == 'E001'
        assert result.FirstError == '请求失败'
        assert result.DebugError == '网络错误'

