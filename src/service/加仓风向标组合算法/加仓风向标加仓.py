# 顶部导入片段
import os
import sys

# 获取项目根目录路径并添加到 Python 路径（必须在导入 src 模块之前）
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import logging
import math
from typing import Dict, Optional

from src.common.logger import get_logger

from src.domain.user.User import User
from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.service.基金信息.基金信息 import get_all_fund_info
from src.API.交易管理.trade import get_trades_list, get_bank_shares
from src.service.交易管理.购买基金 import commit_order
from src.service.大数据.加仓风向标服务 import get_fund_investment_indicators
from src.common.constant import DEFAULT_USER
from src.API.基金信息.FundRank import get_fund_growth_rate
from src.service.交易管理.交易查询 import count_success_trades_on_prev_nav_day
from src.service.公共服务.nav_gate_service import nav5_gate
from src.service.公共服务.trade_guard_service import has_buy_submission_on_dates
from src.service.公共服务.estimated_profit_service import calc_estimated_change, calc_estimated_profit_rate
# 新增导入 get_user_all_info
from src.service.用户管理.用户信息 import get_user_all_info


def _safe_float(v, default=0.0):
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _get_primary_theme(fund_info):
    """
    提取主动型基金主主题，口径与加仓风向标新增/估值逻辑一致：
    1. 优先 theme_infos 中 isshow=True 的首个主题
    2. 否则退回 relate_themes 中 corr_1y 最高的主题
    """
    if not fund_info:
        return None

    theme_infos = getattr(fund_info, "theme_infos", None) or []
    show_themes = [theme for theme in theme_infos if getattr(theme, "isshow", False)]
    if show_themes:
        theme = show_themes[0]
        sec_code = str(getattr(theme, "sec_code", "") or "").strip()
        sec_name = str(getattr(theme, "sec_name", "") or "").strip()
        if sec_code or sec_name:
            return sec_code, sec_name

    relate_themes = getattr(fund_info, "relate_themes", None) or []
    if relate_themes:
        theme = max(relate_themes, key=lambda item: _safe_float(getattr(item, "corr_1y", 0.0), 0.0))
        sec_code = str(getattr(theme, "sec_code", "") or "").strip()
        sec_name = str(getattr(theme, "sec_name", "") or "").strip()
        if sec_code or sec_name:
            return sec_code, sec_name

    return None


def _get_group_key_and_label(fund_info) -> tuple[Optional[str], str]:
    """为基金生成同类分组键：指数基金按指数，主动基金按主题。"""
    if not fund_info:
        return None, "未知分组"

    fund_type = str(getattr(fund_info, "fund_type", "") or "").strip()
    if fund_type == "000":
        index_code = str(getattr(fund_info, "index_code", "") or "").strip()
        if index_code:
            return f"index:{index_code}", f"同指数({index_code})"
        return None, "未知分组"

    theme = _get_primary_theme(fund_info)
    if not theme:
        return None, "未知分组"

    sec_code, sec_name = theme
    if sec_code:
        return f"sec_code:{sec_code}", f"同主题({sec_name or sec_code})"
    if sec_name:
        return f"sec_name:{sec_name}", f"同主题({sec_name})"
    return None, "未知分组"


def _calc_post_add_profit_rate(current_asset_value: float, estimated_profit_rate: float, buy_amount: float) -> float:
    """
    计算“按当前标准金额加仓后，新的持有收益率是多少”。
    分值越高（越接近 0 或转正），说明越可能更快靠近止盈线。
    """
    asset_value = _safe_float(current_asset_value, 0.0)
    buy = _safe_float(buy_amount, 0.0)
    rate_pct = _safe_float(estimated_profit_rate, 0.0)
    rate = rate_pct / 100.0

    if asset_value <= 0.0 or rate <= -0.999:
        return rate_pct
    if buy <= 0.0 or rate >= 0.0:
        return rate_pct

    current_cost = asset_value / (1.0 + rate)
    if current_cost <= 0.0:
        return rate_pct

    new_rate = ((asset_value + buy) / (current_cost + buy)) - 1.0
    return new_rate * 100.0


