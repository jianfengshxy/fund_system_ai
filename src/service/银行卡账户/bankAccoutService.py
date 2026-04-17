import logging
from src.common.logger import get_logger
from src.API.银行卡信息.CashBag import getCashBagAvailableShareV2  # 替换为实际导入路径

logger = get_logger(__name__)

def getMaxhqbBank(user):
    """
    获取用户最大活期宝银行卡信息。
    Args:
        user: 用户对象
    Returns:
        user: 增加max_hqb_bank属性的用户对象
    """
    extra = {"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "action": "get_max_hqb"}
    logger.info("开始获取最大活期宝银行卡信息...", extra=extra)
    logger.info(
        f"用户上下文: customer_no={getattr(user, 'customer_no', None)}, index={getattr(user, 'index', None)}",
        extra=extra,
    )

    bank_cards = getCashBagAvailableShareV2(user)
    logger.info(f"CashBagAvailableShareV2 返回银行卡数量: {len(bank_cards) if bank_cards else 0}", extra=extra)

    if not bank_cards:
        logger.error("获取银行卡信息失败：没有可用的银行卡", extra=extra)
        user.max_hqb_bank = None
        return user

    def _safe_float(v):
        try:
            return float(v or 0.0)
        except Exception:
            return 0.0

    def _mask_no(v):
        s = str(v or "")
        if len(s) <= 8:
            return s
        return f"{s[:4]}***{s[-4:]}"

    # 打印候选银行卡关键信息（按返回顺序，通常已按 BankAvaVol 降序）
    for idx, card in enumerate(bank_cards, start=1):
        bank_ava = _safe_float(getattr(card, "BankAvaVol", 0.0))
        current_real = _safe_float(getattr(card, "CurrentRealBalance", 0.0))
        logger.info(
            f"候选卡#{idx}: bank={getattr(card, 'BankName', None)}, "
            f"account={_mask_no(getattr(card, 'AccountNo', None))}, "
            f"BankAvaVol={bank_ava}, CurrentRealBalance={current_real}, "
            f"CanPayment={getattr(card, 'CanPayment', None)}, BankState={getattr(card, 'BankState', None)}",
            extra=extra,
        )
    # 选择余额最大的银行卡：
    # 优先按 CurrentRealBalance，其次按 BankAvaVol，避免接口返回顺序导致选错卡
    def _card_score(card):
        current_real = _safe_float(getattr(card, "CurrentRealBalance", 0.0))
        bank_ava = _safe_float(getattr(card, "BankAvaVol", 0.0))
        return (current_real, bank_ava)

    user.max_hqb_bank = max(bank_cards, key=_card_score)
    if user.max_hqb_bank.AccountNo:
        user.max_hqb_bank.AccountNo = user.max_hqb_bank.AccountNo.split('#')[0]
    logger.info(
        f"{user.customer_name}选中最大余额账号：{user.max_hqb_bank.AccountNo}",
        extra=extra,
    )
    logger.info(
        f"选中银行卡: bank={getattr(user.max_hqb_bank, 'BankName', None)}, "
        f"account={_mask_no(getattr(user.max_hqb_bank, 'AccountNo', None))}, "
        f"BankAvaVol={_safe_float(getattr(user.max_hqb_bank, 'BankAvaVol', 0.0))}, "
        f"CurrentRealBalance={_safe_float(getattr(user.max_hqb_bank, 'CurrentRealBalance', 0.0))}",
        extra=extra,
    )
    logger.info("最大活期宝银行卡信息获取完成", extra=extra)
    return user
