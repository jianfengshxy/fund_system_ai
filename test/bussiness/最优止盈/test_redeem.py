import pytest
import os
import sys
import logging

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# 修改导入路径，使用正确的导入路径
from src.common.constant import DEFAULT_USER, DEFAULT_FUND_PLAN_DETAIL
from src.bussiness.最优止盈组合.redeem import redeem
from src.domain.fund_plan.fund_plan_detail import FundPlanDetail
from src.domain.user.User import User
from src.API.定投计划管理.SmartPlan import getFundRations, getPlanDetailPro

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)d)')
logger = logging.getLogger(__name__)


def test_redeem_success():
    """测试最优止盈组合的止盈功能
    使用 DEFAULT_USER 和默认的 '最优止盈' 组合名称进行测试
    """
    # 调用 redeem 函数进行止盈操作
    result = redeem(DEFAULT_USER, "最优止盈")
    
    # 验证函数执行成功
    assert result == True


def test_redeem_all_users_success():
    """测试 redeem_all_users 函数的成功用例
    """
    # 调用 redeem_all_users 函数
    # 从redeem模块导入redeem_all_users函数
    from src.bussiness.最优止盈组合.redeem import redeem_all_users
    result = redeem_all_users()
 

if __name__ == "__main__":
    # 直接运行测试
    logger.info("直接运行止盈测试")
    # test_redeem_success()
    test_redeem_all_users_success()