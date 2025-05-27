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

from src.API.定投计划管理.SmartPlan import getFundPlanList
from src.domain.fund_plan import ApiResponse, FundPlanResponse, PageInfo, FundPlan
from src.common.constant import DEFAULT_USER, FUND_CODE
from src.API.登录接口.login import inference_passport_for_bind, login

@pytest.fixture
def mock_response():
    return {
        "Success": True,
        "ErrorCode": None,
        "Data": {
            "fundCode": "020256",
            "fundName": "国泰君安基金",
            "pageInfo": {
                "pageIndex": 1,
                "pageSize": 100,
                "currPageSize": 1,
                "totalPage": 1,
                "totalSize": 1,
                "extraData": None,
                "data": [
                    {
                        "planId": "12345",
                        "planState": "1",
                        "planExtendStatus": "0",
                        "planType": "1",
                        "planConfigId": "67890",
                        "executedTime": 1650000000,
                        "executedAmount": "1000",
                        "nextDeductDescription": "每月15日定投",
                        "subAcctId": "ACC001",
                        "subAcctName": "我的账户"
                    }
                ]
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
        "FirstError": "请求失败",
        "DebugError": "网络错误"
    }

def test_get_fund_plan_list_success():
    print(f"开始测试获取基金计划列表，基金代码: 021740")
    # test_user = login("13918199137", "sWX15706")
    # test_user = inference_passport_for_bind(test_user)
    result = getFundPlanList(fund_code='021740', user=DEFAULT_USER)
    # result = getFundPlanList(fund_code='021740', user=test_user)
    print(f"API响应结果: {result}")
    
    assert isinstance(result, ApiResponse)
    assert result.Success == True
    assert isinstance(result.Data, FundPlanResponse)
    assert result.Data.fundCode == '021740'
    print("基本响应数据验证通过")
    
    page_info = result.Data.pageInfo
    assert isinstance(page_info, PageInfo)
    assert page_info.pageIndex >= 1
    assert page_info.pageSize == 100
    print(f"分页信息验证通过: pageIndex={page_info.pageIndex}, pageSize={page_info.pageSize}")
    
    if len(page_info.data) > 0:
        plan = page_info.data[0]
        assert isinstance(plan, FundPlan)
        assert plan.planId is not None
        assert plan.planState is not None
        print(f"计划数据验证通过: planId={plan.planId}, planState={plan.planState}")
    else:
        print("未找到任何计划数据")

def test_get_fund_plan_list_http_error():
    with patch('requests.get') as mock_get:
        mock_get.side_effect = requests.exceptions.RequestException('网络错误')
        
        with pytest.raises(Exception) as exc_info:
            getFundPlanList(fund_code='020256', user=DEFAULT_USER)
        
        assert str(exc_info.value) == '请求失败: 网络错误'

def test_get_fund_plan_list_error_response(mock_error_response):
    with patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = mock_error_response
        mock_get.return_value.raise_for_status = MagicMock()
        
        result = getFundPlanList(fund_code='020256', user=DEFAULT_USER)
        
        assert isinstance(result, ApiResponse)
        assert result.Success == False
        assert result.ErrorCode == 'E001'
        assert result.FirstError == '请求失败'
        assert result.DebugError == '网络错误'