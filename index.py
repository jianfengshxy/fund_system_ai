import os
from datetime import datetime
from zoneinfo import ZoneInfo
import sys
import logging
import urllib3  # 添加对 urllib3 的导入
from src.bussiness.最优止盈组合.redeem import redeem_all_users
# 禁用 urllib3 的警告信息
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 添加 src 到 Python 模块路径
sys.path.append('src')

# 导入需要的变量和函数
from src.common.constant import SERVER_VERSION, PASSPORT_CTOKEN
from src.common.constant import DEFAULT_USER
from src.bussiness.全局智能定投处理.increase import increase_all_fund_plans
from src.bussiness.全局智能定投处理.redeem import redeem_all_fund_plans 
from src.domain.user.User import User
from src.common.constant import DEFAULT_USER, DEFAULT_FUND_PLAN_DETAIL

# 初始化日志记录器
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def redeem(event, context):
    redeem_all_fund_plans(DEFAULT_USER)
    result = redeem_all_users()

def increase(event, context):
    increase_all_fund_plans(DEFAULT_USER)
    

if __name__ == "__main__":
    handler(None, None)