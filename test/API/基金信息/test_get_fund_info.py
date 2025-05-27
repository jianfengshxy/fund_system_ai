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

from src.API.基金信息.FundInfo import getFundInfo
from src.domain.fund.fund_info import FundInfo
from src.common.constant import DEFAULT_USER, FUND_CODE

@pytest.fixture
def mock_success_response():
    """模拟成功响应的数据"""
    return {
        "data": [{
            "NAV": 1.3188,
            "NAVCHGRT": 2.89,
            "MAXSG": 100000000000,
            "GZTIME": "2025-04-30 15:00",
            "FCODE": "020256",
            "SHORTNAME": "中欧中证机器人指数发起C",
            "GSZ": 1.319,
            "GSZZL": 2.91,
            "PDATE": "2025-04-30",
            "RSFUNDTYPE": "000",
            "SYL_Z": 2.37,
            "SYL_Y": -4.66,
            "SYL_3Y": 5.02,
            "SYL_6Y": 19.42,
            "SYL_1N": 20.3,
            "SYL_JN": 10.38,
            "ISBUY": "1"
        }],
        "success": True,
        "errorCode": 0
    }

@pytest.fixture
def mock_error_response():
    """模拟错误响应的数据"""
    return {
        "data": None,
        "success": False,
        "errorCode": 1001,
        "firstError": "获取基金信息失败"
    }

def test_get_fund_info_success():
    """测试成功获取基金信息"""
    fund_code = '004857'
    fund_name = '永赢先进制造智选混合发起C'
    result = getFundInfo(DEFAULT_USER, fund_code)
    assert result.fund_code == fund_code
    assert result.fund_name is not None
    assert result.nav is not None
    assert result.nav_change is not None
    
    print(f"获取到的基金信息: 基金代码={result.fund_code}, 基金名称={result.fund_name}, "
          f"净值={result.nav}, 涨跌幅={result.nav_change}, 是否可购买={result.can_purchase}")

def test_get_fund_info_network_error():
    """测试网络请求失败的情况"""
    with patch('requests.post') as mock_post:
        mock_post.side_effect = requests.exceptions.RequestException('网络错误')
        
        result = getFundInfo(DEFAULT_USER, FUND_CODE)
        assert result is None

def test_get_fund_info_api_error(mock_error_response):
    """测试API返回错误的情况"""
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = mock_error_response
        mock_post.return_value.raise_for_status = MagicMock()
        
        result = getFundInfo(DEFAULT_USER, FUND_CODE)
        assert result is None

def test_get_fund_info_empty_data():
    """测试返回空数据的情况"""
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = {"success": True, "data": []}
        mock_post.return_value.raise_for_status = MagicMock()
        
        result = getFundInfo(DEFAULT_USER, FUND_CODE)
        assert result is None