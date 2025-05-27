import pytest
import requests
from unittest.mock import patch, MagicMock
from API.组合管理.SubAccountMrg import getSubAssetMultList
from domain.user import ApiResponse
from domain.sub_account.sub_asset_mult_list_response import SubAssetMultListResponse, SubAccountGroup, GroupType
from common.constant import DEFAULT_USER

@pytest.fixture
def mock_response():
    return {
        "Success": True,
        "ErrorCode": None,
        "Data": {
            "SubBankState": "1",
            "GroupCardTip": "组合提示",
            "SubAccountRemark": "备注信息",
            "Update": False,
            "SubAccountAsset": "100000.00",
            "HasConditionTrade": False,
            "ConditionTradeAmount": "0.00",
            "ConditionTradeProfit": "0.00",
            "ConditionTradeToOrYesDayProfit": False,
            "BaseAccountAmount": "50000.00",
            "YesterDayProfit": "100.00",
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
                    "TotalProfit": "1000.00",
                    "TotalProfitRate": "0.1",
                    "TotalAmount": "11000.00",
                    "TotalAmountDecimal": 11000.00,
                    "DayProfit": "50.00",
                    "Comment": None,
                    "Score": "80",
                    "FundUpdating": False,
                    "ToOrYesDayProfit": False,
                    "ListProfit": None,
                    "GroupTypes": [
                        {
                            "GroupTypeName": "稳健型",
                            "Color": "#FF0000"
                        }
                    ],
                    "IntervalProfitRate": "0.05",
                    "IntervalProfitRateName": "近一月",
                    "SubAccountExplain": None,
                    "FollowedSubAccountNo": None
                }
            ],
            "ToOrYesDayProfit": False,
            "SubTotalAmount": "150000.00"
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

def test_get_sub_asset_mult_list_success():
    print("开始测试获取组合资产列表")
    
    result = getSubAssetMultList(user=DEFAULT_USER)
    print(f"API响应结果: {result}")
    
    assert isinstance(result, ApiResponse)
    assert result.Success == True
    assert isinstance(result.Data, SubAssetMultListResponse)
    print("基本响应数据验证通过")
    
    data = result.Data
    assert len(data.list_group) > 0
    
    group = data.list_group[0]
    assert isinstance(group, SubAccountGroup)
    assert len(group.group_types) > 0
    
    group_type = group.group_types[0]
    assert isinstance(group_type, GroupType)
    print(f"组合资产数据验证通过: sub_total_amount={data.sub_total_amount}")

def test_get_sub_asset_mult_list_http_error():
    with patch('requests.post') as mock_post:
        mock_post.side_effect = requests.exceptions.RequestException('网络错误')
        
        with pytest.raises(Exception) as exc_info:
            getSubAssetMultList(user=DEFAULT_USER)
        
        assert str(exc_info.value) == '请求失败: 网络错误'

def test_get_sub_asset_mult_list_parse_error(mock_response):
    with patch('requests.post') as mock_post:
        # 返回无效的JSON数据结构
        mock_post.return_value.json.return_value = {"Success": True, "Data": None}
        mock_post.return_value.raise_for_status = MagicMock()
        
        with pytest.raises(Exception) as exc_info:
            getSubAssetMultList(user=DEFAULT_USER)
        
        assert '解析响应数据失败' in str(exc_info.value)

def test_get_sub_asset_mult_list_error_response(mock_error_response):
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = mock_error_response
        mock_post.return_value.raise_for_status = MagicMock()
        
        result = getSubAssetMultList(user=DEFAULT_USER)
        
        assert isinstance(result, ApiResponse)
        assert result.Success == False
        assert result.ErrorCode == 'E001'
        assert result.FirstError == '请求失败'
        assert result.DebugError == '网络错误'