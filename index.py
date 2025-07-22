import os
from datetime import datetime
from zoneinfo import ZoneInfo
import sys
import logging
import urllib3  # 添加对 urllib3 的导入
from src.bussiness.最优止盈组合.redeem import redeem_all_users
from src.bussiness.最优止盈组合.increase import increase_all_users
from src.bussiness.最优止盈组合.add_new import add_new_all_users
# 禁用 urllib3 的警告信息
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 添加 src 到 Python 模块路径
sys.path.append('src')

# 导入需要的变量和函数
from src.common.constant import SERVER_VERSION, PASSPORT_CTOKEN
from src.common.constant import DEFAULT_USER
from src.bussiness.全局智能定投处理.increase import increase_all_fund_plans
from src.bussiness.全局智能定投处理.redeem import redeem_all_fund_plans
from src.bussiness.全局智能定投处理.dissolve_plan import dissolve_daily_plan
# 添加 add_plan 函数的导入
from src.bussiness.全局智能定投处理.add_plan import add_plan
# 添加组合定投管理函数的导入
from src.bussiness.组合定投.指数型组合定投管理 import create_plan_by_group_for_index_funds,dissolve_plan_by_group_for_index_funds
from src.domain.user.User import User
from src.common.constant import DEFAULT_USER, DEFAULT_FUND_PLAN_DETAIL

# 在现有导入语句后添加
from src.bussiness.组合定投.主动型组合定投管理 import create_plan_by_group, dissolve_plan_by_group

# 初始化日志记录器
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def redeem(event, context):
    redeem_all_fund_plans(DEFAULT_USER)
    result = redeem_all_users()

def increase(event, context):
    increase_all_fund_plans(DEFAULT_USER)
    increase_all_users()

def create_period_smart_investment(event, context):   
    # add_plan(DEFAULT_USER, 3000)
    create_plan_by_group(DEFAULT_USER,"低风险组合",1000000.0,10000.0)
    pass

def dissolve_period_smart_investment(event, context):          
    dissolve_daily_plan(DEFAULT_USER)
    dissolve_plan_by_group(DEFAULT_USER,"低风险组合",1000000.0)
    pass

def add_new(event, context):          
    add_new_all_users()
    pass

def create_period_index_investment(event, context):
    """创建指数型基金定投计划"""
    create_plan_by_group_for_index_funds(DEFAULT_USER, "指数基金组合", 200000.0, 2000.0)
    pass

def dissolve_period_index_investment(event, context):
    """解散指数型基金定投计划"""
    dissolve_plan_by_group_for_index_funds(DEFAULT_USER, "指数基金组合", 1000000.0)
    pass

if __name__ == "__main__":
    # 根据需要调用 redeem 或 increase 函数
    # redeem(None, None)
    # create_period_smart_investment(None, None)
    dissolve_period_smart_investment(None, None)
    # create_period_smart_investment(None, None)
