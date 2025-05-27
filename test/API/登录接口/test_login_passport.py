import pytest
import requests
from unittest.mock import patch, MagicMock
from API.登录接口.login import login_passport,login
from domain.user import User
from common.constant import DEFAULT_USER

@pytest.fixture
def mock_response():
    return {
        "Success": True,
        "ErrorCode": None,
        "Data": {
            "PassportUid": "test_passport_uid",
            "PassportCToken": "test_passport_ctoken",
            "PassportUToken": "test_passport_utoken"
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
        "FirstError": "Passport登录失败",
        "DebugError": "认证失败"
    }

@pytest.mark.skip(reason="暂时不需要此测试用例")
def test_login_passport_success():
    """测试Passport登录成功的情况"""
    print("开始测试Passport登录成功")
    # user = login("13918199137","sWX15706")
    result = login_passport(DEFAULT_USER)
    print(f"Passport登录响应结果: {result}")
    
    # assert isinstance(result, User)
    assert result.passport_uid is not None
    assert result.passport_ctoken is not None
    assert result.passport_utoken is not None
    print("Passport登录成功验证通过")

def test_login_passport_http_error():
    """测试HTTP请求失败的情况"""
    with patch('requests.post') as mock_post:
        mock_post.side_effect = requests.exceptions.RequestException('网络错误')
        
        result = login_passport(DEFAULT_USER)
        assert result is None

def test_login_passport_api_error(mock_error_response):
    """测试API返回错误的情况"""
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = mock_error_response
        mock_post.return_value.raise_for_status = MagicMock()
        
        result = login_passport(DEFAULT_USER)
        assert result is None

def test_login_passport_parse_error():
    """测试解析响应数据失败的情况"""
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = {"Success": True, "Data": None}
        mock_post.return_value.raise_for_status = MagicMock()
        
        result = login_passport(DEFAULT_USER)
        assert result is None