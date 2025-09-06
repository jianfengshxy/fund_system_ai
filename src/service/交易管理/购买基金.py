import logging
import random
from typing import Optional
from src.domain.user.User import User
from src.domain.trade.TradeResult import TradeResult
from src.service.公共服务.trade_time_service import is_trading_time
from src.API.交易管理.buyMrg import commit_order as api_commit_order
from src.service.基金信息.基金信息 import get_all_fund_info

def commit_order(user: User, sub_account_no: str, fund_code: str, amount: float) -> Optional[TradeResult]:
    """
    购买基金服务层封装：
    - 负责业务保护逻辑（交易时间判断、金额保护、余额校验、购买限额检查）
    - 调用 API 层进行实际下单请求
    """
    logger = logging.getLogger("BuyFundService")

    # 1) 交易时间判断
    if not is_trading_time(user):
        logger.info(f"{user.customer_name} 当前非交易时间，跳过提交订单")
        return None

    # 2) 获取银行卡信息（下单所需 + 余额保护）
    try:
        bank_card_info = user.max_hqb_bank
    except AttributeError:
        logger.error(f"提交订单失败: 银行卡信息未设置。上下文: user_id={user.customer_no}, sub_account_no={sub_account_no}, fund_code={fund_code}, amount={amount}")
        return None

    # 2.1) 基金购买限额检查（与 SmartPlan 创建定投时一致）
    try:
        fund_info = get_all_fund_info(user, fund_code)
        if not fund_info:
            logger.warning(f"无法获取基金{fund_code}的信息")
            return None

        if not hasattr(fund_info, 'max_purchase') or not fund_info.max_purchase:
            logger.warning(f"基金{fund_code}缺少限额信息")
            return None

        max_amount = float(fund_info.max_purchase)
        request_amount = float(amount)
        logger.info(f"基金{fund_code}限额检查: 请求金额{request_amount}, 限额{max_amount}")

        exceeded_limit = False
        if request_amount > max_amount:
            logger.warning(f"购买金额{request_amount}超过基金限额{max_amount}，自动调整为限额金额")
            amount = max_amount
            exceeded_limit = True
    except Exception as e:
        logger.error(f"限额检查失败: {str(e)}")
        return None

    # 3) 金额保护（保底 10 元 + 轻微扰动）
    # 若已因限额被调整，为避免再次扰动导致接近或高于限额，这里跳过随机扰动与保底规则
    if not 'exceeded_limit' in locals() or not exceeded_limit:
        if float(amount) < 10:
            amount = 10 + round(random.uniform(0.01, 1), 2)
        else:
            amount = float(amount) - round(random.uniform(0.01, 1), 2)

    # 4) 余额校验（示例阈值：100）
    if getattr(bank_card_info, "CurrentRealBalance", 0) < 100:
        logger.error(f"银行卡余额不足: {bank_card_info.CurrentRealBalance} < 100。上下文: user_id={user.customer_no}, sub_account_no={sub_account_no}, fund_code={fund_code}, amount={amount}")
        return None

    # 5) 调用 API 层发起真实下单请求
    return api_commit_order(user, sub_account_no, fund_code, amount)