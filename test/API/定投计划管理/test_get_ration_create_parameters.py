import pytest
import requests
from unittest.mock import patch, MagicMock
from API.定投计划管理.SmartPlan import getRationCreateParameters
from domain.fund_plan import ApiResponse, RationCreateParameters, DiscountRate
from common.constant import DEFAULT_USER

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