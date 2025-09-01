import pytest
import json
import sys
import os

# 添加项目根目录到 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from index import redeem  # 现在可以正确导入
from src.common.constant import DEFAULT_USER  # 添加导入，如果需要

def test_redeem_success():
    # 使用提供的 payload 制造 event
    payload = {
        "account": "13918199137",
        "password": "sWX15706",
        "sub_account_name": "低风险组合",
        "total_budget": 1000000.0
    }
    event = {'payload': json.dumps(payload)}
    context = None  # 可以根据需要模拟 context，如果不需要则设为 None
    
    # 直接调用 redeem 函数
    redeem(event, context)
    
    # 如果需要添加断言，例如检查日志或特定输出，请在此处添加
    # 例如：assert some_condition

def test_redeem_missing_params():
    # 测试缺少参数的情况
    payload = {
        "account": "13918199137",
        "password": "sWX15706",
        # 缺少 sub_account_name 和 total_budget
    }
    event = {'payload': json.dumps(payload)}
    context = None
    
    # 直接调用 redeem 函数
    redeem(event, context)
    
    # 添加相关断言如果必要
    # 例如：assert some_condition

if __name__ == "__main__":
    # test_redeem_missing_params()
    test_redeem_success()