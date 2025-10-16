import logging
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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
    
    # 获取加仓风向标数据
    wind_vane_funds = get_fund_investment_indicators()
    if not wind_vane_funds:
        logger.error("获取加仓风向标数据失败")
        return False
    
    # 构建风向标集合：非指数用 fund_code，指数用 index_code
    wind_vane_codes = {f.fund_code for f in wind_vane_funds}
    wind_vane_indices = set()
    for f in wind_vane_funds:
        if getattr(f, "fund_type", None) == "000":
            try:
                fi = get_all_fund_info(user, f.fund_code)
                if fi and getattr(fi, "index_code", None):
                    wind_vane_indices.add(fi.index_code)
            except Exception as e:
                logger.warning(f"获取指数风向标 index_code 异常: {f.fund_code}, {e}")
    
    # 引入0费率份额查询（函数内导入以避免顶部变更）
    from src.service.交易管理.费率查询 import get_0_fee_shares
    
    # 第一轮：构建候选并执行赎回0费率份额
    success_count = 0
    post_selection_candidates: List[Tuple] = []  # [(asset, fund_info, estimated_profit_rate)]
    # 新增：跳过原因统计
    skip_stats = {
        "no_fund_info": 0,
        "index_threshold_not_met": 0,
        "index_zero_fee_none": 0,
        "non_index_in_wind_vane_skipped": 0,
        "non_index_threshold_not_met": 0,
        "non_index_week_return_non_positive": 0,
        "non_index_rank_checks_failed": 0,
    }
    
    def _safe_float(v, default=0.0):
        try:
            if v is None:
                return default
            return float(v)
        except Exception:
            return default
    
    # 第一轮遍历：根据规则加入候选
    for asset in user_assets:
        fund_code = asset.fund_code
        fund_info = get_all_fund_info(user, fund_code)
        if not fund_info:
            skip_stats["no_fund_info"] += 1
            logger.info(f"后选跳过：无法获取基金信息 {fund_code}")
            continue
        
        fund_name = getattr(fund_info, "fund_name", fund_code)
        fund_type = getattr(fund_info, "fund_type", None)
        
        # 判断是否在风向标中
        in_wind_vane = False
        if fund_type == "000":  # 指数
            idx_code = getattr(fund_info, "index_code", None)
            in_wind_vane = idx_code in wind_vane_indices if idx_code else False
        else:
            in_wind_vane = fund_code in wind_vane_codes
        
        # 预估收益率 = 当前收益率 + 估值涨跌
        current_profit_rate = _safe_float(getattr(asset, "constant_profit_rate", 0.0), 0.0)
        estimated_change = _safe_float(getattr(fund_info, "estimated_change", 0.0), 0.0)
        estimated_profit_rate = current_profit_rate + estimated_change
        
        # 0费率份额
        zero_fee_shares = _safe_float(get_0_fee_shares(user, fund_code), 0.0)
        
        if fund_type == "000":
            # 指数基金
            if in_wind_vane:
                if estimated_profit_rate > 5.0 and zero_fee_shares > 0.0:
                    post_selection_candidates.append((asset, fund_info, estimated_profit_rate))
                    logger.info(f"后选加入（指数/风向标中，阈值5.0）：{fund_name}({fund_code}) 预估收益={estimated_profit_rate:.2f}% 0费率份额={zero_fee_shares:.2f}")
                else:
                    reasons = []
                    if estimated_profit_rate <= 5.0:
                        reasons.append("预估收益率<=5.0")
                        skip_stats["index_threshold_not_met"] += 1
                    if zero_fee_shares <= 0.0:
                        reasons.append("0费率份额=0")
                        skip_stats["index_zero_fee_none"] += 1
                    logger.info(f"后选跳过（指数/风向标中）：{fund_name}({fund_code}) 原因={','.join(reasons)} 预估收益={estimated_profit_rate:.2f}% 0费率份额={zero_fee_shares:.2f}")
            else:
                if estimated_profit_rate > 3.0 and zero_fee_shares > 0.0:
                    post_selection_candidates.append((asset, fund_info, estimated_profit_rate))
                    logger.info(f"后选加入（指数/非风向标，阈值3.0）：{fund_name}({fund_code}) 预估收益={estimated_profit_rate:.2f}% 0费率份额={zero_fee_shares:.2f}")
                else:
                    reasons = []
                    if estimated_profit_rate <= 3.0:
                        reasons.append("预估收益率<=3.0")
                        skip_stats["index_threshold_not_met"] += 1
                    if zero_fee_shares <= 0.0:
                        reasons.append("0费率份额=0")
                        skip_stats["index_zero_fee_none"] += 1
                    logger.info(f"后选跳过（指数/非风向标）：{fund_name}({fund_code}) 原因={','.join(reasons)} 预估收益={estimated_profit_rate:.2f}% 0费率份额={zero_fee_shares:.2f}")
        else:
            # 非指数基金：在风向标中则跳过
            if in_wind_vane:
                skip_stats["non_index_in_wind_vane_skipped"] += 1
                logger.info(f"非指数基金在加仓风向标中，按规则跳过：{fund_name}({fund_code})")
                continue
            
            # 严格条件
            if estimated_profit_rate > 5.0 and zero_fee_shares > 0.0:
                week_growth_rate = _safe_float(getattr(fund_info, "week_return", None), 0.0)
                if week_growth_rate <= 0.0:
                    skip_stats["non_index_week_return_non_positive"] += 1
                    logger.info(f"非指数后选检查：{fund_name}({fund_code}) 周收益率<=0，跳过")
                    continue
                
                month_rank_rate = None
                try:
                    _, month_item_rank, month_item_sc = get_fund_growth_rate(fund_info, 'Y')
                    if month_item_rank is not None and month_item_sc is not None:
                        denom = float(month_item_sc)
                        if denom != 0.0:
                            month_rank_rate = float(month_item_rank) / denom
                except Exception as e:
                    logger.info(f"获取月度排名数据异常: {e}")
                
                r100 = _safe_float(getattr(fund_info, "rank_100day", None), None)
                
                if (month_rank_rate is not None and month_rank_rate > 0.25) and (r100 is not None and r100 < 90.0):
                    post_selection_candidates.append((asset, fund_info, estimated_profit_rate))
                    logger.info(f"后选加入（非指数/严格条件）：{fund_name}({fund_code}) 预估收益={estimated_profit_rate:.2f}% 周收益率={week_growth_rate:.2f}% "
                                f"month_rank_rate={month_rank_rate:.3f} rank_100day={r100}")
                else:
                    skip_stats["non_index_rank_checks_failed"] += 1
                    logger.info(f"非指数后选检查未通过：{fund_name}({fund_code}) month_rank_rate={month_rank_rate if month_rank_rate is not None else 'N/A'} rank_100day={r100 if r100 is not None else 'N/A'}")
            else:
                skip_stats["non_index_threshold_not_met"] += 1
                logger.info(f"后选跳过（非指数/阈值未达）：{fund_name}({fund_code}) 预估收益={estimated_profit_rate:.2f}% 0费率份额={zero_fee_shares:.2f}")
    
    # 新增：候选阶段跳过统计汇总
    logger.info(
        f"第一轮后选候选统计：候选={len(post_selection_candidates)}，跳过："
        f"无信息={skip_stats['no_fund_info']}，指数阈值未过={skip_stats['index_threshold_not_met']}，指数0费率=0={skip_stats['index_zero_fee_none']}，"
        f"非指数在风向标中跳过={skip_stats['non_index_in_wind_vane_skipped']}，非指数阈值未过={skip_stats['non_index_threshold_not_met']}，"
        f"非指数周收益<=0={skip_stats['non_index_week_return_non_positive']}，非指数排名未达标={skip_stats['non_index_rank_checks_failed']}"
    )
    # 第一轮执行：对候选逐一赎回“0费率份额”（按预估收益率从高到低排序，最多3个）
    if len(post_selection_candidates) > 0:
        post_selection_candidates.sort(key=lambda x: x[2], reverse=True)
        max_redeems = 3
        selected_candidates = post_selection_candidates[:max_redeems]
        logger.info(f"第一轮止盈候选共 {len(post_selection_candidates)} 个，按预估收益率排序后拟处理前 {len(selected_candidates)} 个")
        for asset, fund_info, est_profit in selected_candidates:
            fund_code = asset.fund_code
            fund_name = getattr(fund_info, "fund_name", fund_code)
            try:
                shares = get_bank_shares(user, sub_account_no, fund_code)
                logger.info(f"{user.customer_name} 第一轮止盈：赎回0费率份额（按当天预估收益率降序） {fund_name}({fund_code}) 预估收益率={est_profit:.2f}%")
                redeem_ok = bool(sell_0_fee_shares(user, sub_account_no, fund_code, shares))
                if redeem_ok:
                    success_count += 1  # 仅统计真正成功的赎回
                else:
                    logger.info(f"{user.customer_name} 第一轮止盈未成功或被跳过：{fund_name}({fund_code})")
            except Exception as e:
                logger.error(f"第一轮止盈失败：{fund_name}({fund_code}) 异常={e}")
    
    # 组合资产总和与预算比例
    total_asset_value = sum(_safe_float(getattr(a, "asset_value", 0.0), 0.0) for a in user_assets)
    if total_budget:
        asset_budget_ratio = (total_asset_value / total_budget) * 100.0
        logger.info(f"组合资产总和: {total_asset_value:.2f} 占总预算比例: {asset_budget_ratio:.2f}%")
    
    # 第二轮（特殊止盈）触发条件：
    # 1) 第一轮无候选
    # 2) 组合基金数量 > 20
    # 3) 当天累计止盈数量 < 3
    # 4) 组合资产总和 > 预算的 80%
    eligible_for_special_take_profit = (
        len(post_selection_candidates) == 0
        and fund_count > 15
        and success_count < 3
        and (total_budget is not None and total_budget > 0.0)
        and total_asset_value > total_budget * 0.8
    )
    
    if eligible_for_special_take_profit:
        logger.info("满足特殊止盈触发条件，执行第二轮在风向标内的非指数基金中的择优止盈")
        best_candidate = None  # (asset, fund_info, est_profit)
        
        for asset in user_assets:
            fund_code = asset.fund_code
            fund_info = get_all_fund_info(user, fund_code)
            if not fund_info:
                logger.info(f"第二轮跳过：无法获取基金信息 {fund_code}")
                continue
            
            fund_type = getattr(fund_info, "fund_type", None)
            if fund_type == "000":
                # 第二轮仅在非指数基金中选择
                continue
            
            in_wind_vane = fund_code in wind_vane_codes
            if not in_wind_vane:
                logger.info(f"第二轮跳过：不在风向标内 {fund_code}")
                continue
            
            current_profit_rate = _safe_float(getattr(asset, "constant_profit_rate", 0.0), 0.0)
            estimated_change = _safe_float(getattr(fund_info, "estimated_change", 0.0), 0.0)
            estimated_profit_rate = current_profit_rate + estimated_change
            zero_fee_shares = _safe_float(get_0_fee_shares(user, fund_code), 0.0)
            
            if estimated_profit_rate > 5.0 and zero_fee_shares > 0.0:
                if best_candidate is None or estimated_profit_rate > best_candidate[2]:
                    best_candidate = (asset, fund_info, estimated_profit_rate)
            else:
                reasons = []
                if estimated_profit_rate <= 5.0:
                    reasons.append("预估收益率<=5.0")
                if zero_fee_shares <= 0.0:
                    reasons.append("0费率份额=0")
                logger.info(f"第二轮跳过候选：{fund_code} 原因={','.join(reasons)} 预估收益={estimated_profit_rate:.2f}% 0费率份额={zero_fee_shares:.2f}")
        
        if best_candidate is not None:
            asset, fund_info, est_profit = best_candidate
            fund_code = asset.fund_code
            fund_name = getattr(fund_info, "fund_name", fund_code)
            try:
                shares = get_bank_shares(user, sub_account_no, fund_code)
                # 基金名称含“C”则赎回0费率份额；否则赎回低费率份额
                if "C" in str(fund_name):
                    logger.info(f"{user.customer_name} 第二轮特殊止盈：C类基金优先赎回0费率份额 {fund_name}({fund_code}) 预估收益={est_profit:.2f}%")
                    redeem_ok = bool(sell_0_fee_shares(user, sub_account_no, fund_code, shares))
                else:
                    logger.info(f"{user.customer_name} 第二轮特殊止盈：非C类基金优先赎回低费率份额 {fund_name}({fund_code}) 预估收益={est_profit:.2f}%")
                    redeem_ok = bool(sell_low_fee_shares(user, sub_account_no, fund_code, shares))
                if redeem_ok:
                    success_count += 1  # 仅统计真正成功的赎回
                else:
                    logger.info(f"{user.customer_name} 第二轮特殊止盈未成功或被跳过：{fund_name}({fund_code})")
            except Exception as e:
                logger.error(f"第二轮止盈失败：{fund_name}({fund_code}) 异常={e}")
        else:
            logger.info("第二轮未找到符合条件的非指数风向标内基金，跳过特殊止盈")
    
    logger.info(f"止盈完成：{user.customer_name} 成功执行 {success_count} 次赎回操作")
    return True

if __name__ == "__main__":
    try:
        redeem_funds(DEFAULT_USER, "Martin Geggs", 1000000.0)
        logging.info(f"用户 {DEFAULT_USER.customer_name} 止盈操作完成")
    except Exception as e:
        logging.error(f"测试用户处理失败：{str(e)}")