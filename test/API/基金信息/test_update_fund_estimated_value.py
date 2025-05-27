import pytest
import requests
import json
import os
import sys
from unittest.mock import patch, MagicMock

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.API.基金信息.FundInfo import updateFundEstimatedValue, getFundInfo
from src.domain.fund.fund_info import FundInfo
from src.common.constant import DEFAULT_USER

# 测试用的基金代码，使用终端输出中失败的基金代码
TEST_FUND_CODE = '011707'

@pytest.fixture
def mock_fund_info():
    """创建一个基金信息对象用于测试"""
    # 提供所有必要的参数
    fund_info = FundInfo(
        fund_code=TEST_FUND_CODE,
        fund_name="测试基金",
        fund_type="混合型",
        nav=1.2345,
        acc_nav=1.5678,
        nav_date="2025-05-20",
        nav_change=0.73,
        estimated_value=0.0,
        estimated_change=0.0,
        estimated_time="",
        week_return=1.2,
        month_return=2.3,
        three_month_return=3.4,
        six_month_return=4.5,
        year_return=5.6,
        this_year_return=6.7,
        max_purchase=100000.0,
        can_purchase=True,
        index_code="",
        tracking_error=0.0
    )
    return fund_info

@pytest.fixture
def mock_estimated_response():
    """模拟估值接口的成功响应"""
    return 'jsonpgz({"fundcode":"011707","name":"测试基金","jzrq":"2025-05-20","dwjz":"1.2345","gsz":"1.2456","gszzl":"0.90","gztime":"2025-05-21 15:00"});'

@pytest.fixture
def mock_frequency_capped_response():
    """模拟频率限制的响应"""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "514 Server Error: Frequency Capped for url: https://fundgz.1234567.com.cn/js/011707.js"
    )
    return mock_response

def test_update_fund_estimated_value_success(mock_fund_info, mock_estimated_response):
    """测试成功更新基金估值信息"""
    with patch('requests.get') as mock_get:
        # 设置模拟响应
        mock_response = MagicMock()
        mock_response.text = mock_estimated_response
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        # 调用函数
        updated_fund_info = updateFundEstimatedValue(mock_fund_info)
        
        # 验证结果
        assert updated_fund_info is not None
        assert updated_fund_info.estimated_value == 1.2456
        assert updated_fund_info.estimated_change == 0.90
        assert updated_fund_info.estimated_time == "2025-05-21 15:00"
        
        # 验证请求参数
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert f"https://fundgz.1234567.com.cn/js/{TEST_FUND_CODE}.js" in args[0]
        assert 'rt' in kwargs['params']
        assert kwargs['verify'] is False

def test_update_fund_estimated_value_retry_success(mock_fund_info, mock_estimated_response):
    """测试重试成功的情况"""
    with patch('requests.get') as mock_get:
        # 第一次请求失败，第二次成功
        mock_error_response = MagicMock()
        mock_error_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "514 Server Error: Frequency Capped"
        )
        
        mock_success_response = MagicMock()
        mock_success_response.text = mock_estimated_response
        mock_success_response.raise_for_status = MagicMock()
        
        mock_get.side_effect = [mock_error_response, mock_success_response]
        
        # 调用函数
        updated_fund_info = updateFundEstimatedValue(mock_fund_info)
        
        # 验证结果
        assert updated_fund_info is not None
        assert updated_fund_info.estimated_value == 1.2456
        assert updated_fund_info.estimated_change == 0.90
        
        # 验证重试次数
        assert mock_get.call_count == 2

def test_update_fund_estimated_value_all_retries_fail(mock_fund_info):
    """测试所有重试都失败的情况"""
    with patch('requests.get') as mock_get:
        # 所有请求都失败
        mock_get.side_effect = requests.exceptions.HTTPError(
            "514 Server Error: Frequency Capped"
        )
        
        # 调用函数
        updated_fund_info = updateFundEstimatedValue(mock_fund_info)
        
        # 验证结果
        assert updated_fund_info is None
        
        # 验证重试次数（最多3次）
        assert mock_get.call_count == 3

def test_update_fund_estimated_value_json_error(mock_fund_info):
    """测试JSON解析错误的情况"""
    with patch('requests.get') as mock_get:
        # 设置无效的JSON响应
        mock_response = MagicMock()
        mock_response.text = 'invalid json data'
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        # 调用函数
        updated_fund_info = updateFundEstimatedValue(mock_fund_info)
        
        # 验证结果
        assert updated_fund_info is None

def test_update_fund_estimated_value_network_error(mock_fund_info):
    """测试网络错误的情况"""
    with patch('requests.get') as mock_get:
        # 模拟网络错误
        mock_get.side_effect = requests.exceptions.ConnectionError("网络连接错误")
        
        # 调用函数
        updated_fund_info = updateFundEstimatedValue(mock_fund_info)
        
        # 验证结果
        assert updated_fund_info is None

def test_update_fund_estimated_value_timeout(mock_fund_info):
    """测试请求超时的情况"""
    with patch('requests.get') as mock_get:
        # 模拟请求超时
        mock_get.side_effect = requests.exceptions.Timeout("请求超时")
        
        # 调用函数
        updated_fund_info = updateFundEstimatedValue(mock_fund_info)
        
        # 验证结果
        assert updated_fund_info is None

def test_integration_with_real_fund():
    """集成测试：使用真实基金代码测试完整流程"""
    # 先获取基金信息
    fund_info = getFundInfo(DEFAULT_USER, TEST_FUND_CODE)
    
    if fund_info:
        # 更新估值信息
        updated_fund_info = updateFundEstimatedValue(fund_info)
        
        # 由于可能会遇到频率限制，这里不断言一定成功
        # 只验证基本信息保持不变
        if updated_fund_info:
            assert updated_fund_info.fund_code == TEST_FUND_CODE
            assert updated_fund_info.fund_name == fund_info.fund_name
            assert updated_fund_info.nav == fund_info.nav
            
            # 打印估值信息
            print(f"\n估值信息获取成功:")
            print(f"基金代码: {updated_fund_info.fund_code}")
            print(f"基金名称: {updated_fund_info.fund_name}")
            print(f"当前净值: {updated_fund_info.nav}")
            print(f"估算净值: {updated_fund_info.estimated_value}")
            print(f"估算涨跌: {updated_fund_info.estimated_change}%")
            print(f"估算时间: {updated_fund_info.estimated_time}")
        else:
            print("\n估值信息获取失败，可能是由于频率限制")
    else:
        pytest.skip("无法获取基金基本信息，跳过此测试")

if __name__ == "__main__":
    # 配置日志
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 直接运行测试
    pytest.main(["-v", __file__])