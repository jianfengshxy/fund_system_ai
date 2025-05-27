# 删除外部导入
# from API.定投计划管理.SmartPlan import createPlanV3 
import requests
import pytest
import logging
import os
import sys

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# 只保留内部导入
from src.API.定投计划管理.SmartPlan import createPlanV3 
from src.common.constant import DEFAULT_USER

# 如果需要保留手动调用的版本，可以使用不同的函数名
@pytest.mark.skip(reason="手工指定调用")
def test_create_plan_V3_success_manual():
    """测试成功创建定投计划V3（手动调用版本）"""
    # 配置日志
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # 准备测试数据 - 使用与API实现匹配的参数
    fund_code = "019458"  # 使用API中硬编码的基金代码
    amount = "5000"       # 使用API中硬编码的金额
    period_type = 4       # 使用API中硬编码的周期类型(每日)
    period_value = 1      # 使用API中硬编码的周期值
    strategy_type = 0     # 策略类型 (0: 目标止盈定投)
    
    try:
        # 获取用户信息
        user_info = DEFAULT_USER
        assert user_info is not None, "获取用户信息失败"
        assert user_info.max_hqb_bank is not None, "未获取到活期宝银行卡信息"
        
        # 打印用户信息用于调试
        logger.debug(f"用户信息: customer_no={user_info.customer_no}")
        logger.debug(f"银行卡信息: account_no={user_info.max_hqb_bank.AccountNo}")
        
        # 调用接口创建定投计划 - 按照函数定义的参数顺序传递
        response = createPlanV3(
            user=user_info,
            fund_code=fund_code,
            amount=amount,
            period_type=period_type,
            period_value=period_value,
            strategy_type=strategy_type
        )
        
        # 打印响应信息以便调试
        logger.info(f"API响应状态: {response}")
        
        # 验证响应结果
        assert response is not None, "响应不能为空"
        # 取消注释以下断言进行更详细的验证
        # assert response.Success is True, f"API调用失败: {response.FirstError if hasattr(response, 'FirstError') else '未知错误'}"
        # assert response.Data is not None, "响应数据不能为空"
        
        # 验证计划详情
        # plan_detail = response.Data
        # assert plan_detail.fundCode == fund_code, "基金代码不匹配"
        # assert plan_detail.amount == amount, "投资金额不匹配"
        # assert plan_detail.periodInfo is not None, "定投周期信息不能为空"
        
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP请求失败: {str(e)}")
        logger.error(f"请求URL: {e.response.url if hasattr(e.response, 'url') else 'unknown'}")
        logger.error(f"状态码: {e.response.status_code if hasattr(e, 'response') else 'unknown'}")
        logger.error(f"响应内容: {e.response.text if hasattr(e.response, 'text') else 'unknown'}")
        pytest.fail(f"HTTP请求失败: {str(e)}")
    except requests.exceptions.RequestException as e:
        logger.error(f"请求异常: {str(e)}")
        pytest.fail(f"请求异常: {str(e)}")
    except Exception as e:
        logger.error(f"测试执行失败: {str(e)}")
        pytest.fail(f"测试执行失败: {str(e)}")
