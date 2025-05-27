import pytest
from unittest.mock import patch, MagicMock
import requests
import sys
import os

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from common.constant import DEFAULT_USER
from service.用户管理.userAllInfo import get_user_all_info
from domain.user import ApiResponse
# 修改导入方式，确保正确导入User类
from domain.user import User as UserModule
# 如果User是模块，则需要从该模块中导入正确的类
# 例如：from domain.user.User import User

@pytest.fixture
def mock_user():
    """创建模拟用户对象"""
    # 如果User是模块，则创建一个MagicMock对象来模拟User实例
    user = MagicMock()
    user.customer_no = "test_customer"
    user.u_token = "test_utoken"
    user.c_token = "test_ctoken"
    return user

@pytest.fixture
def mock_hqb_bank():
    """创建模拟活期宝银行卡对象"""
    bank = HqbBank(
        BankName="测试银行",
        BankCardNo="6222***********1234",
        BankCode="001",
        BankState=True,
        HasBranch=True,
        BankAvaVol="1000.00",
        CurrentRealBalance=1000.00
    )
    return bank

def test_get_user_all_info_success():
    """测试成功获取用户完整信息"""
    # 调用测试函数
    result = get_user_all_info(DEFAULT_USER.account, DEFAULT_USER.password)
    print(f"名字: {result.customer_name}")
    # 验证结果
    assert result is not None
    # assert isinstance(result, User)
    assert result.customer_name == "施小雨"
    # assert isinstance(result, User)
    assert result.max_hqb_bank is not None

