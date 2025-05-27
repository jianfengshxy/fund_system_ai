import pytest
import logging
from unittest.mock import patch, Mock
from requests.exceptions import RequestException
import os
import sys

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from common.constant import DEFAULT_USER
from API.资产管理.AssetManager import GetMyAssetMainPartAsync

@pytest.fixture
def mock_response():
    mock = Mock()
    mock.json.return_value = {
        'Success': True,
        'ErrorCode': None,
        'Data': {
            'TotalAsset': 10000.00,
            'FundAsset': 8000.00,
            'CashAsset': 2000.00
        },
        'FirstError': None,
        'DebugError': None
    }
    return mock

def test_get_my_asset_success(caplog):
    """测试成功获取用户资产信息"""
    caplog.set_level(logging.INFO)
    
    response = GetMyAssetMainPartAsync(DEFAULT_USER)
    print(f"API响应结果: {response}")
    
    assert response.Success is True
    assert response.ErrorCode is 0
    assert float(response.Data['TotalValue']) > 0
    assert float(response.Data['HqbValue']) >= 0
    assert float(response.Data['TotalFundAsset']) >= 0
    assert response.FirstError is None
    assert response.DebugError is None
    
    print(f"资产数据验证通过: 总资产={response.Data['TotalValue']}, 基金资产={response.Data['TotalFundAsset']}")

def test_get_my_asset_http_error(caplog):
    """测试HTTP请求失败的情况"""
    caplog.set_level(logging.ERROR)
    
    with patch('requests.post', side_effect=RequestException('Connection error')):
        with pytest.raises(Exception) as exc_info:
            GetMyAssetMainPartAsync(DEFAULT_USER)
            
    assert '请求失败: Connection error' in str(exc_info.value)
    assert '请求失败: Connection error' in caplog.text

def test_get_my_asset_parse_error(caplog):
    """测试解析响应数据失败的情况"""
    caplog.set_level(logging.ERROR)
    mock = Mock()
    mock.json.return_value = {'Success': True, 'Data': None}
    
    with patch('requests.post', return_value=mock):
        with pytest.raises(Exception) as exc_info:
            GetMyAssetMainPartAsync(DEFAULT_USER)
            
    assert '解析响应数据失败: Data字段为空' in str(exc_info.value)
    assert '解析响应数据失败: Data字段为空' in caplog.text

def test_get_my_asset_error_response(caplog):
    """测试API返回错误响应的情况"""
    caplog.set_level(logging.INFO)
    mock = Mock()
    mock.json.return_value = {
        'Success': False,
        'ErrorCode': 'E001',
        'Data': None,
        'FirstError': '用户未登录',
        'DebugError': 'User not authenticated'
    }
    
    with patch('requests.post', return_value=mock):
        response = GetMyAssetMainPartAsync(DEFAULT_USER)
        
    assert response.Success is False
    assert response.ErrorCode == 'E001'
    assert response.Data is None
    assert response.FirstError == '用户未登录'
    assert response.DebugError == 'User not authenticated'