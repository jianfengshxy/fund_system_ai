import logging
from src.common.logger import get_logger
import os
import sys
from typing import Optional, List, Tuple

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.domain.user.User import User
from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.service.基金信息.基金信息 import get_all_fund_info
from src.API.交易管理.trade import get_bank_shares
from src.service.大数据.加仓风向标服务 import get_fund_investment_indicators
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

    # 新增：获取加仓风向标集合（与风向标系列一致）
    wind_vane_codes = set()
    wind_vane_indices = set()
    try:
        wind_vane_funds = get_fund_investment_indicators()
        if wind_vane_funds:
            wind_vane_codes = {getattr(f, 'fund_code', '') for f in wind_vane_funds if getattr(f, 'fund_code', None)}
            wind_vane_indices = {
                getattr(get_all_fund_info(user, f.fund_code), 'index_code', None)
                for f in wind_vane_funds
                if getattr(f, 'fund_type', None) == '000'
            }
            wind_vane_indices = {idx for idx in wind_vane_indices if idx}  # 去除 None
        else:
            logger.warning("获取加仓风向标数据为空，按常规止盈逻辑继续")
    except Exception as e:
        logger.warning(f"获取加仓风向标数据异常，按常规止盈逻辑继续：{e}")

    # 安全数值工具（与加仓风向标加仓.py一致）
    def _safe_float(v, default=0.0):
        try:
            if v is None:
                return default
            return float(v)
        except Exception:
            return default
    # 新增：将外部传入的止盈阈值做安全转换，默认 20
    local_threshold = _safe_float(profit_threshold, 20.0)
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

        # 新增：在风向标中则跳过止盈（指数按 index_code，非指数按 fund_code）
        in_wind_vane = False
        try:
            ftype = getattr(fund_info, "fund_type", None)
            if ftype == '000':
                idx_code = getattr(fund_info, "index_code", None)
                in_wind_vane = (idx_code in wind_vane_indices) if idx_code else False
            else:
                in_wind_vane = (fund_code in wind_vane_codes)
        except Exception:
            in_wind_vane = False

        if in_wind_vane:
            logger.info(f"{user.customer_name}的基金{fund_name}({fund_code})在加仓风向标中，跳过止盈")
            continue

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

        # 季度百分位排名（3Y 数据，做分母校验）
        season_rank_rate = None
        try:
            _, season_item_rank, season_item_sc = get_fund_growth_rate(fund_info, '3Y')
            if season_item_rank is not None and season_item_sc is not None:
                denom = float(season_item_sc)
                if denom != 0.0:
                    season_rank_rate = float(season_item_rank) / denom
        except Exception as e:
            logger.info(f"获取季度排名数据异常: {e}")

        # 三条件统一止盈：
        # 1) 预估收益率 > 动态阈值 local_threshold
        # 2) rank_100day < 90
        # 3) season_rank_rate > 0.25（开始掉出前1/4）
        should_take_profit = (
            (estimated_profit_rate is not None and estimated_profit_rate > local_threshold) and
            (r100 is not None and r100 < 90.0) and
            (season_rank_rate is not None and season_rank_rate > 0.25)
        )

        logger.info(
            f"{user.customer_name}的基金{fund_name}({fund_code}) "
            f"预估收益率={estimated_profit_rate:.2f}%，rank_100day={r100 if r100 is not None else 'N/A'}, "
            f"season_rank_rate={season_rank_rate if season_rank_rate is not None else 'N/A'}"
        )

        if not should_take_profit:
            continue

        # 满足止盈条件，执行赎回
        try:
            bank_shares = get_bank_shares(user, sub_account_no, fund_code)
            logger.info(
                f"{user.customer_name}的止盈操作开始：基金{fund_name}({fund_code})满足条件"
                f"（收益率>{local_threshold}%、rank_100<90、季度百分位>25%）"
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
