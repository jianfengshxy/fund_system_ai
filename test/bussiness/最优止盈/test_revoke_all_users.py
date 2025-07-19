import logging
import os
import sys

# 配置 logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.bussiness.最优止盈组合.revoke import revoke
from src.service.用户管理.用户信息 import get_user_all_info
from src.domain.user.User import User

logger = logging.getLogger(__name__)

# 只使用指定的用户数据作为测试数据
user_info = ("13500819290", "guojing1985", "guojing1985", "郭婧", "最优止盈", 200000.0)

def test_revoke():
    """测试 revoke 函数，使用指定用户数据"""
    logger.info("开始测试 revoke 函数")
    
    account, password, _, name, sub_account_name, _ = user_info
    
    user = get_user_all_info(account, password)
    if not user:
        logger.error(f"获取用户 {name} 信息失败")
        return
    
    success = revoke(user, sub_account_name)
    
    if success:
        logger.info(f"用户 {name} 的撤回操作成功")
    else:
        logger.warning(f"用户 {name} 的撤回操作有部分失败")
    
    logger.info("测试 revoke 函数完成")

if __name__ == "__main__":
    test_revoke()