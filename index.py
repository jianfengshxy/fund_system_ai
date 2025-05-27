import os
from datetime import datetime
from zoneinfo import ZoneInfo
import sys
import logging
import urllib3  # 添加对 urllib3 的导入

# 禁用 urllib3 的警告信息
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 添加 src 到 Python 模块路径
sys.path.append('src')

# 导入需要的变量和函数
from src.common.constant import SERVER_VERSION, PASSPORT_CTOKEN
from src.common.constant import DEFAULT_USER
from src.bussiness.全局智能定投处理.increase import increase_all_fund_plans
from src.domain.user.User import User

# 初始化日志记录器
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def handler(event, context):
    logger.info("code目录下index:handler")
    
    # 获取当前工作目录路径
    current_dir = os.getcwd()
    logger.info(f"Current directory: {current_dir}")
    
    # 获取当前目录下的所有文件和目录
    dir_contents = os.listdir(current_dir)
    logger.info("Directory contents:")
    for item in dir_contents:
        logger.info(item)
    
    # 获取当前东八区时间
    current_time = datetime.now(ZoneInfo("Asia/Shanghai"))
    # 打印时间
    logger.info(f"东八区当前时间: {current_time}")
    logger.info(f"格式化输出: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 打印 SERVER_VERSION
    # logger.info(f"SERVER_VERSION: {SERVER_VERSION}")
    # logger.info(f"DEFAULT_USER: {DEFAULT_USER}")
    run_testcase()

def run_testcase():
    """测试 increase_all_fund_plans 函数"""
    # 打印测试开始信息
    # logger.info("开始测试 increase_all_fund_plans 函数")
    # # 调用函数进行加仓测试
    increase_all_fund_plans(DEFAULT_USER)
    logger.info("开始测试 redeem_all_fund_plans 函数")
    # 调用函数进行加仓测试


if __name__ == "__main__":
    handler(None, None)