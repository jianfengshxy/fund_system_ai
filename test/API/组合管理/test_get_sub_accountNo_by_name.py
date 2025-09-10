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

from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.domain.user import ApiResponse
from src.domain.sub_account.sub_asset_mult_list_response import SubAssetMultListResponse, SubAccountGroup
from src.common.constant import DEFAULT_USER

@pytest.fixture
def mock_success_response():
    return {
        "Success": True,
        "ErrorCode": None,
        "Data": {
            "sub_bank_state": "",
            "group_card_tip": "",
            "sub_account_remark": "",
            "update": False,
            "ListGroup": [
                {
                    "OpenFlag": "1",
                    "IsDissolving": False,
                    "RaceId": None,
                    "OnWayTradeCount": 0,
                    "OnWayTradeDesc": None,
                    "SubAccountNo": "SA001",
                    "GroupName": "测试组合1",
                    "GroupType": "1",
                    "TotalProfit": "100.00",
                    "TotalProfitRate": "0.1",
                    "TotalAmount": "1000.00",
                    "TotalAmountDecimal": 1000.00,
                    "DayProfit": "10.00",
                    "Comment": None,
                    "Score": "80",
                    "FundUpdating": False,
                    "ToOrYesDayProfit": False,
                    "ListProfit": None,
                    "GroupTypes": [],
                    "IntervalProfitRate": "0.05",
                    "IntervalProfitRateName": "近一月",
                    "SubAccountExplain": None,
                    "FollowedSubAccountNo": None
                }
            ]
        },
        "FirstError": None,
        "DebugError": None
    }

@pytest.fixture
def mock_empty_response():
    return {
        "Success": True,
        "ErrorCode": None,
        "Data": {
            "sub_bank_state": "",
            "group_card_tip": "",
            "sub_account_remark": "",
            "update": False,
            "ListGroup": [],
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

def test_get_sub_account_no_by_name_success():
    print("开始测试根据组合名称获取组合编号 - 成功场景")
    
    result = getSubAccountNoByName(user=DEFAULT_USER, name="SmartFund")
    print(f"获取到的组合编号: {result}")
    
    assert result is not None
    assert isinstance(result, str)
    assert len(result) > 0
    print(f"验证通过: 成功获取到组合编号 {result}")

def test_get_sub_account_no_by_name_not_found(mock_success_response):
    print("开始测试根据组合名称获取组合编号 - 未找到场景")
    
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = mock_success_response
        mock_post.return_value.raise_for_status = MagicMock()
        
        result = getSubAccountNoByName(user=DEFAULT_USER, name="不存在的组合")
        print(f"获取到的组合编号: {result}")
        
        assert result is None

def test_get_sub_account_no_by_name_empty_list(mock_empty_response):
    print("开始测试根据组合名称获取组合编号 - 空列表场景")
    
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = mock_empty_response
        mock_post.return_value.raise_for_status = MagicMock()
        
        result = getSubAccountNoByName(user=DEFAULT_USER, name="测试组合1")
        print(f"获取到的组合编号: {result}")
        
        assert result is None

def test_get_sub_account_no_by_name_error(mock_error_response):
    print("开始测试根据组合名称获取组合编号 - 错误响应场景")
    
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = mock_error_response
        mock_post.return_value.raise_for_status = MagicMock()
        
        result = getSubAccountNoByName(user=DEFAULT_USER, name="测试组合1")
        print(f"获取到的组合编号: {result}")
        
        assert result is None


def test_get_low_risk_portfolio_id():
    print("开始测试获取低风险组合的组合编号")
    
    result = getSubAccountNoByName(user=DEFAULT_USER, name="低风险组合")
    print(f"获取到的低风险组合编号: {result}")
    
    assert result is not None
    assert isinstance(result, str)
    assert len(result) > 0
    print(f"验证通过: 成功获取到低风险组合编号 {result}")
    
    return result

if __name__ == "__main__":
    # 直接运行测试获取低风险组合的组合编号
    print("直接运行获取低风险组合的组合编号测试")
    portfolio_id = test_get_low_risk_portfolio_id()
    print(f"低风险组合的组合编号: {portfolio_id}")