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
        
        # 现在直接返回列表，不再是ApiResponse对象
        assert isinstance(result, list)
        
        # 验证过滤逻辑：只保留名称中包含字母"C"且不包含"债"的基金
        assert len(result) == 2  # 应该只有两个符合条件的基金
        
        # 验证排序逻辑：按product_rank从小到大排序
        assert result[0].product_rank < result[1].product_rank
        
        # 验证第一个基金的属性
        fund = result[0]
        assert isinstance(fund, FundInvestmentIndicator)
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
        
        # 现在直接返回列表
        assert isinstance(result, list)
        assert len(result) == 0  # 应该没有基金

def test_get_fund_investment_indicators_error(mock_error_response):
    """测试API返回错误的情况"""
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = mock_error_response
        mock_post.return_value.raise_for_status = MagicMock()
        
        # 当API返回错误时，函数应该抛出异常
        with pytest.raises(Exception) as exc_info:
            getFundInvestmentIndicators(DEFAULT_USER)
        
        # 验证异常信息包含错误详情
        assert "请求失败" in str(exc_info.value)

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
        result = getFundInvestmentIndicators(DEFAULT_USER, page_size=50)
        
        # 验证返回的是列表
        assert isinstance(result, list)
        
        # 验证请求中包含了正确的page_size参数
        _, kwargs = mock_post.call_args
        assert 'data' in kwargs
        assert kwargs['data']['pageSize'] == 50

def test_get_fund_investment_indicators_success_real():
    """测试真实调用获取加仓风向标基金信息"""
    result = getFundInvestmentIndicators(DEFAULT_USER)
    
    # 验证返回结果是列表
    assert isinstance(result, list)
    
    # 如果有数据，验证基金对象的属性
    if len(result) > 0:
        fund = result[0]
        assert hasattr(fund, 'fund_name')
        assert hasattr(fund, 'fund_code')
        assert hasattr(fund, 'fund_type')
        assert hasattr(fund, 'fund_sub_type')
        assert hasattr(fund, 'one_year_return')
        assert hasattr(fund, 'since_launch_return')
        assert hasattr(fund, 'update_time')
        assert hasattr(fund, 'product_rank')
        
        # 验证数据类型
        assert isinstance(fund.fund_name, str)
        assert isinstance(fund.fund_code, str)
        assert isinstance(fund.fund_type, str)
        assert isinstance(fund.fund_sub_type, str)
        assert isinstance(fund.one_year_return, (int, float))
        assert isinstance(fund.since_launch_return, (int, float))
        assert isinstance(fund.update_time, str)
        
        # 验证过滤逻辑：基金名称应该包含"C"且不包含"债"，且基金子类型不等于"002003"
        for fund_item in result:
            assert 'C' in fund_item.fund_name
            assert '债' not in fund_item.fund_name
            assert fund_item.fund_sub_type != "002003"
        
        # 验证排序逻辑：按product_rank从小到大排序
        if len(result) > 1:
            for i in range(len(result) - 1):
                assert result[i].product_rank <= result[i + 1].product_rank
    else:
        print("API调用成功但返回空列表")