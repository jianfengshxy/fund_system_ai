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

from src.API.定投计划管理.SmartPlan import getPlanDetailPro
from src.domain.fund_plan import ApiResponse, FundPlan
from src.domain.fund_plan.fund_plan_detail import FundPlanDetail, Share
from src.common.constant import DEFAULT_USER, PLAN_ID

@pytest.fixture
def mock_response():
    return {
        "Success": True,
        "ErrorCode": None,
        "Data": {
            "rationPlan": {
                "planId": "12345",
                "fundCode": "020256",
                "fundName": "国泰君安基金",
                "fundType": "1",
                "executedAmount": 1000.0,
                "executedTime": 1650000000,
                "planState": "1",
                "planBusinessState": "1",
                "planExtendStatus": "0",
                "periodType": 1,
                "periodValue": 15,
                "amount": 1000.0,
                "nextDeductDate": "2025-05-15",
                "bankCode": "001",
                "showBankCode": "工商银行",
                "shortBankCardNo": "1234",
                "bankAccountNo": "6222021234567890",
                "payType": 1,
                "planAssets": 5000.0
            },
            "profitTrends": [],
            "couponDetail": None,
            "shares": [
                {
                    "availableVol": 100.0,
                    "bankCode": "001",
                    "showBankCode": "工商银行",
                    "bankCardNo": "6222021234567890",
                    "bankName": "工商银行",
                    "shareId": "SH001",
                    "bankAccountNo": "6222021234567890",
                    "totalVol": 100.0
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

@pytest.fixture
def mock_detailed_response():
    return {
        "Success": True, 
        "ErrorCode": 0, 
        "Data": { 
            "rationPlan": { 
                "planId": "fb5f5ee06eb941258f2fd6965cab32b4", 
                "fundCode": "017968", 
                "fundName": "华富科技动能混合C", 
                "fundType": "4", 
                "financialType": "", 
                "isCashBag": False, 
                "executedAmount": 4000, 
                "executedTime": 2, 
                "planState": 0, 
                "planBusinessState": "10", 
                "pauseType": None, 
                "planExtendStatus": "13", 
                "periodType": 4, 
                "periodValue": 1, 
                "amount": 2000, 
                "nextDeductDate": None, 
                "reTriggerDate": "1900-01-01", 
                "recentDeductDate": "2025-05-21", 
                "bankCode": "002", 
                "showBankCode": "002", 
                "shortBankCardNo": "8882", 
                "bankAccountNo": "f12a70addec7458dae41369ac1005e5a", 
                "payType": 1, 
                "subAccountNo": "28010355", 
                "subAccountName": "目标止盈定投017968", 
                "subDisband": None, 
                "currentDay": "2025-05-20", 
                "isGdlc": False, 
                "buyStrategy": "1", 
                "redeemStrategy": "1", 
                "retriggerTips": "", 
                "isDeductDay": False, 
                "couponsSummaryInfo": None, 
                "remark": None, 
                "createTime": "2025-05-07", 
                "stateTip": "该定投计划已经连续6期扣款失败，系统暂停了该计划的买入策略，您可以手动恢复", 
                "chargeDateTip": "扣款日为每个工作日；若定投计划连续6期扣款失败，系统会进行暂停，您可以手动恢复", 
                "deductType": None, 
                "enable36": True, 
                "enable815": True, 
                "enable890": True, 
                "allowRedeemToHqb": True, 
                "allowRedeem": True, 
                "rationAutoPay": True, 
                "isForceRation": False, 
                "configType": None, 
                "paramType": None, 
                "dueDate": None, 
                "duePeriods": None, 
                "dueAmount": None, 
                "planConfigId": "CL001", 
                "indexCode": None, 
                "indexName": None, 
                "maxTime": None, 
                "minTime": None, 
                "amountMin": None, 
                "amountMax": None, 
                "planAssets": 5962.12, 
                "rationProfit": -38.75, 
                "totalProfit": -38.75, 
                "rationProfitRate": -0.0065, 
                "totalProfitRate": -0.0065, 
                "unitPrice": 1.382, 
                "targetRate": "5%", 
                "retreatPercentage": None, 
                "renewal": True, 
                "redemptionWay": 1, 
                "sellLockDays": -1, 
                "latestTakeProfitDetail": None, 
                "takeProfitFailedDate": None, 
                "redeemFailedMessage": None, 
                "reachExpectationDate": None, 
                "isHKFund": False, 
                "rangeIndex": None, 
                "planStrategyId": "CL001", 
                "lockTime": "2025-05-12", 
                "maxProfit": -0.0065, 
                "redeemLimit": "1" 
            }, 
            "profitTrends": [ 
                { 
                    "date": "2025-05-08", 
                    "profitRate": 0, 
                    "unitPrice": 1.3963, 
                    "buyPoint": False, 
                    "redeemPoint": False 
                }, 
                { 
                    "date": "2025-05-09", 
                    "profitRate": -0.023, 
                    "unitPrice": 1.3963, 
                    "buyPoint": False, 
                    "redeemPoint": False 
                }, 
                { 
                    "date": "2025-05-12", 
                    "profitRate": 0.0064, 
                    "unitPrice": 1.3963, 
                    "buyPoint": False, 
                    "redeemPoint": False 
                }, 
                { 
                    "date": "2025-05-13", 
                    "profitRate": -0.0028, 
                    "unitPrice": 1.3963, 
                    "buyPoint": False, 
                    "redeemPoint": False 
                }, 
                { 
                    "date": "2025-05-14", 
                    "profitRate": -0.0152, 
                    "unitPrice": 1.3963, 
                    "buyPoint": False, 
                    "redeemPoint": False 
                }, 
                { 
                    "date": "2025-05-15", 
                    "profitRate": -0.0156, 
                    "unitPrice": 1.382, 
                    "buyPoint": False, 
                    "redeemPoint": False 
                }, 
                { 
                    "date": "2025-05-16", 
                    "profitRate": 0.0125, 
                    "unitPrice": 1.382, 
                    "buyPoint": False, 
                    "redeemPoint": False 
                }, 
                { 
                    "date": "2025-05-19", 
                    "profitRate": -0.0065, 
                    "unitPrice": 1.382, 
                    "buyPoint": False, 
                    "redeemPoint": False 
                } 
            ], 
            "couponDetail": None, 
            "shares": [ 
                { 
                    "availableVol": 4342.09, 
                    "bankCode": "002", 
                    "showBankCode": "002", 
                    "bankCardNo": "PR28010355Z6222021104005268882", 
                    "bankName": "工商银行", 
                    "shareId": "1724705588", 
                    "bankAccountNo": "f12a70addec7458dae41369ac1005e5a", 
                    "totalVol": 4342.09 
                } 
            ] 
        }, 
        "FirstError": None, 
        "DebugError": None 
    }

def test_get_plan_detail_pro_with_mock_data(mock_detailed_response):
    """
    使用详细的模拟数据测试getPlanDetailPro函数
    """
    print("开始测试获取定投计划详情，使用详细模拟数据")
    
    with patch('requests.post') as mock_post:
        # 配置mock响应
        mock_post.return_value.json.return_value = mock_detailed_response
        mock_post.return_value.raise_for_status = MagicMock()
        
        # 调用被测试的函数
        result = getPlanDetailPro(plan_id="fb5f5ee06eb941258f2fd6965cab32b4", user=DEFAULT_USER)
        
        # 验证基本响应结构
        assert isinstance(result, ApiResponse)
        assert result.Success == True
        assert result.ErrorCode == 0
        assert isinstance(result.Data, FundPlanDetail)
        print("基本响应数据验证通过")
        
        # 验证定投计划数据
        ration_plan = result.Data.rationPlan
        assert isinstance(ration_plan, FundPlan)
        assert ration_plan.planId == "fb5f5ee06eb941258f2fd6965cab32b4"
        assert ration_plan.fundCode == "017968"
        assert ration_plan.fundName == "华富科技动能混合C"
        assert ration_plan.fundType == "4"
        assert ration_plan.periodType == 4
        assert ration_plan.periodValue == 1
        assert ration_plan.amount == 2000
        assert ration_plan.targetRate == "5%"
        print(f"定投计划数据验证通过: planId={ration_plan.planId}, fundName={ration_plan.fundName}")
        
        # 验证收益趋势数据
        profit_trends = result.Data.profitTrends
        assert len(profit_trends) == 8
        assert profit_trends[0]["date"] == "2025-05-08"
        assert profit_trends[7]["profitRate"] == -0.0065
        print(f"收益趋势数据验证通过: 共{len(profit_trends)}条记录")
        
        # 验证份额数据
        shares = result.Data.shares
        assert len(shares) == 1
        share = shares[0]
        assert isinstance(share, Share)
        assert share.shareId == "1724705588"
        assert share.bankCode == "002"
        assert share.bankName == "工商银行"
        assert float(share.availableVol) == 4342.09
        assert float(share.totalVol) == 4342.09
        print(f"份额数据验证通过: shareId={share.shareId}, availableVol={share.availableVol}")

def test_get_plan_detail_pro_success():
    print(f"开始测试获取定投计划详情，计划ID: {PLAN_ID}")
    
    result = getPlanDetailPro(plan_id="fb5f5ee06eb941258f2fd6965cab32b4", user=DEFAULT_USER)
    print(f"API响应结果: {result}")
    
    assert isinstance(result, ApiResponse)
    assert result.Success == True
    assert isinstance(result.Data, FundPlanDetail)
    print("基本响应数据验证通过")
    
    ration_plan = result.Data.rationPlan
    assert isinstance(ration_plan, FundPlan)
    assert ration_plan.planId == "fb5f5ee06eb941258f2fd6965cab32b4"
    print(f"定投计划数据验证通过: planId={ration_plan.planId}")
    
    if len(result.Data.shares) > 0:
        share = result.Data.shares[0]
        assert isinstance(share, Share)
        assert share.shareId is not None
        assert share.bankCode is not None
        assert float(share.availableVol) > 0
        print(f"份额数据验证通过: shareId={share.shareId}, availableVol={share.availableVol}")
    else:
        print("未找到任何份额数据")

def test_get_plan_detail_pro_http_error():
    with patch('requests.post') as mock_post:
        mock_post.side_effect = requests.exceptions.RequestException('网络错误')
        
        with pytest.raises(Exception) as exc_info:
            getPlanDetailPro(plan_id='12345', user=DEFAULT_USER)
        
        assert str(exc_info.value) == '请求失败: 网络错误'

def test_get_plan_detail_pro_parse_error(mock_response):
    with patch('requests.post') as mock_post:
        # 返回无效的JSON数据结构
        mock_post.return_value.json.return_value = {"Success": True, "Data": None}
        mock_post.return_value.raise_for_status = MagicMock()
        
        with pytest.raises(Exception) as exc_info:
            getPlanDetailPro(plan_id='12345', user=DEFAULT_USER)
        
        assert '解析响应数据失败' in str(exc_info.value)

def test_get_plan_detail_pro_error_response(mock_error_response):
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = mock_error_response
        mock_post.return_value.raise_for_status = MagicMock()
        
        result = getPlanDetailPro(plan_id='12345', user=DEFAULT_USER)
        
        assert isinstance(result, ApiResponse)
        assert result.Success == False
        assert result.ErrorCode == 'E001'
        assert result.FirstError == '请求失败'
        assert result.DebugError == '网络错误'


def test_get_plan_detail_pro_with_constant_plan_id():
    print(f"开始测试获取定投计划详情，使用常量PLAN_ID: {PLAN_ID}")
    
    result = getPlanDetailPro(plan_id=PLAN_ID, user=DEFAULT_USER)
    print(f"API响应结果: {result}")
    
    assert isinstance(result, ApiResponse)
    assert result.Success == True
    assert isinstance(result.Data, FundPlanDetail)
    print("基本响应数据验证通过")
    
    ration_plan = result.Data.rationPlan
    assert isinstance(ration_plan, FundPlan)
    assert ration_plan.planId == PLAN_ID
    print(f"定投计划数据验证通过: planId={ration_plan.planId}")
    
    if len(result.Data.shares) > 0:
        share = result.Data.shares[0]
        assert isinstance(share, Share)
        assert share.shareId is not None
        assert share.bankCode is not None
        assert float(share.availableVol) > 0
        print(f"份额数据验证通过: shareId={share.shareId}, availableVol={share.availableVol}")
    else:
        print("未找到任何份额数据")