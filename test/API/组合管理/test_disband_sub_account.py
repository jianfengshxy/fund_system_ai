import pytest
import requests
from unittest.mock import patch, MagicMock
import os
import sys

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.API.组合管理.SubAccountMrg import disbandSubAccount, getSubAccountNoByName, getSubAssetMultList
from src.domain.user import ApiResponse
from src.domain.sub_account.sub_account_response import SubAccountResponse
from src.common.constant import DEFAULT_USER

@pytest.fixture
def mock_response():
    return {
        "Success": True,
        "ErrorCode": None,
        "Data": {
            "SubAccountAppNo": "APP001",
            "UserId": "USER001",
            "LastCloseTime": "2025-04-15",
            "OpenState": 0,
            "SubAccountNoIdea": "IDEA001",
            "CustomizeProperty": None,
            "FollowedCustomerNo": None,
            "FollowedSubAccountNo": None,
            "Property": "P1",
            "ManualReviewState": 0,
            "Style": "S1",
            "CreateTime": "2025-04-15 10:00:00",
            "IsEnabled": False,
            "State": 0,
            "Name": "测试子账户",
            "Alias": None,
            "SubAccountNo": "SA001",
            "UpdateTime": "2025-04-15 11:00:00",
            "ManualReviewField": ""
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

@pytest.mark.skip(reason="手工指定调用")
def test_disband_sub_account_success():
    print("开始测试解散子账户")
    result = disbandSubAccount(user=DEFAULT_USER, sub_account_no=getSubAccountNoByName(user=DEFAULT_USER, name="测试子账户"))
    print(f"API响应结果: {result}")
    
    assert isinstance(result, ApiResponse)
    assert result.Success == True
    assert isinstance(result.Data, SubAccountResponse)
    print("基本响应数据验证通过")
    
    sub_account = result.Data
    print(f"子账户数据验证通过: sub_account_no={sub_account.sub_account_no}, state={sub_account.state}")

def test_disband_sub_account_http_error():
    with patch('requests.post') as mock_post:
        mock_post.side_effect = requests.exceptions.RequestException('网络错误')
        
        with pytest.raises(Exception) as exc_info:
            disbandSubAccount(user=DEFAULT_USER, sub_account_no="SA001")
        
        assert str(exc_info.value) == '请求失败: 网络错误'

def test_disband_sub_account_parse_error(mock_response):
    with patch('requests.post') as mock_post:
        # 返回无效的JSON数据结构
        mock_post.return_value.json.return_value = {"Success": True, "Data": None}
        mock_post.return_value.raise_for_status = MagicMock()
        
        with pytest.raises(Exception) as exc_info:
            disbandSubAccount(user=DEFAULT_USER, sub_account_no="SA001")
        
        assert '解析响应数据失败' in str(exc_info.value)

def test_disband_sub_account_error_response(mock_error_response):
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = mock_error_response
        mock_post.return_value.raise_for_status = MagicMock()
        
        result = disbandSubAccount(user=DEFAULT_USER, sub_account_no="SA001")
        
        assert isinstance(result, ApiResponse)
        assert result.Success == False
        assert result.ErrorCode == 'E001'
        assert result.FirstError == '请求失败'
        assert result.DebugError == '网络错误'