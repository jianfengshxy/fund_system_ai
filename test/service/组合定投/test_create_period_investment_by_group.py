import logging
import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from src.domain.user.User import User
from src.service.用户管理.用户信息 import get_user_all_info
from src.service.定投管理.组合定投.组合定投管理 import create_period_investment_by_group
from src.common.constant import DEFAULT_USER

# 配置 logger
logger = logging.getLogger("TestCreatePeriodInvestmentByGroup")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

def test_create_period_investment_by_group_success():
    logger.info("开始测试 create_period_investment_by_group 函数")
    
    # 获取用户所有信息
    user_info = get_user_all_info(DEFAULT_USER.account,DEFAULT_USER.password)
    logger.info(f"获取到的用户信息: {user_info}")
    logger.info(f"user.max_hqb_bank: {user_info.max_hqb_bank}")
    logger.info(f"user.max_hqb_bank 类型: {type(user_info.max_hqb_bank)}")
    response = create_period_investment_by_group(
        user=user_info,
        sub_account_name="指数基金组合",
        fund_code="016496",
        amount=2000,
        period_type=4,
        period_value=1
    )
    
    logger.info(f"创建定投响应: {response}")
    
    # 断言响应是否成功
    assert response is not None, "创建定投响应为 None"
    assert response.Success, f"创建定投失败: {response.FirstError}"
    logger.info("测试通过")

if __name__ == "__main__":
    test_create_period_investment_by_group_success()