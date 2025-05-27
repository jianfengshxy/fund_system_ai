import pytest
import requests
from unittest.mock import patch, MagicMock
from API.组合管理.SubAccountMrg import createSubAccount
from domain.user import ApiResponse
from domain.sub_account.sub_account_response import SubAccountResponse
from common.constant import DEFAULT_USER

@pytest.fixture
def mock_response():
    return {
        "Success": True,
        "ErrorCode": None,
        "Data": {
            "SubAccountAppNo": "APP001",
            "UserId": "USER001",
            "LastCloseTime": "2025-04-15",
            "OpenState": 1,
            "SubAccountNoIdea": "IDEA001",
            "CustomizeProperty": None,
            "FollowedCustomerNo": None,
            "FollowedSubAccountNo": None,
            "Property": "P1",
            "ManualReviewState": 0,
            "Style": "S1",
            "CreateTime": "2025-04-15 10:00:00",
            "IsEnabled": True,
            "State": 1,
            "Name": "测试子账户",
            "Alias": None,
            "SubAccountNo": "SA001",
            "UpdateTime": "2025-04-15 10:00:00",
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
def test_create_sub_account_success():
    print("开始测试创建子账户")
    
    result = createSubAccount(user=DEFAULT_USER, name="测试子账户", style="S1")
    print(f"API响应结果: {result}")
    
    assert isinstance(result, ApiResponse)
    assert result.Success == True
    assert isinstance(result.Data, SubAccountResponse)
    print("基本响应数据验证通过")
    
    sub_account = result.Data
    assert sub_account.open_state == 1
    assert sub_account.style == "激进型"
    assert sub_account.name == "测试子账户"
    print(f"子账户数据验证通过: sub_account_no={sub_account.sub_account_no}, name={sub_account.name}")

def test_create_sub_account_http_error():
    with patch('requests.post') as mock_post:
        mock_post.side_effect = requests.exceptions.RequestException('网络错误')
        
        with pytest.raises(Exception) as exc_info:
            createSubAccount(user=DEFAULT_USER, name="测试子账户")
        
        assert str(exc_info.value) == '请求失败: 网络错误'

def test_create_sub_account_parse_error(mock_response):
    with patch('requests.post') as mock_post:
        # 返回无效的JSON数据结构
        mock_post.return_value.json.return_value = {"Success": True, "Data": None}
        mock_post.return_value.raise_for_status = MagicMock()
        
        with pytest.raises(Exception) as exc_info:
            createSubAccount(user=DEFAULT_USER, name="测试子账户")
        
        assert '解析响应数据失败' in str(exc_info.value)

def test_create_sub_account_error_response(mock_error_response):
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = mock_error_response
        mock_post.return_value.raise_for_status = MagicMock()
        
        result = createSubAccount(user=DEFAULT_USER, name="测试子账户")
        
        assert isinstance(result, ApiResponse)
        assert result.Success == False
        assert result.ErrorCode == 'E001'
        assert result.FirstError == '请求失败'
        assert result.DebugError == '网络错误'