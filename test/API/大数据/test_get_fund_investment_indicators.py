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

# 修改导入路径，使用正确的导入路径
from src.API.大数据.加仓风向标 import getFundInvestmentIndicators
from src.domain.fund_plan import ApiResponse
from src.domain.fund.fund_investment_indicator import FundInvestmentIndicator
from src.common.constant import DEFAULT_USER

@pytest.fixture
def mock_response():
    return {
        "success": True,
        "errorCode": None,
        "data": {
            "9": [
                {
                    "SHORTNAME": "测试基金C",
                    "RSFUNDTYPE": "混合型",
                    "RSBTYPE": "灵活配置型",
                    "SYL_1N": 15.23,
                    "SYL_LN": 50.45,
                    "FCODE": "123456",
                    "EUTIME": "2023-04-15 10:00:00",
                    "PRODUCT_RANK": 1
                },
                {
                    "SHORTNAME": "另一个基金C",
                    "RSFUNDTYPE": "股票型",
                    "RSBTYPE": "普通股票型",
                    "SYL_1N": 12.34,
                    "SYL_LN": 45.67,
                    "FCODE": "654321",
                    "EUTIME": "2023-04-15 11:00:00",
                    "PRODUCT_RANK": 2
                },
                {
                    "SHORTNAME": "债券基金C",
                    "RSFUNDTYPE": "债券型",
                    "RSBTYPE": "普通债券型",
                    "SYL_1N": 5.67,
                    "SYL_LN": 20.34,
                    "FCODE": "789012",
                    "EUTIME": "2023-04-15 12:00:00",
                    "PRODUCT_RANK": 3
                },
                {
                    "SHORTNAME": "普通基金",
                    "RSFUNDTYPE": "混合型",
                    "RSBTYPE": "灵活配置型",
                    "SYL_1N": 10.11,
                    "SYL_LN": 30.22,
                    "FCODE": "345678",
                    "EUTIME": "2023-04-15 13:00:00",
                    "PRODUCT_RANK": 4
                }
            ]
        },
        "firstError": None,
        "hasWrongToken": None
    }

@pytest.fixture
def mock_error_response():
    return {
        "success": False,
        "errorCode": "E001",
        "data": None,
        "firstError": "请求失败",
        "hasWrongToken": "认证失败"
    }

@pytest.fixture
def mock_empty_response():
    return {
        "success": True,
        "errorCode": None,
        "data": {
            "9": []
        },
        "firstError": None,
        "hasWrongToken": None
    }

def test_get_fund_investment_indicators_success(mock_response):
    """测试成功获取加仓风向标基金信息"""
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = mock_response
        mock_post.return_value.raise_for_status = MagicMock()
        
        result = getFundInvestmentIndicators(DEFAULT_USER)
        
        # assert isinstance(result, ApiResponse)
        assert result.Success == True
        # assert isinstance(result.Data, list)
        
        # 验证过滤逻辑：只保留名称中包含字母"C"且不包含"债"的基金
        assert len(result.Data) == 2  # 应该只有两个符合条件的基金
        
        # 验证排序逻辑：按product_rank从小到大排序
        assert result.Data[0].product_rank < result.Data[1].product_rank
        
        # 验证第一个基金的属性
        fund = result.Data[0]
        # assert isinstance(fund, FundInvestmentIndicator)
        assert fund.fund_name == "测试基金C"
        assert fund.fund_code == "123456"
        assert fund.fund_type == "混合型"
        assert fund.fund_sub_type == "灵活配置型"
        assert fund.one_year_return == 15.23
        assert fund.since_launch_return == 50.45
        assert fund.update_time == "2023-04-15 10:00:00"
        assert fund.product_rank == 1

def test_get_fund_investment_indicators_empty(mock_empty_response):
    """测试获取空的加仓风向标基金信息"""
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = mock_empty_response
        mock_post.return_value.raise_for_status = MagicMock()
        
        result = getFundInvestmentIndicators(DEFAULT_USER)
        
        # assert isinstance(result, ApiResponse)
        assert result.Success == True
        # assert isinstance(result.Data, list)
        assert len(result.Data) == 0  # 应该没有基金

def test_get_fund_investment_indicators_error(mock_error_response):
    """测试API返回错误的情况"""
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = mock_error_response
        mock_post.return_value.raise_for_status = MagicMock()
        
        result = getFundInvestmentIndicators(DEFAULT_USER)
        
        # assert isinstance(result, ApiResponse)
        assert result.Success == False
        assert result.ErrorCode == "E001"
        assert result.FirstError == "请求失败"
        assert result.DebugError == "认证失败"

def test_get_fund_investment_indicators_http_error():
    """测试HTTP请求失败的情况"""
    with patch('requests.post') as mock_post:
        mock_post.side_effect = requests.exceptions.RequestException('网络错误')
        
        with pytest.raises(Exception) as exc_info:
            getFundInvestmentIndicators(DEFAULT_USER)
        
        assert str(exc_info.value) == '请求失败: 网络错误'

def test_get_fund_investment_indicators_parse_error():
    """测试解析响应数据失败的情况"""
    with patch('requests.post') as mock_post:
        # 返回无效的JSON数据结构
        mock_post.return_value.json.return_value = {"success": True, "data": None}
        mock_post.return_value.raise_for_status = MagicMock()
        
        with pytest.raises(Exception) as exc_info:
            getFundInvestmentIndicators(DEFAULT_USER)
        
        assert '解析响应数据失败' in str(exc_info.value)

def test_get_fund_investment_indicators_with_page_size():
    """测试指定页面大小参数"""
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = {
            "success": True,
            "data": {"9": []}
        }
        mock_post.return_value.raise_for_status = MagicMock()
        
        # 调用函数时指定page_size参数
        getFundInvestmentIndicators(DEFAULT_USER, page_size=50)
        
        # 验证请求中包含了正确的page_size参数
        _, kwargs = mock_post.call_args
        assert 'data' in kwargs
        assert kwargs['data']['pageSize'] == 50