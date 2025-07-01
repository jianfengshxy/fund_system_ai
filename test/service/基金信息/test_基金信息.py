import pytest
import os
import sys
import logging
from unittest.mock import patch, MagicMock

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# 导入被测试的模块
from src.service.基金信息.基金信息 import get_all_fund_info
from src.domain.fund.fund_info import FundInfo
from src.common.constant import DEFAULT_USER, FUND_CODE

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)d)')
logger = logging.getLogger(__name__)

# 测试用的基金代码
TEST_FUND_CODE = '016453'

@pytest.fixture
def mock_fund_info():
    """创建一个基金信息对象用于测试"""
    # 创建一个模拟的基金信息对象
    fund_info = MagicMock(spec=FundInfo)
    fund_info.fund_code = TEST_FUND_CODE
    fund_info.fund_name = "测试基金"
    fund_info.nav = 1.2345
    fund_info.nav_date = "2023-05-20"
    fund_info.nav_change = 0.73
    fund_info.acc_nav = 1.5678
    fund_info.estimated_value = None
    fund_info.estimated_change = None
    fund_info.estimated_time = None
    fund_info.month_return = 2.5
    return fund_info

@pytest.fixture
def mock_updated_fund_info(mock_fund_info):
    """创建一个更新了估值信息的基金信息对象"""
    fund_info = mock_fund_info
    fund_info.estimated_value = 1.2456
    fund_info.estimated_change = 0.90
    fund_info.estimated_time = "2023-05-21 15:00"
    return fund_info

def test_get_all_fund_info_from_cache():
    """测试从缓存中获取基金信息"""
    with patch('src.service.基金信息.基金信息.fund_info_cache') as mock_cache:
        # 设置缓存中已有基金信息
        mock_fund = MagicMock(spec=FundInfo)
        mock_fund.fund_code = TEST_FUND_CODE
        mock_fund.fund_name = "缓存基金"
        mock_cache.__contains__.return_value = True
        mock_cache.__getitem__.return_value = mock_fund
        
        # 调用函数
        result = get_all_fund_info(DEFAULT_USER, TEST_FUND_CODE)
        
        # 验证结果
        assert result is mock_fund
        assert result.fund_name == "缓存基金"
        mock_cache.__contains__.assert_called_once_with(TEST_FUND_CODE)
        mock_cache.__getitem__.assert_called_once_with(TEST_FUND_CODE)

def test_get_all_fund_info_basic_info_failure():
    """测试获取基金基础信息失败的情况"""
    with patch('src.service.基金信息.基金信息.fund_info_cache') as mock_cache, \
         patch('src.service.基金信息.基金信息.getFundInfo') as mock_get_fund_info:
        # 设置缓存中没有基金信息
        mock_cache.__contains__.return_value = False
        # 设置获取基金基础信息失败
        mock_get_fund_info.return_value = None
        
        # 调用函数
        result = get_all_fund_info(DEFAULT_USER, TEST_FUND_CODE)
        
        # 验证结果
        assert result is None
        mock_cache.__contains__.assert_called_once_with(TEST_FUND_CODE)
        mock_get_fund_info.assert_called_once_with(DEFAULT_USER, TEST_FUND_CODE)

def test_get_all_fund_info_success():
    """测试成功获取基金完整信息的情况（直接调用实际函数）"""
    # 直接调用函数获取基金信息
    fund_code = '016531'
    result = get_all_fund_info(DEFAULT_USER, fund_code)
    
    # 验证结果
    assert result is not None
    assert result.fund_code == fund_code
    assert result.fund_name is not None
    assert result.nav > 0
    
    # 验证基础信息
    assert result.fund_name is not None
    assert result.nav > 0
    
    # 打印获取到的信息（用于调试）
    logger.info(f"获取到的基金信息: {result.fund_name}({result.fund_code})")
    logger.info(f"净值: {result.nav}, 日期: {result.nav_date}")
    
    # 验证估值信息（可能为None，因为估值信息可能获取失败）
    if result.estimated_value is not None:
        logger.info(f"估值: {result.estimated_value}, 涨跌: {result.estimated_change}%, 时间: {result.estimated_time}")
    
    # 验证排名信息
    if hasattr(result, 'rank_30day') and result.rank_30day is not None:
        logger.info(f"30日排名: {result.rank_30day}")
    
    if hasattr(result, 'rank_100day') and result.rank_100day is not None:
        logger.info(f"100日排名: {result.rank_100day}")
    
    # 验证波动率信息
    if hasattr(result, 'volatility') and result.volatility is not None:
        logger.info(f"波动率: {result.volatility}")

    # 基金类型
    if hasattr(result, 'fund_type') and result.fund_type is not None:
        logger.info(f"基金类型: {result.fund_type}")
    
    # 返回结果，方便后续测试使用
    return result
    with patch('src.service.基金信息.基金信息.fund_info_cache') as mock_cache, \
         patch('src.service.基金信息.基金信息.getFundInfo') as mock_get_fund_info, \
         patch('src.service.基金信息.基金信息.updateFundEstimatedValue') as mock_update_estimated, \
         patch('src.service.基金信息.基金信息.get_nav_rank') as mock_get_nav_rank, \
         patch('src.service.基金信息.基金信息.get_fund_volatility_api') as mock_get_volatility:
        # 设置缓存中没有基金信息
        mock_cache.__contains__.return_value = False
        # 设置获取基金基础信息成功
        mock_get_fund_info.return_value = mock_fund_info
        # 设置更新估值信息成功
        mock_update_estimated.return_value = mock_updated_fund_info
        # 设置获取排名信息成功
        mock_get_nav_rank.side_effect = [10, 50]  # 30日排名10，100日排名50
        # 设置获取波动率信息成功
        mock_get_volatility.return_value = (0.01, 0.0025, 0.05)  # 均值，方差，波动率
        
        # 调用函数
        result = get_all_fund_info(DEFAULT_USER, TEST_FUND_CODE)
        
        # 验证结果
        assert result is mock_updated_fund_info
        assert result.rank_30day == 10
        assert result.rank_100day == 50
        assert result.volatility == 0.05
        
        # 验证函数调用
        mock_cache.__contains__.assert_called_once_with(TEST_FUND_CODE)
        mock_get_fund_info.assert_called_once_with(DEFAULT_USER, TEST_FUND_CODE)
        mock_update_estimated.assert_called_once_with(mock_fund_info)
        assert mock_get_nav_rank.call_count == 2
        mock_get_volatility.assert_called_once_with(DEFAULT_USER, mock_updated_fund_info, 30)
        
        # 验证缓存更新
        mock_cache.__setitem__.assert_called_once_with(TEST_FUND_CODE, mock_updated_fund_info)