def _get_max_funds_threshold():
    env_val = os.environ.get('MAX_FUNDS_THRESHOLD')
    if env_val is None or env_val == "":
        return 20
    try:
        return int(env_val)
    except ValueError:
        logger.warning(f"环境变量 MAX_FUNDS_THRESHOLD 非法值: {env_val}，回退为默认 20")
        return 20

import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = get_logger(__name__)

def increase_funds(user: User, sub_account_name: str, total_budget: float, amount: Optional[float] = None, fund_type: str = 'all', fund_num: int = 5, spread_days: int = 5) -> bool:
    """
    加仓（最小集成落地版）：
    - fund_num: 本次最多下单次数（默认5）
    - spread_days: 预算摊薄天数（默认20），仅在未传入amount时生效
    - 若余额不足，动态下调 buy_amount（至少10元）
    """
    logger.info(f"[加仓参数] 用户={getattr(user,'customer_name','N/A')} | 组合={sub_account_name} | fund_num={fund_num} | spread_days={spread_days}")
    # 计算基础单笔金额（与新增金额保持一致，再乘2）
    if amount is not None:
        base_amount = float(amount) * 2
    else:
        MAX_FUNDS_THRESHOLD = _get_max_funds_threshold()
        base_amount = round(total_budget / max(MAX_FUNDS_THRESHOLD, 1) / max(spread_days, 1), 2) * 2
    logger.info(f"[买入金额] 单只基础买入金额={base_amount} 元(是新增金额的2倍)")
    buy_amount = base_amount
    fund_info_cache: Dict[str, Optional[object]] = {}

    def _get_cached_fund_info(fund_code: str):
        if not fund_code:
            return None
        if fund_code not in fund_info_cache:
            fund_info_cache[fund_code] = get_all_fund_info(user, fund_code)
        return fund_info_cache[fund_code]

    # 获取子账户
    sub_account_no = getSubAccountNoByName(user, sub_account_name)
    if not sub_account_no:
        logger.error(f"未找到组合 {sub_account_name} 的账号")
        return False

    # 准备风向标集合
    wind_vane_funds = get_fund_investment_indicators(user=user)
    if not wind_vane_funds:
        logger.error("获取加仓风向标数据失败")
        return False
    if fund_type == 'index':
        wind_vane_funds = [f for f in wind_vane_funds if f.fund_type == '000']
    elif fund_type == 'non_index':
        wind_vane_funds = [f for f in wind_vane_funds if f.fund_type != '000']
    wind_vane_codes = {f.fund_code for f in wind_vane_funds}
    wind_vane_indices = {
        getattr(fi, "index_code", None)
        for f in wind_vane_funds
        if f.fund_type == '000'
        for fi in [_get_cached_fund_info(f.fund_code)]
        if fi and getattr(fi, "index_code", None)
    }

    # 获取持仓
    user_assets = get_sub_account_asset_by_name(user, sub_account_name)
    if not user_assets:
        logger.info(f"组合 {sub_account_name} 中没有基金资产")
        return True

    # 预筛选并打标，然后按“风向标优先”排序
    enriched = []
    group_best_candidates = {}
    for asset in user_assets:
        fund_code = asset.fund_code
        fi = _get_cached_fund_info(fund_code)
        if not fi:
            logger.info(f"跳过 {fund_code}: 未获取到基金基础信息")
            continue

        current_profit_rate = _safe_float(getattr(asset, "constant_profit_rate", 0.0), 0.0)
        estimated_change, label_est = calc_estimated_change(fi)
        estimated_profit_rate = current_profit_rate + estimated_change

        # 公共前置过滤：仅保留跌幅足够的标的
        if estimated_profit_rate >= -1.0:
            logger.info(f"[跳过] {fi.fund_name}({fund_code}) | 原因: 回撤不达标 estimated_profit_rate={estimated_profit_rate:.2f}%（阈值<-1.00%，current={current_profit_rate:.2f}%, change={estimated_change:.2f}%, {label_est}）")
            continue

        in_wind_vane = (fi.fund_type != '000' and fund_code in wind_vane_codes) or (fi.fund_type == '000' and fi.index_code in wind_vane_indices)
        current_asset_value = _safe_float(getattr(asset, "asset_value", 0.0), 0.0)
        group_key, group_label = _get_group_key_and_label(fi)
        post_add_profit_rate = _calc_post_add_profit_rate(current_asset_value, estimated_profit_rate, buy_amount)
        enriched.append((asset, fi, in_wind_vane, estimated_profit_rate, group_key, group_label, post_add_profit_rate))

        if group_key:
            candidate = group_best_candidates.get(group_key)
            current_candidate = {
                "fund_code": fund_code,
                "fund_name": fi.fund_name,
                "group_label": group_label,
                "post_add_profit_rate": post_add_profit_rate,
                "estimated_profit_rate": estimated_profit_rate,
                "asset_value": current_asset_value,
                "in_wind_vane": in_wind_vane,
            }
            if (
                candidate is None
                or current_candidate["post_add_profit_rate"] > candidate["post_add_profit_rate"]
                or (
                    math.isclose(current_candidate["post_add_profit_rate"], candidate["post_add_profit_rate"], rel_tol=1e-9, abs_tol=1e-9)
                    and current_candidate["estimated_profit_rate"] > candidate["estimated_profit_rate"]
                )
                or (
                    math.isclose(current_candidate["post_add_profit_rate"], candidate["post_add_profit_rate"], rel_tol=1e-9, abs_tol=1e-9)
                    and math.isclose(current_candidate["estimated_profit_rate"], candidate["estimated_profit_rate"], rel_tol=1e-9, abs_tol=1e-9)
                    and current_candidate["asset_value"] < candidate["asset_value"]
                )
            ):
                group_best_candidates[group_key] = current_candidate

    # 关键：风向标在前；组内按 estimated_profit_rate 升序（跌幅越大越优先）
    for candidate in group_best_candidates.values():
        logger.info(
            f"[同类优先] {candidate['group_label']} 仅保留 {candidate['fund_name']}({candidate['fund_code']}) "
            f"作为当前加仓代表，post_add_profit_rate={candidate['post_add_profit_rate']:.4f}%, "
            f"estimated_profit_rate={candidate['estimated_profit_rate']:.2f}%, asset_value={candidate['asset_value']:.2f}"
        )

    enriched.sort(key=lambda t: (not t[2], t[3]))
    logger.info("排序策略：风向标优先；组内按回撤深度（estimated_profit_rate 越小越优先）")
    # 风向标在前，非风向标在后
    enriched.sort(key=lambda t: (not t[2],))
    success_count = 0
    orders_made = 0
    logger.info("本次加仓处理顺序：风向标基金优先")
    
    # 计算当前组合总资产
    current_total_asset = 0.0
    for asset in user_assets:
        current_total_asset += _safe_float(getattr(asset, "asset_value", 0.0), 0.0)
    logger.info(f"[组合资产] 当前组合总资产={current_total_asset:.2f} | 总预算={total_budget:.2f}")

    # 加仓流程中风向标路径的判定替换
    for asset, fi, in_wind_vane, estimated_profit_rate, group_key, group_label, post_add_profit_rate in enriched:
        if orders_made >= fund_num:
            logger.info(f"已达本次下单上限 {fund_num} 笔，提前结束")
            break

        fund_code = asset.fund_code
        fund_name = fi.fund_name

        if group_key:
            best_candidate = group_best_candidates.get(group_key)
            if best_candidate and best_candidate["fund_code"] != fund_code:
                logger.info(
                    f"[同类跳过] {fund_name}({fund_code}) | {group_label} | "
                    f"post_add_profit_rate={post_add_profit_rate:.4f}%，当前优先处理 "
                    f"{best_candidate['fund_name']}({best_candidate['fund_code']}) "
                    f"(post_add_profit_rate={best_candidate['post_add_profit_rate']:.4f}%)"
                )
                continue

        # 统一使用公共服务的5日均值判定（覆盖风向标与非风向标）
        prefixed_name = f"风向标 {fund_name}" if in_wind_vane else fund_name
        logger.info(f"[基金处理] {prefixed_name}({fund_code}) | 类型={'风向标' if in_wind_vane else '非风向标'} | 预估回撤={estimated_profit_rate:.2f}% | 单笔金额={buy_amount:.2f}")
        
        # 检查步骤1: 5日均值判定
        if not nav5_gate(fi, prefixed_name, fund_code, logger):
            logger.info(f"[检查失败] 步骤1-5日均值判定未通过")
            continue
        logger.info(f"[检查通过] 步骤1-5日均值判定 ✓")

        # 检查步骤2: 公共排名检查
        rank_100 = getattr(fi, "rank_100day", None)
        rank_30 = getattr(fi, "rank_30day", None)
        if not isinstance(rank_100, (int, float)) or not isinstance(rank_30, (int, float)):
            logger.info(f"[检查失败] 步骤2-排名数据缺失 (rank_100day={rank_100}, rank_30day={rank_30})")
            continue
        if rank_100 < 20 or rank_100 > 90 or rank_30 < 5:
            logger.info(f"[检查失败] 步骤2-排名条件不满足 (期望 20≤rank_100day≤90 且 rank_30day≥5，实际 {rank_100},{rank_30})")
            continue
        logger.info(f"[检查通过] 步骤2-公共排名检查 ✓ (rank_100day={rank_100}, rank_30day={rank_30})")

        # 检查步骤3: 百分位排名检查
        try:
            _, season_item_rank, season_item_sc = get_fund_growth_rate(fi, '3Y')
            _, month_item_rank, month_item_sc = get_fund_growth_rate(fi, 'Y')
        except Exception as e:
            logger.info(f"[检查失败] 步骤3-获取百分位排名数据异常: {e}")
            continue
        
        if not season_item_rank or not season_item_sc or season_item_sc == 0 \
           or not month_item_rank or not month_item_sc or month_item_sc == 0:
            logger.info(f"[检查失败] 步骤3-百分位排名数据不可用 (season: rank={season_item_rank}, sc={season_item_sc}; month: rank={month_item_rank}, sc={month_item_sc})")
            continue

        month_rank_rate = float(month_item_rank) / float(month_item_sc)
        season_rank_rate = float(season_item_rank) / float(season_item_sc)
        if month_rank_rate > 0.75 or season_rank_rate > 0.75:
            logger.info(f"[检查失败] 步骤3-百分位排名过高 (month={month_rank_rate:.2%}, season={season_rank_rate:.2%}，阈值≤75%)")
            continue
        logger.info(f"[检查通过] 步骤3-百分位排名检查 ✓ (month={month_rank_rate:.2%}, season={season_rank_rate:.2%})")

        # 检查步骤4: 单个基金仓位限制（≤15%组合资产）
        safe_asset_value = _safe_float(getattr(asset, "asset_value", 0.0), 0.0)
        if current_total_asset > 0.0:
            position_ratio = safe_asset_value / current_total_asset * 100.0
            if position_ratio > 15.0:
                logger.info(
                    f"[检查失败] 步骤4-单个基金仓位占比过高 (占比={position_ratio:.2f}% > 15.00%，"
                    f"单基金市值={safe_asset_value:.2f}，组合总市值={current_total_asset:.2f})"
                )
                continue
            logger.info(
                f"[检查通过] 步骤4-单个基金仓位限制 ✓ (占比={position_ratio:.2f}% ≤ 15.00%，"
                f"单基金市值={safe_asset_value:.2f}，组合总市值={current_total_asset:.2f})"
            )

        # 检查步骤5: 组合总资产限制（加仓后≤总预算）
        if current_total_asset + buy_amount > float(total_budget):
            logger.info(f"[检查失败] 步骤5-组合总资产超限 (当前={current_total_asset:.2f} + 加仓={buy_amount:.2f} > 总预算={total_budget:.2f})")
            continue
        logger.info(f"[检查通过] 步骤5-组合总资产限制 ✓ (当前={current_total_asset:.2f} + 加仓={buy_amount:.2f} ≤ 总预算={total_budget:.2f})")

        # 记录过滤条件检查结果
        filter_checks = []
        filter_checks.append("✓ 5日均值判定通过（估算净值 > 5日均值）")
        filter_checks.append("✓ 公共排名检查通过（20≤rank_100day≤90 且 rank_30day≥5）")
        filter_checks.append(f"✓ 百分位排名检查通过（month={month_rank_rate:.2%}, season={season_rank_rate:.2%} ≤ 75%）")
        filter_checks.append("✓ 单个基金仓位限制通过（单基金/组合 ≤ 15%）")
        filter_checks.append(f"✓ 组合总资产限制通过（当前={current_total_asset:.2f} + 加仓={buy_amount:.2f} ≤ 总预算={total_budget:.2f}）")

        # 打印过滤条件汇总信息
        logger.info(f"[过滤条件汇总] 基金 {fund_name}({fund_code}) 满足所有条件:")
        for check in filter_checks:
            logger.info(f"  {check}")

        # 步骤6: 不连续交易守卫（通用）：检查上一个交易日是否有有效买入/定投
        try:
            nav_date_str = getattr(fi, "nav_date", None)
            prev_trade_day = datetime.datetime.strptime(nav_date_str, "%Y-%m-%d").date() if nav_date_str else None
        except Exception:
            nav_date_str = None
            prev_trade_day = None
        
        prev_trade_record = has_buy_submission_on_dates(user, sub_account_no, fund_code, prev_trade_day)
        if prev_trade_record:
            state = getattr(prev_trade_record, "app_state_text", None) or getattr(prev_trade_record, "status", None)
            logger.info(f"[检查失败] 步骤6-不连续交易守卫触发 (nav_date={nav_date_str}, 状态={state})")
            continue
        logger.info(f"[检查通过] 步骤6-不连续交易守卫 ✓ (nav_date={nav_date_str})")

        # 步骤7: 当日不重复交易：检查今天是否有有效买入/定投
        today = datetime.date.today()
        today_trade_record = has_buy_submission_on_dates(user, sub_account_no, fund_code, today)
        if today_trade_record:
            state = getattr(today_trade_record, "app_state_text", None) or getattr(today_trade_record, "status", None)
            logger.info(f"[检查失败] 步骤7-当日不重复交易触发 (today={today}, 状态={state})")
            continue
        logger.info(f"[检查通过] 步骤7-当日不重复交易 ✓ (today={today})")

        # 先尝试风向标路径（仅对风向标标的）
        if in_wind_vane:
            try:
                # 为风向标路径添加额外的过滤条件记录
                filter_checks.append("✓ 风向标基金检查通过（在风向标集合中）")
                filter_checks.append("✓ 不连续交易守卫检查通过（无近期买入记录）")

                # 执行加仓
                res = commit_order(user, sub_account_no, fund_code, buy_amount)
                if res:
                    logger.info(f"[加仓成功] {prefixed_name}({fund_code}) | 金额: {buy_amount} | 订单号: {res.busin_serial_no}")
                    orders_made += 1
                    success_count += 1
                    # 更新组合总资产
                    current_total_asset += buy_amount
                    logger.info(f"[资产更新] 组合总资产: {current_total_asset:.2f}")
                if orders_made >= fund_num:
                    break
                continue
            except Exception as e:
                logger.error(f"[加仓异常] 风向标路径失败 {fund_name}({fund_code}): {e}")
                continue

        # 非风向标路径处理
        try:
            # 检查步骤6: 趋势条件检查
            season_growth_rate = _safe_float(getattr(fi, "three_month_return", None), 0.0)
            month_growth_rate = _safe_float(getattr(fi, "month_return", None), 0.0)
            week_growth_rate = _safe_float(getattr(fi, "week_return", None), 0.0)
            if (week_growth_rate < 0.0 and month_growth_rate < 0.0 and season_growth_rate < 0.0) or \
               (season_growth_rate < 0.0 and (month_growth_rate < 0.0 or week_growth_rate < 0.0)) or \
               (season_growth_rate > 0.0 and (month_growth_rate < 0.0 and week_growth_rate < 0.0)):
                logger.info(f"[检查失败] 步骤6-趋势条件不满足 (week={week_growth_rate:.2f}%, month={month_growth_rate:.2f}%, season={season_growth_rate:.2f}%)")
                continue
            logger.info(f"[检查通过] 趋势条件检查 ✓ (week={week_growth_rate:.2f}%, month={month_growth_rate:.2f}%, season={season_growth_rate:.2f}%)")

            # 为非风向标路径添加额外的过滤条件记录
            filter_checks.append(f"✓ 趋势条件检查通过（week={week_growth_rate:.2f}%, month={month_growth_rate:.2f}%, season={season_growth_rate:.2f}%）")
            filter_checks.append("✓ 不连续交易守卫检查通过（无近期买入记录）")

            # 基础加仓
            res1 = commit_order(user, sub_account_no, fund_code, buy_amount)
            if res1:
                logger.info(f"[加仓成功] 基础加仓 | {fund_name}({fund_code}) | 金额: {buy_amount} | 订单号: {res1.busin_serial_no}")
                orders_made += 1
                success_count += 1
                # 更新组合总资产
                current_total_asset += buy_amount
                logger.info(f"[资产更新] 组合总资产: {current_total_asset:.2f}")
            if orders_made >= fund_num:
                break
            
            # -5% 额外加仓
            if estimated_profit_rate < -5.0 and orders_made < fund_num:
                res2 = commit_order(user, sub_account_no, fund_code, buy_amount)
                if res2:
                    logger.info(f"[加仓成功] -5%额外加仓 | {fund_name}({fund_code}) | 金额: {buy_amount} | 订单号: {res2.busin_serial_no}")
                    orders_made += 1
                    success_count += 1
                    # 更新组合总资产
                    current_total_asset += buy_amount
                    logger.info(f"[资产更新] 组合总资产: {current_total_asset:.2f}")
        except Exception as e:
            logger.error(f"规则路径加仓失败 {fund_name}({fund_code}): {e}")

    logger.info(f"加仓完成，本次共下单 {orders_made} 笔，成功 {success_count} 笔")
    return success_count > 0


if __name__ == "__main__":
    # 测试单个用户的加仓流程
    try:
        # 使用默认用户进行测试，无需再获取
        user = DEFAULT_USER
        # user = get_user_all_info("13500819290","guojing1985")
        # 执行加仓操作
        # increase_funds(user, "飞龙在天",1000000.0, None, 'non_index')  # 使用 DEFAULT_USER，并假设参数合适
        increase_funds(user, "马丁格尔plus",1000000.0, None, 'index')  # 使用 DEFAULT_USER，并假设参数合适
        logging.info(f"用户 {user.customer_name} 加仓操作完成")
    except Exception as e:
        logging.error(f"测试用户处理失败：{str(e)}")
