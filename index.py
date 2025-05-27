
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import sys
import logging
# 修改导入路径，使用正确的导入路径
from src.common.constant import DEFAULT_USER
from src.bussiness.全局智能定投处理.increase import increase_all_fund_plans

def handler(event, context):
    print("code目录下index:handler")
    
    # 打印当前工作目录路径
    current_dir = os.getcwd()
    print(f"Current directory: {current_dir}")
    
    # 获取当前目录下的所有文件和目录
    dir_contents = os.listdir(current_dir)
    print("Directory contents:")
    for item in dir_contents:
        print(item)
    # 获取当前东八区时间
    current_time = datetime.now(ZoneInfo("Asia/Shanghai"))
    # 打印时间
    print("东八区当前时间:", current_time)
    print("格式化输出:", current_time.strftime("%Y-%m-%d %H:%M:%S"))
    run_testcase()

def print_env_info():
     # 获取项目根目录路径
     root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
     print(f"root_dir:{root_dir}")
     # 如果项目根目录不在Python路径中，则添加
     if root_dir not in sys.path:
          sys.path.insert(0, root_dir)
    

def run_testcase():
    print("run_testcase")
    print(DEFAULT_USER)
    pass


def print_domain():
    pass

if __name__ == "__main__":
   run_testcase()
