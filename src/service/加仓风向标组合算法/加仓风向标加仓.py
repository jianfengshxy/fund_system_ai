# 顶部导入片段
import logging
from src.common.logger import get_logger
import os
import sys
import math
from typing import Optional

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

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
# 新增导入 get_user_all_info
from src.service.用户管理.用户信息 import get_user_all_info
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
        base_amount = float(amount)
    else:
        MAX_FUNDS_THRESHOLD = _get_max_funds_threshold()
        base_amount = round(total_budget / max(MAX_FUNDS_THRESHOLD, 1) / max(spread_days, 1), 2) * 2
    logger.info(f"[买入金额] 单只基础买入金额={base_amount} 元(是新增金额的2倍)")
    buy_amount = base_amount

    # 获取子账户
    sub_account_no = getSubAccountNoByName(user, sub_account_name)
    if not sub_account_no:
        logger.error(f"未找到组合 {sub_account_name} 的账号")
        return False

    # 准备风向标集合
    wind_vane_funds = get_fund_investment_indicators()
    if not wind_vane_funds:
        logger.error("获取加仓风向标数据失败")
        return False
    if fund_type == 'index':
        wind_vane_funds = [f for f in wind_vane_funds if f.fund_type == '000']
    elif fund_type == 'non_index':
        wind_vane_funds = [f for f in wind_vane_funds if f.fund_type != '000']
    wind_vane_codes = {f.fund_code for f in wind_vane_funds}
    wind_vane_indices = {get_all_fund_info(user, f.fund_code).index_code for f in wind_vane_funds if f.fund_type == '000'}

    # 获取持仓
    user_assets = get_sub_account_asset_by_name(user, sub_account_name)
    if not user_assets:
        logger.info(f"组合 {sub_account_name} 中没有基金资产")
        return True

    # 预筛选并打标，然后按“风向标优先”排序
    enriched = []
    for asset in user_assets:
        fund_code = asset.fund_code
        fi = get_all_fund_info(user, fund_code)
        if not fi:
            logger.info(f"跳过 {fund_code}: 未获取到基金基础信息")
            continue

        # 安全数值工具
        def _safe_float(v, default=0.0):
            try:
                if v is None:
                    return default
                return float(v)
            except Exception:
                return default

        current_profit_rate = _safe_float(getattr(asset, "constant_profit_rate", 0.0), 0.0)
        estimated_change = _safe_float(getattr(fi, "estimated_change", 0.0), 0.0)
        estimated_profit_rate = current_profit_rate + estimated_change

        # 公共前置过滤：仅保留跌幅足够的标的
        if estimated_profit_rate >= -1.0:
            logger.info(f"[跳过] {fi.fund_name}({fund_code}) | 原因: 回撤不达标 estimated_profit_rate={estimated_profit_rate:.2f}%（阈值<-1.00%，current={current_profit_rate:.2f}%, change={estimated_change:.2f}%）")
            continue

        in_wind_vane = (fi.fund_type != '000' and fund_code in wind_vane_codes) or (fi.fund_type == '000' and fi.index_code in wind_vane_indices)
        enriched.append((asset, fi, in_wind_vane, estimated_profit_rate))

    # 关键：风向标在前；组内按 estimated_profit_rate 升序（跌幅越大越优先）
    enriched.sort(key=lambda t: (not t[2], t[3]))
    logger.info("排序策略：风向标优先；组内按回撤深度（estimated_profit_rate 越小越优先）")
    # 风向标在前，非风向标在后
    enriched.sort(key=lambda t: (not t[2],))
    success_count = 0
    orders_made = 0
    logger.info("本次加仓处理顺序：风向标基金优先")

    # 加仓流程中风向标路径的判定替换
    for asset, fi, in_wind_vane, estimated_profit_rate in enriched:
        if orders_made >= fund_num:
            logger.info(f"已达本次下单上限 {fund_num} 笔，提前结束")
            break

        fund_code = asset.fund_code
        fund_name = fi.fund_name

        # 统一使用公共服务的5日均值判定（覆盖风向标与非风向标）
        prefixed_name = f"风向标 {fund_name}" if in_wind_vane else fund_name
        logger.info(f"[处理开始] {prefixed_name}({fund_code}) | 标签={'风向标' if in_wind_vane else '非风向标'} | 预估回撤={estimated_profit_rate:.2f}% | 单笔金额={buy_amount:.2f}")
        if not nav5_gate(fi, prefixed_name, fund_code, logger):
            logger.info(f"[跳过] {prefixed_name}({fund_code}) | 原因: 5日均值判定未通过（详见公共服务日志）")
            continue

        # 先尝试风向标路径（仅对风向标标的）
        if in_wind_vane:
            try:
                safe_asset_value = _safe_float(getattr(asset, "asset_value", 0.0), 0.0)
                logger.info(f"[检查] {prefixed_name}({fund_code}) | 持仓资产={safe_asset_value:.2f} | 预算阈值={float(total_budget):.2f}")
                if safe_asset_value < float(total_budget):
                    # 删除原分支内的 5 日均值判定，避免重复
                    # 原逻辑保持不变（不连续交易守卫、下单等）
                    # 基金级不连续交易守卫（上一个交易日(nav_date)+今天，排除撤单）
                    try:
                        nav_date_str = getattr(fi, "nav_date", None)
                        prev_trade_day = datetime.datetime.strptime(nav_date_str, "%Y-%m-%d").date() if nav_date_str else None
                    except Exception:
                        prev_trade_day = None
                    today = datetime.date.today()
                    date_set = {d for d in [prev_trade_day, today] if d}
                    from src.service.公共服务.trade_guard_service import has_buy_submission_on_dates
                    stay_trade = has_buy_submission_on_dates(user, sub_account_no, fund_code, date_set)
                    if stay_trade:
                        state = getattr(stay_trade, "app_state_text", None) or getattr(stay_trade, "status", None)
                        logger.info(f"[跳过] {prefixed_name}({fund_code}) | 原因: 不连续交易守卫触发（状态={state}）")
                        continue

                    res = commit_order(user, sub_account_no, fund_code, buy_amount)
                    if res:
                        logger.info(f"[加仓成功] {prefixed_name}({fund_code}) | 金额: {buy_amount} | 订单号: {res.busin_serial_no}")
                        orders_made += 1
                        success_count += 1
                    if orders_made >= fund_num:
                        break
                else:
                    logger.info(f"[跳过] {prefixed_name}({fund_code}) | 原因: 持仓资产 {safe_asset_value} >= 本次预算阈值 {total_budget}（不重复加仓）")
                continue
            except Exception as e:
                logger.error(f"风向标加仓失败 {fund_name}({fund_code}): {e}")
                continue

        # 非风向标路径（原分支内的 5 日均值判定已前置并统一）
        try:
            rank_100 = getattr(fi, "rank_100day", None)
            rank_30 = getattr(fi, "rank_30day", None)
            if not isinstance(rank_100, (int, float)) or not isinstance(rank_30, (int, float)):
                logger.info(f"[跳过] {fund_name}({fund_code}) | 原因: 排名数据缺失（rank_100day={rank_100}, rank_30day={rank_30}）")
                continue
            if rank_100 < 20 or rank_100 > 90 or rank_30 < 5:
                logger.info(f"[跳过] {fund_name}({fund_code}) | 原因: 排名条件不满足（期望 20<=rank_100day<=90 且 rank_30day>=5），实际 rank_100day={rank_100}, rank_30day={rank_30}")
                continue

            season_growth_rate = _safe_float(getattr(fi, "three_month_return", None), 0.0)
            month_growth_rate = _safe_float(getattr(fi, "month_return", None), 0.0)
            week_growth_rate = _safe_float(getattr(fi, "week_return", None), 0.0)
            if (week_growth_rate < 0.0 and month_growth_rate < 0.0 and season_growth_rate < 0.0) or \
               (season_growth_rate < 0.0 and (month_growth_rate < 0.0 or week_growth_rate < 0.0)) or \
               (season_growth_rate > 0.0 and (month_growth_rate < 0.0 and week_growth_rate < 0.0)):
                logger.info(f"[跳过] {fund_name}({fund_code}) | 原因: 趋势条件不满足 week={week_growth_rate:.2f}%, month={month_growth_rate:.2f}%, season={season_growth_rate:.2f}%")
                continue

            # 百分位排名数据
            try:
                _, season_item_rank, season_item_sc = get_fund_growth_rate(fi, '3Y')
                _, month_item_rank, month_item_sc = get_fund_growth_rate(fi, 'Y')
            except Exception as e:
                logger.info(f"[跳过] {fund_name}({fund_code}) | 原因: 获取百分位排名数据异常 {e}")
                continue
            if not season_item_rank or not season_item_sc or season_item_sc == 0 \
               or not month_item_rank or not month_item_sc or month_item_sc == 0:
                logger.info(f"[跳过] {fund_name}({fund_code}) | 原因: 百分位排名数据不可用（season: rank={season_item_rank}, sc={season_item_sc}; month: rank={month_item_rank}, sc={month_item_sc}）")
                continue

            month_rank_rate = float(month_item_rank) / float(month_item_sc)
            season_rank_rate = float(season_item_rank) / float(season_item_sc)
            if month_rank_rate > 0.75 or season_rank_rate > 0.75:
                logger.info(f"[跳过] {fund_name}({fund_code}) | 原因: 百分位排名过高 month_rank_rate={month_rank_rate:.2%}, season_rank_rate={season_rank_rate:.2%}（阈值<=75%）")
                continue

            # 5 日均值判定（分支内若仍保留，补充原因日志）
            if not nav5_gate(fi, fund_name, fund_code, logger):
                logger.info(f"[跳过] {fund_name}({fund_code}) | 原因: 5日均值判定未通过（详见公共服务日志）")
                continue

            # 基金级不连续交易守卫（上一个交易日(nav_date)+今天，排除撤单）
            try:
                nav_date_str = getattr(fi, "nav_date", None)
                prev_trade_day = datetime.datetime.strptime(nav_date_str, "%Y-%m-%d").date() if nav_date_str else None
            except Exception:
                prev_trade_day = None
            today = datetime.date.today()
            date_set = {d for d in [prev_trade_day, today] if d}
            from src.service.公共服务.trade_guard_service import has_buy_submission_on_dates
            stay_trade = has_buy_submission_on_dates(user, sub_account_no, fund_code, date_set)
            if stay_trade:
                state = getattr(stay_trade, "app_state_text", None) or getattr(stay_trade, "status", None)
                logger.info(f"[跳过] {fund_name}({fund_code}) | 原因: 不连续交易守卫触发（状态={state}）")
                continue

            # 基础加仓
            res1 = commit_order(user, sub_account_no, fund_code, buy_amount)
            if res1:
                logger.info(f"[加仓成功] {fund_name}({fund_code}) | 金额: {buy_amount} | 订单号: {res1.busin_serial_no}")
                orders_made += 1
                success_count += 1
            if orders_made >= fund_num:
                break
            # -5% 额外加仓
            if estimated_profit_rate < -5.0 and orders_made < fund_num:
                res2 = commit_order(user, sub_account_no, fund_code, buy_amount)
                if res2:
                    logger.info(f"[加仓成功] {fund_name}({fund_code}) | -5%额外加仓 | 金额: {buy_amount} | 订单号: {res2.busin_serial_no}")
                    orders_made += 1
                    success_count += 1
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
        increase_funds(user, "飞龙在天",1000000.0, None, 'non_index')  # 使用 DEFAULT_USER，并假设参数合适
        logging.info(f"用户 {user.customer_name} 加仓操作完成")
    except Exception as e:
        logging.error(f"测试用户处理失败：{str(e)}")
