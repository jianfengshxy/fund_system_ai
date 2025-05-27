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

from src.API.定投计划管理.SmartPlan import getFundRations
from src.domain.fund_plan import ApiResponse, FundPlan
from src.common.constant import DEFAULT_USER

@pytest.fixture
def mock_response():
    return {
        "Success": True,
        "ErrorCode": None,
        "Data": {
            "data": [
                {
                    "planId": "12345",
                    "fundCode": "020256",
                    "fundName": "国泰君安基金",
                    "executedAmount": "1000",
                    "executedTime": 1650000000,
                    "planState": "1",
                    "planExtendStatus": "0",
                    "planType": "1",
                    "nextDeductDescription": "每月15日定投",
                    "periodType": 1,
                    "periodValue": 15,
                    "amount": "100",
                    "nextDeductDate": "2025-04-15",
                    "bankCode": "0001",
                    "shortBankCardNo": "1234",
                    "payType": 1
                }
            ]
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

def test_get_fund_rations_success():
    print("开始测试获取定投计划列表")
    
    result = getFundRations(user=DEFAULT_USER)
    print(f"API响应结果: {result}")
    
    assert isinstance(result, ApiResponse)
    assert result.Success == True
    assert isinstance(result.Data, list)
    print("基本响应数据验证通过")
    
    if len(result.Data) > 0:
        plan = result.Data[0]
        assert isinstance(plan, FundPlan)
        assert plan.planId is not None
        assert plan.fundCode is not None
        assert plan.fundName is not None
        assert plan.planState is not None
        assert plan.planType is not None
        print(f"计划数据验证通过: planId={plan.planId}, fundCode={plan.fundCode}, fundName={plan.fundName}")
    else:
        print("未找到任何定投计划数据")

def test_get_fund_rations_http_error():
    with patch('requests.post') as mock_post:
        mock_post.side_effect = requests.exceptions.RequestException('网络错误')
        
        with pytest.raises(Exception) as exc_info:
            getFundRations(user=DEFAULT_USER)
        
        assert str(exc_info.value) == '请求失败: 网络错误'

def test_get_fund_rations_parse_error():
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = {"Success": True, "Data": None}
        mock_post.return_value.raise_for_status = MagicMock()
        
        with pytest.raises(Exception) as exc_info:
            getFundRations(user=DEFAULT_USER)
        
        assert '解析响应数据失败' in str(exc_info.value)

def test_get_fund_rations_error_response(mock_error_response):
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = mock_error_response
        mock_post.return_value.raise_for_status = MagicMock()
        
        result = getFundRations(user=DEFAULT_USER)
        
        assert isinstance(result, ApiResponse)
        assert result.Success == False
        assert result.ErrorCode == 'E001'
        assert result.FirstError == '请求失败'
        assert result.DebugError == '网络错误'