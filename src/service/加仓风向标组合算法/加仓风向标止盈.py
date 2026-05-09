# 顶部导入片段
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
from src.service.大数据.加仓风向标服务 import get_fund_investment_indicators
from src.common.constant import DEFAULT_USER
from src.API.资产管理.AssetManager import GetMyAssetMainPartAsync
from src.API.基金信息.FundRank import get_fund_growth_rate, get_fund_volatility
from src.service.交易管理.赎回基金 import sell_low_fee_shares, sell_0_fee_shares, sell_usable_non_zero_fee_shares
from src.service.公共服务.nav_gate_service import nav5_gate, nav5_fall_gate

logger = get_logger(__name__)

from src.service.公共服务.risk_control_service import check_hqb_risk_allowed

def redeem_funds(user: User, sub_account_name: str, total_budget: Optional[float] = None) -> bool:
    customer_name = user.customer_name
    logger.info(f"开始为用户 {customer_name} 执行止盈操作，组合: {sub_account_name}")
    
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
    
    # 检查组合持有基金数量
    fund_count = len(user_assets)
    logger.info(f"组合中共有 {fund_count} 个基金资产")
    
    # 引入费率份额查询（函数内导入，避免顶部改动）
    from src.service.交易管理.费率查询 import get_low_fee_shares
    
    success_count = 0

    def _safe_float(v, default=0.0):
        try:
            if v is None:
                return default
            return float(v)
        except Exception:
            return default

    logger.info("采用新止盈策略：针对指数型(000)与非指数型(001,002)分别计算30日波动率设定止盈点")

    for asset in user_assets:
        if success_count >= 3:
            break

        fund_code = asset.fund_code
        fund_info = get_all_fund_info(user, fund_code)
        if not fund_info:
            logger.info(f"跳过：无法获取基金信息 {fund_code}")
            continue

        fund_name = getattr(fund_info, "fund_name", fund_code)
        fund_type = getattr(fund_info, "fund_type", None)

        if fund_type not in ["000", "001", "002"]:
            logger.info(f"跳过：{fund_name}({fund_code}) 基金类型为 {fund_type}，不在支持的类型(000, 001, 002)内")
            continue

        # 预估收益率
        current_profit_rate = _safe_float(getattr(asset, "constant_profit_rate", 0.0), 0.0)
        estimated_change = _safe_float(getattr(fund_info, "estimated_change", 0.0), 0.0)
        estimated_profit_rate = current_profit_rate + estimated_change

        # 波动率对齐
        volatility = fund_info.volatility if fund_info and hasattr(fund_info, "volatility") and fund_info.volatility is not None else 0.0

        if fund_type == "000":
            stop_rate = min(max(float(volatility), 3.0), 10.0)
        else:
            stop_rate = min(max(float(volatility), 5.0), 15.0)

        # 100个交易日排名
        rank_100 = getattr(fund_info, "rank_100day", None)

        if estimated_profit_rate > stop_rate:
            try:
                shares = get_bank_shares(user, sub_account_no, fund_code)
                
                # 分层止盈逻辑
                if rank_100 is not None and rank_100 > 90:
                    # 满足更高要求，卖出所有低费率份额（卖出更多）
                    low_fee_shares = _safe_float(get_low_fee_shares(user, fund_code), 0.0)
                    if low_fee_shares > 10.0:
                        logger.info(
                            f"{user.customer_name} 分层止盈(rank_100>90)：{fund_name}({fund_code}) 预估={estimated_profit_rate:.2f}% "
                            f"止盈点={stop_rate:.2f}% 波动率={volatility:.2f} 100日排名={rank_100} 低费率份额={low_fee_shares:.2f}，执行卖出低费率份额"
                        )
                        redeem_ok = bool(sell_low_fee_shares(user, sub_account_no, fund_code, shares))
                        if redeem_ok:
                            success_count += 1
                        else:
                            logger.info(f"{user.customer_name} 低费率止盈未成功：{fund_name}({fund_code})")
                    else:
                        logger.info(f"跳过低费率止盈：{fund_name}({fund_code}) 低费率份额≤10 预估={estimated_profit_rate:.2f}% 止盈点={stop_rate:.2f}%")
                else:
                    # 仅满足基本收益率要求，卖出0费率份额（卖出较少，更保守）
                    logger.info(
                        f"{user.customer_name} 分层止盈(仅收益达标)：{fund_name}({fund_code}) 预估={estimated_profit_rate:.2f}% "
                        f"止盈点={stop_rate:.2f}% 波动率={volatility:.2f} 100日排名={rank_100}，执行卖出0费率份额"
                    )
                    redeem_ok = bool(sell_0_fee_shares(user, sub_account_no, fund_code, shares))
                    if redeem_ok:
                        success_count += 1
                    else:
                        logger.info(f"{user.customer_name} 0费率止盈未成功：{fund_name}({fund_code})")
                        
            except Exception as e:
                logger.error(f"止盈失败：{fund_name}({fund_code}) 异常={e}")
        else:
            logger.info(f"跳过：{fund_name}({fund_code}) 预估收益未达标（预估={estimated_profit_rate:.2f}%, 止盈点={stop_rate:.2f}%, 100日排名={rank_100}）")

    logger.info(f"止盈完成：{user.customer_name} 成功执行 {success_count} 次赎回操作（最多3个）")
    return True

if __name__ == "__main__":
    try:
        redeem_funds(DEFAULT_USER, "飞龙在天", 1000000.0)
        # redeem_funds(DEFAULT_USER, "马丁格尔plus", 1000000.0)
        logging.info(f"用户 {DEFAULT_USER.customer_name} 止盈操作完成")
    except Exception as e:
        logging.error(f"测试用户处理失败：{str(e)}")
