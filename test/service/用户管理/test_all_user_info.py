import sys
import os
# Insert the project root instead
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
sys.path.insert(0, project_root)
import pytest
import requests

import logging
from src.common.constant import DEFAULT_USER
from src.domain.user import ApiResponse
from src.domain.user.User import User as UserModule  # 修改为正确的类导入
from src.domain.bank.bank import HqbBank
from src.service.用户管理.用户信息 import get_user_all_info

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_get_user_all_info_success():
    logger.info("开始测试获取用户全部信息")
    
    result = get_user_all_info(DEFAULT_USER.account, DEFAULT_USER.password)
    logger.info(f"API响应结果类型: {type(result)}")
    logger.info(f"用户姓名: {result.customer_name}")
    logger.info(f"最大活期宝银行: {result.max_hqb_bank}")
    
    assert isinstance(result, UserModule)
    assert result is not None
    assert result.customer_name == "施小雨"
    assert result.max_hqb_bank is not None
    logger.info("用户全部信息验证通过")

if __name__ == "__main__":
    test_get_user_all_info_success()

