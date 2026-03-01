import logging
from src.common.logger import get_logger
import random
from typing import Optional
from src.domain.user.User import User
from src.domain.trade.TradeResult import TradeResult
from src.service.公共服务.trade_time_service import is_trading_time
from src.API.工具.utils import is_long_holiday
from src.API.交易管理.buyMrg import commit_order as api_commit_order
from src.service.基金信息.基金信息 import get_all_fund_info
from src.common.errors import RetriableError, ValidationError, TradePasswordError

def commit_order(user: User, sub_account_no: str, fund_code: str, amount: float) -> Optional[TradeResult]:
    """
    购买基金服务层封装：
    - 负责业务保护逻辑（交易时间判断、金额保护、余额校验、购买限额检查）
    - 调用 API 层进行实际下单请求
    """
    logger = get_logger("BuyFundService")
    extra = {"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "sub_account_name": "", "action": "buy_commit", "fund_code": fund_code, "sub_account_no": sub_account_no}

    # 1) 交易时间判断
    if not is_trading_time(user):
        logger.info(f"{user.customer_name} 当前非交易时间，跳过提交订单", extra=extra)
        return None

    # 1.1) 长假期判断：如果是长假期前（距离下一个交易日超过3天），暂停买入，避免持仓时间过长不可控
    if is_long_holiday(user):
        logger.info(f"{user.customer_name} 当前处于长假期前夕（距下一交易日>3天），暂停买入以规避长假风险", extra=extra)
        return None

    # 2) 获取银行卡信息（下单所需 + 余额保护）
    try:
        bank_card_info = user.max_hqb_bank
    except AttributeError:
        logger.error(f"提交订单失败: 银行卡信息未设置。上下文: user_id={user.customer_no}, sub_account_no={sub_account_no}, fund_code={fund_code}, amount={amount}", extra=extra)
        return None

    # 2.1) 基金状态与购买限额检查
    try:
        fund_info = get_all_fund_info(user, fund_code)
        if not fund_info:
            logger.warning(f"无法获取基金{fund_code}的信息", extra=extra)
            return None

        can_purchase = getattr(fund_info, 'can_purchase', None)
        if can_purchase is not None and not bool(can_purchase):
            logger.info(f"基金{fund_code}当前不可申购，跳过", extra=extra)
            return None

        if not hasattr(fund_info, 'max_purchase') or not fund_info.max_purchase:
            logger.warning(f"基金{fund_code}缺少限额信息", extra=extra)
            return None

        max_amount = float(fund_info.max_purchase)
        request_amount = float(amount)
        logger.info(f"基金{fund_code}限额检查: 请求金额{request_amount}, 限额{max_amount}", extra=extra)

        exceeded_limit = False
        if request_amount > max_amount:
            logger.warning(f"购买金额{request_amount}超过基金限额{max_amount}，自动调整为限额金额", extra=extra)
            amount = max_amount
            exceeded_limit = True
    except Exception as e:
        logger.error(f"限额检查失败: {str(e)}", extra=extra)
        return None

    # 3) 金额保护（保底 10 元 + 轻微扰动）
    # 若已因限额被调整，为避免再次扰动导致接近或高于限额，这里跳过随机扰动与保底规则
    if not 'exceeded_limit' in locals() or not exceeded_limit:
        if float(amount) < 10:
            amount = 10 + round(random.uniform(0.01, 1), 2)
        else:
            amount = float(amount) - round(random.uniform(0.01, 1), 2)

    # 4) 余额校验（示例阈值：100）
    balance = getattr(bank_card_info, "CurrentRealBalance", 0) if bank_card_info is not None else 0
    if balance < 100:
        logger.error(
            f"银行卡余额不足: {balance} < 100。上下文: user_id={user.customer_no}, sub_account_no={sub_account_no}, fund_code={fund_code}, amount={amount}",
            extra=extra,
        )
        return None

    # 5) 调用 API 层发起真实下单请求
    try:
        return api_commit_order(user, sub_account_no, fund_code, amount)
    except TradePasswordError:
        raise
    except RetriableError as e:
        logger.warning(f"购买API异常可重试: {e}", extra=extra)
        return None
    except ValidationError as e:
        logger.error(f"购买API解析/数据错误: {e}", extra=extra)
        return None