def test_get_all_fund_info_partial_failure(mock_fund_info):
    """测试部分信息获取失败的情况"""
    with patch('src.service.基金信息.基金信息.fund_info_cache') as mock_cache, \
         patch('src.service.基金信息.基金信息.getFundInfo') as mock_get_fund_info, \
         patch('src.service.基金信息.基金信息.updateFundEstimatedValue') as mock_update_estimated, \
         patch('src.service.基金信息.基金信息.get_nav_rank') as mock_get_nav_rank, \
         patch('src.service.基金信息.基金信息.get_fund_volatility_api') as mock_get_volatility:
        # 设置缓存中没有基金信息
        mock_cache.__contains__.return_value = False
        # 设置获取基金基础信息成功
        mock_get_fund_info.return_value = mock_fund_info
        # 设置更新估值信息失败
        mock_update_estimated.return_value = None
        # 设置获取排名信息部分失败
        mock_get_nav_rank.side_effect = [None, 50]  # 30日排名获取失败，100日排名50
        # 设置获取波动率信息失败
        mock_get_volatility.return_value = None
        
        # 调用函数
        result = get_all_fund_info(DEFAULT_USER, TEST_FUND_CODE)
        
        # 验证结果
        assert result is mock_fund_info  # 返回原始基金信息
        assert not hasattr(result, 'rank_30day') or result.rank_30day is None
        assert result.rank_100day == 50
        assert not hasattr(result, 'volatility') or result.volatility is None
        
        # 验证函数调用
        mock_cache.__contains__.assert_called_once_with(TEST_FUND_CODE)
        mock_get_fund_info.assert_called_once_with(DEFAULT_USER, TEST_FUND_CODE)
        mock_update_estimated.assert_called_once_with(mock_fund_info)
        assert mock_get_nav_rank.call_count == 2
        mock_get_volatility.assert_called_once_with(DEFAULT_USER, mock_fund_info, 30)
        
        # 验证缓存更新
        mock_cache.__setitem__.assert_called_once_with(TEST_FUND_CODE, mock_fund_info)

def test_get_all_fund_info_exception_handling(mock_fund_info):
    """测试异常处理情况"""
    with patch('src.service.基金信息.基金信息.fund_info_cache') as mock_cache, \
         patch('src.service.基金信息.基金信息.getFundInfo') as mock_get_fund_info, \
         patch('src.service.基金信息.基金信息.updateFundEstimatedValue') as mock_update_estimated, \
         patch('src.service.基金信息.基金信息.get_nav_rank') as mock_get_nav_rank, \
         patch('src.service.基金信息.基金信息.get_fund_volatility_api') as mock_get_volatility:
        # 设置缓存中没有基金信息
        mock_cache.__contains__.return_value = False
        # 设置获取基金基础信息成功
        mock_get_fund_info.return_value = mock_fund_info
        # 设置更新估值信息抛出异常
        mock_update_estimated.side_effect = Exception("估值更新异常")
        # 设置获取排名信息抛出异常
        mock_get_nav_rank.side_effect = Exception("排名获取异常")
        # 设置获取波动率信息抛出异常
        mock_get_volatility.side_effect = Exception("波动率计算异常")
        
        # 调用函数
        result = get_all_fund_info(DEFAULT_USER, TEST_FUND_CODE)
        
        # 验证结果 - 即使有异常，函数也应该返回基础信息
        assert result is mock_fund_info
        
        # 验证函数调用
        mock_cache.__contains__.assert_called_once_with(TEST_FUND_CODE)
        mock_get_fund_info.assert_called_once_with(DEFAULT_USER, TEST_FUND_CODE)
        mock_update_estimated.assert_called_once_with(mock_fund_info)
        assert mock_get_nav_rank.call_count == 2
        mock_get_volatility.assert_called_once_with(DEFAULT_USER, mock_fund_info, 30)
        
        # 验证缓存更新
        mock_cache.__setitem__.assert_called_once_with(TEST_FUND_CODE, mock_fund_info)

if __name__ == "__main__":
    # 直接运行测试
    test_get_all_fund_info_success()