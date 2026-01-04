import logging
import os
import sys
from typing import Optional, List, Tuple

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.logger import get_logger

from src.domain.user.User import User
from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.service.基金信息.基金信息 import get_all_fund_info
from src.API.交易管理.trade import get_bank_shares
from src.common.constant import DEFAULT_USER
from src.API.资产管理.AssetManager import GetMyAssetMainPartAsync
from src.API.基金信息.FundRank import get_fund_growth_rate
from src.service.交易管理.赎回基金 import sell_low_fee_shares, sell_0_fee_shares, sell_usable_non_zero_fee_shares

logger = get_logger(__name__)

def redeem_funds(user: User, sub_account_name: str, total_budget: Optional[float] = None, profit_threshold: Optional[float] = 10.0) -> bool:
    # 统一日志前缀与风格（保持原有）
    customer_name = user.customer_name
    logger.info(f"开始为用户 {customer_name} 执行止盈操作，组合: {sub_account_name}", extra={"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "sub_account_name": sub_account_name, "action": "jianlong_redeem"})
    
    # 获取组合账号
    sub_account_no = getSubAccountNoByName(user, sub_account_name)
    if not sub_account_no:
        logger.error(f"未找到组合 {sub_account_name} 的账号")
        return False
    
    # 获取组合所有基金资产
    user_assets = get_sub_account_asset_by_name(user, sub_account_name)
    if not user_assets:
        logger.info(f"组合 {sub_account_name} 中没有基金资产")
        return True

    # 安全数值工具（与加仓风向标加仓.py一致）
    def _safe_float(v, default=0.0):
        try:
            if v is None:
                return default
            return float(v)
        except Exception:
            return default
    # 修改：直接从环境变量读取止盈阈值，忽略传入的 profit_threshold 参数
    local_threshold = _safe_float(os.environ.get("JIANLONG_PROFIT_THRESHOLD"), 5.0)
    logger.info(f"止盈收益率阈值设置为: {local_threshold}%")

    success_count = 0

    # 遍历每只持有基金，按统一止盈条件处理
    for asset in user_assets:
        fund_code = getattr(asset, "fund_code", None)
        if not fund_code:
            continue

        fund_info = get_all_fund_info(user, fund_code)
        if not fund_info:
            logger.info(f"跳过 {fund_code}: 未获取到基金基础信息")
            continue

        fund_name = getattr(fund_info, "fund_name", fund_code)

        # 可用份额判定
        available_vol = _safe_float(getattr(asset, "available_vol", 0.0), 0.0)
        if available_vol <= 0.0:
            logger.info(f"{user.customer_name}的基金{fund_name}({fund_code})可用份额为0, 跳过赎回.")
            continue

        # 预估收益率 = 当前收益率 + 估值涨跌幅
        current_profit_rate = _safe_float(getattr(asset, "constant_profit_rate", 0.0), 0.0)
        estimated_change = _safe_float(getattr(fund_info, "estimated_change", 0.0), 0.0)
        estimated_profit_rate = current_profit_rate + estimated_change

        # rank_100day
        r100 = _safe_float(getattr(fund_info, "rank_100day", None), None)

        # 获取月度和季度排名数据
        month_rank_num = None
        quarter_rank_num = None
        try:
            _, month_item_rank, _ = get_fund_growth_rate(fund_info, 'Y')
            if month_item_rank is not None:
                month_rank_num = float(month_item_rank)
            
            _, quarter_item_rank, _ = get_fund_growth_rate(fund_info, '3Y')
            if quarter_item_rank is not None:
                quarter_rank_num = float(quarter_item_rank)
        except Exception as e:
            logger.info(f"获取排名数据异常: {e}")

        # 三条件统一止盈：
        # 1) 预估收益率 > 动态阈值 local_threshold
        # 2) rank_100day > 80
      
      
        # 统一策略：所有基金（含指数）均需满足 cond3
        is_index = getattr(fund_info, 'fund_type', '') == '000'
        cond3 = False
        if month_rank_num is not None and quarter_rank_num is not None:
            cond3 = quarter_rank_num < month_rank_num

        should_take_profit = (
            (estimated_profit_rate is not None and estimated_profit_rate > local_threshold) and
            (r100 is not None and r100 > 80.0) and
            cond3
        )

        logger.info(
            f"{user.customer_name}的基金{fund_name}({fund_code}) "
            f"预估收益率={estimated_profit_rate:.2f}%，rank_100day={r100 if r100 is not None else 'N/A'}, "
            f"Q_Rank={quarter_rank_num}, M_Rank={month_rank_num}, IsIndex={is_index}"
        )

        if not should_take_profit:
            continue

        # 满足止盈条件，执行赎回
        try:
            bank_shares = get_bank_shares(user, sub_account_no, fund_code)
            logger.info(
                f"{user.customer_name}的止盈操作开始：基金{fund_name}({fund_code})满足条件"
                f"（收益率>{local_threshold}%、rank_100>80、Q_Rank<M_Rank）"
            )
            sell_result = sell_low_fee_shares(user, sub_account_no, fund_code, bank_shares)
            if sell_result and getattr(sell_result, "busin_serial_no", None):
                logger.info(f"{user.customer_name}的基金{fund_name}({fund_code})卖出止盈成功")
                success_count += 1
            else:
                logger.warning(f"{user.customer_name}的基金{fund_name}({fund_code})止盈失败")
        except Exception as e:
            logger.error(f"止盈 {fund_code} {fund_name} 失败: {e}")

    logger.info(f"止盈操作完成，成功处理 {success_count} 个基金")
    return success_count > 0

if __name__ == "__main__":
    try:
        redeem_funds(DEFAULT_USER, "见龙在田", 1000000.0)
        logging.info(f"用户 {DEFAULT_USER.customer_name} 止盈操作完成")
    except Exception as e:
        logging.error(f"测试用户处理失败：{str(e)}")
