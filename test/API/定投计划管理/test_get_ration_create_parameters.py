import pytest
import requests
from unittest.mock import patch, MagicMock
import os
import sys
import logging

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.API.定投计划管理.SmartPlan import getRationCreateParameters
from src.domain.fund_plan import ApiResponse, RationCreateParameters, DiscountRate
from src.common.constant import DEFAULT_USER

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@pytest.fixture
def mock_ration_response():
    return {
        "Success": True,
        "ErrorCode": None,
        "Data": {
            "fundCode": "020256",
            "fundName": "国泰君安基金",
            "fundType": "1",
            "fundTypeTwo": "2",
            "fundTypeName": "股票型",
            "chargeTypeName": "前端收费",
            "fundRisk": "3",
            "fundRiskName": "中风险",
            "planStrategyList": ["策略1", "策略2"],
            "buyStrategyList": ["买入策略1"],
            "redeemStrategyList": ["赎回策略1"],
            "couponSelectList": [],
            "allowRedeemToHqb": True,
            "rationAutoPay": True,
            "tjdAutoPay": False,
            "naturalDate": "2025-04-15",
            "closeMarketTip": [],
            "enableDt": True,
            "financialType": "0",
            "majorFundCode": "",
            "isHKFund": False,
            "isHqbFund": False,
            "isFinancialFund": False,
            "isSpecialRateFund": False,
            "supportSubAccount": True,
            "minBusinLimit": "100",
            "maxBusinLimit": "100000",
            "discountRateList": [
                {
                    "lowerLimit": 0,
                    "upperLimit": 100000,
                    "rate": 1.5,
                    "strRate": "1.50%",
                    "discount": 0.1,
                    "strDiscount": "0.10",
                    "discountTips": "优惠说明"
                }
            ],
            "orderNo": "ORDER123",
            "forceRationCode": None,
            "isSale": True,
            "isSupportWitRation": True
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

def test_get_ration_create_parameters_success(mock_ration_response):
    with patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = mock_ration_response
        mock_get.return_value.raise_for_status = MagicMock()
        
        result = getRationCreateParameters(fund_code='020256', user=DEFAULT_USER)
        
        assert isinstance(result, ApiResponse)
        assert result.Success == True
        assert isinstance(result.Data, RationCreateParameters)
        assert result.Data.fundCode == '020256'
        assert result.Data.fundName == '国泰君安基金'
        assert result.Data.fundType == '1'
        assert result.Data.fundRisk == '3'
        assert len(result.Data.planStrategyList) == 2
        assert len(result.Data.discountRateList) == 1
        
        discount_rate = result.Data.discountRateList[0]
        assert isinstance(discount_rate, DiscountRate)
        assert discount_rate.lowerLimit == 0
        assert discount_rate.upperLimit == 100000
        assert discount_rate.rate == 1.5

def test_get_ration_create_parameters_http_error():
    with patch('requests.get') as mock_get:
        mock_get.side_effect = requests.exceptions.RequestException('网络错误')
        
        with pytest.raises(Exception) as exc_info:
            getRationCreateParameters(fund_code='020256', user=DEFAULT_USER)
        
        assert str(exc_info.value) == '请求失败: 网络错误'

def test_get_ration_create_parameters_parse_error():
    with patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = {"Success": True, "Data": None}
        mock_get.return_value.raise_for_status = MagicMock()
        
        with pytest.raises(Exception) as exc_info:
            getRationCreateParameters(fund_code='020256', user=DEFAULT_USER)
        
        assert '解析响应数据失败' in str(exc_info.value)

def test_get_ration_create_parameters_error_response(mock_error_response):
    with patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = mock_error_response
        mock_get.return_value.raise_for_status = MagicMock()
        
        result = getRationCreateParameters(fund_code='020256', user=DEFAULT_USER)
        
        assert isinstance(result, ApiResponse)
        assert result.Success == False
        assert result.ErrorCode == 'E001'
        assert result.FirstError == '请求失败'
        assert result.DebugError == '网络错误'

def test_get_ration_create_parameters_actual():
    """测试实际API调用获取定投创建参数"""
    fund_code = '020256'  # 假设的基金代码，可根据需要修改
    logger.info(f"开始测试实际获取定投创建参数，基金代码: {fund_code}")
    
    result = getRationCreateParameters(fund_code=fund_code, user=DEFAULT_USER)
    
    logger.info(f"API响应结果: Success={result.Success}, ErrorCode={result.ErrorCode}")
    assert isinstance(result, ApiResponse)
    assert result.Success, "API调用应成功"
    
    if result.Data:
        data = result.Data
        assert isinstance(data, RationCreateParameters)
        logger.info(f"基金代码: {data.fundCode}, 基金名称: {data.fundName}")
        logger.info(f"基金类型: {data.fundType}, 风险等级: {data.fundRisk}")
        logger.info(f"支持子账户: {data.supportSubAccount}, 自动支付: {data.rationAutoPay}")
        logger.info(f"最小/最大限额: {data.minBusinLimit} - {data.maxBusinLimit}")
        
        if data.discountRateList:
            for rate in data.discountRateList:
                logger.info(f"折扣率: 限额 {rate.lowerLimit}-{rate.upperLimit}, 费率 {rate.rate}%, 折扣 {rate.discount}")
        else:
            logger.info("无折扣率信息")
        
        assert data.fundCode == fund_code, "基金代码应匹配"
    else:
        logger.warning("无返回数据")
    
    logger.info("测试完成")

if __name__ == "__main__":
    test_get_ration_create_parameters_actual()