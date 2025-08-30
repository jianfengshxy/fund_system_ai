import pytest
import requests
from unittest.mock import patch, MagicMock
from src.API.登录接口.login import inference_passport_for_bind, login
from domain.user.User import User  # 修改这行，直接从User.py导入User类
from common.constant import DEFAULT_USER

@pytest.fixture
def mock_response():
    return {
        "Success": True,
        "ErrorCode": None,
        "Data": {
            "Passport": {
                "UID": "test_passport_uid",
                "CToken": "test_passport_ctoken",
                "UToken": "test_passport_utoken"
            }
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
        "FirstError": "获取Passport绑定信息失败",
        "DebugError": "认证失败"
    }

def test_inference_passport_for_bind_success():
    """测试获取Passport绑定信息成功的情况"""
    print("开始测试获取Passport绑定信息成功")
    # user = login("13918199137", "sWX15706")
    result = inference_passport_for_bind(DEFAULT_USER)
    print(f"Passport绑定信息响应结果: {result}")
    
    assert isinstance(result, User)
    assert result.passport_id is not None
    assert result.passport_uid is not None
    assert result.passport_ctoken is not None
    assert result.passport_utoken is not None
    print("获取Passport绑定信息成功验证通过")

def test_inference_passport_for_bind_http_error():
    """测试HTTP请求失败的情况"""
    with patch('requests.post') as mock_post:
        mock_post.side_effect = requests.exceptions.RequestException('网络错误')
        
        result = inference_passport_for_bind(DEFAULT_USER)
        assert result is None

def test_inference_passport_for_bind_api_error(mock_error_response):
    """测试API返回错误的情况"""
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = mock_error_response
        mock_post.return_value.raise_for_status = MagicMock()
        
        result = inference_passport_for_bind(DEFAULT_USER)
        assert result is None

def test_inference_passport_for_bind_empty_data():
    """测试返回数据为空的情况"""
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = {"Success": True, "Data": None}
        mock_post.return_value.raise_for_status = MagicMock()
        
        result = inference_passport_for_bind(DEFAULT_USER)
        assert result is None

def test_inference_passport_for_bind_empty_passport():
    """测试返回的Passport数据为空的情况"""
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = {"Success": True, "Data": {"Passport": None}}
        mock_post.return_value.raise_for_status = MagicMock()
        
        result = inference_passport_for_bind(DEFAULT_USER)
        assert result is None

def test_inference_passport_for_bind_type_error():
    """测试更新用户对象时发生类型错误的情况"""
    # 创建一个错误的用户信息
    invalid_user = User(
        account="invalid_account",
        password="invalid_password"
    )
    invalid_user.customer_no = "invalid_customer_no"
    invalid_user.c_token = "invalid_token"
    invalid_user.u_token = "invalid_token"
    
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = {
            "Success": True,
            "Data": {
                "Passport": {
                    "UID": None,  # 使用None而不是字符串来触发TypeError
                    "CToken": None,
                    "UToken": None
                }
            }
        }
        mock_post.return_value.raise_for_status = MagicMock()
        
        result = inference_passport_for_bind(invalid_user)
        # assert result is None