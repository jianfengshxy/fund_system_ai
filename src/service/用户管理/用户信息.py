import os, sys
from src.API.登录接口.login import login, login_passport, inference_passport_for_bind
from src.service.银行卡账户.bankAccoutService import getMaxhqbBank
from src.common.logger import get_logger

# 添加全局缓存字典
user_cache = {}
logger = get_logger(__name__)

def get_user_all_info(account: str, password: str):
    """
    获取用户的完整信息，包括登录信息、passport信息和最大活期宝银行卡信息
    Args:
        account: 用户账号
        password: 用户密码
    Returns:
        User: 包含完整信息的用户对象，如果任何步骤失败则返回None
    """
    # 检查缓存
    cache_key = (account, password)
    if cache_key in user_cache:
        logger.info("用户信息命中缓存", extra={"account": account})
        return user_cache[cache_key]
    
    # 第一步：调用登录接口
    user = login(account, password)
    if not user:
        logger.error("登录失败", extra={"account": account})
        return None
        
    # 第二步：获取passport信息
    user = inference_passport_for_bind(user)
    if not user:
        logger.error("passport推断失败", extra={"account": account})
        return None
        
    # 第三步：获取最大活期宝银行卡信息
    user = getMaxhqbBank(user)
    if user:
        user_cache[cache_key] = user
        logger.info("完成用户信息聚合", extra={"account": account})
    return user

if __name__ == "__main__":
    from common.constant import DEFAULT_USER
    result = get_user_all_info(DEFAULT_USER.account, DEFAULT_USER.password)
    print("最终用户信息:", result)
