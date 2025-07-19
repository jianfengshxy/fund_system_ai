import logging
from src.API.银行卡信息.CashBag import getCashBagAvailableShareV2  # 替换为实际导入路径

logger = logging.getLogger(__name__)

def getMaxhqbBank(user):
    """
    获取用户最大活期宝银行卡信息。
    Args:
        user: 用户对象
    Returns:
        user: 增加max_hqb_bank属性的用户对象
    """
    logger.info("开始获取最大活期宝银行卡信息...")
    bank_cards = getCashBagAvailableShareV2(user)
    if not bank_cards:
        logger.error("获取银行卡信息失败：没有可用的银行卡")
        user.max_hqb_bank = None
        return user
    # 使用第一个银行卡（余额最高的）
    user.max_hqb_bank = bank_cards[0]
    if user.max_hqb_bank.AccountNo:
        user.max_hqb_bank.AccountNo = user.max_hqb_bank.AccountNo.split('#')[0]
    logger.info(f"{user.customer_name}的账号：{user.max_hqb_bank.AccountNo}")
    return user