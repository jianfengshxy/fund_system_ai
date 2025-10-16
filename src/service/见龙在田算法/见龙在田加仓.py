import logging
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
from src.API.资产管理.AssetManager import GetMyAssetMainPartAsync
from src.service.交易管理.交易查询 import count_success_trades_on_prev_nav_day

import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def increase_funds(user: User, sub_account_name: str, total_budget: float, amount: Optional[float] = None, fund_type: str = 'all', fund_num: int = 5, spread_days: int = 5) -> bool:
    """
    加仓（最小集成落地版）：
    - fund_num: 本次最多下单次数（默认5）
    - spread_days: 预算摊薄天数（默认20），仅在未传入amount时生效
    - 若余额不足，动态下调 buy_amount（至少10元）
    """
    logger.info(f"参数: fund_num={fund_num}, spread_days={spread_days}")
    # 计算基础单笔金额
    base_amount = float(amount) if amount is not None else round(total_budget / max(fund_num, 1) / max(spread_days, 1), 2) * 2
    logger.info(f"单只基金基础买入金额: {base_amount}元(是新增金额的2倍)")
    # 查询余额并动态下调
    try:
        asset_response = GetMyAssetMainPartAsync(user)
        if not (asset_response.Success and asset_response.Data):
            raise Exception("资产API调用失败")
        available_balance = float(asset_response.Data.get('HqbValue', 0.0))
    except Exception as e:
        logger.error(f"获取用户资产失败: {e}")
        return False

    buy_amount = base_amount
    total_need = round(buy_amount * fund_num, 2)
    if available_balance < total_need:
        cap = max(10.0, round((available_balance * 0.9) / max(fund_num, 1), 2))
        if cap < buy_amount:
            logger.warning(f"余额不足以覆盖计划下单{fund_num}笔（需{total_need}元），单笔金额下调为 {cap} 元")
            buy_amount = cap

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

        # 公共前置过滤：跌幅不深直接跳过
        if estimated_profit_rate >= -1.0:
            logger.info(f"跳过 {fi.fund_name}({fund_code}): 回撤不达标 estimated_profit_rate={estimated_profit_rate:.2f}% ，阈值<-1.00%（current={current_profit_rate:.2f}%, change={estimated_change:.2f}%）")
            continue

        # 使用“昨日净值日(nav_date)+今天”的守卫：任一天存在非撤的买入/定投则跳过
        from src.service.公共服务.trade_guard_service import has_buy_submission_on_dates
        nav_date_str = getattr(fi, "nav_date", None)
        try:
            prev_trade_day = datetime.datetime.strptime(nav_date_str, "%Y-%m-%d").date() if nav_date_str else None
        except Exception:
            prev_trade_day = None
        today = datetime.date.today()
        prev_trade_pre = has_buy_submission_on_dates(user, sub_account_no, fund_code, {d for d in [prev_trade_day] if d})
        today_trade_pre = has_buy_submission_on_dates(user, sub_account_no, fund_code, {today})
        if prev_trade_pre is not None or today_trade_pre is not None:
            logger.info(f"跳过 {fi.fund_name}({fund_code}): 昨日(nav_date)或今日存在买入/定投提交（非撤）")
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

    # 抽取：估算净值 > 5日均值 判定（复用于两条路径）
    def _nav5_gate(fi, fund_name: str, fund_code: str, label: str = "") -> bool:
        prefix = "风向标 " if label == "wind_vane" else ""
        est_nav = getattr(fi, "estimated_value", None)
        nav5 = getattr(fi, "nav_5day_avg", None)
        try:
            est_val = float(est_nav) if est_nav is not None else None
            nav5_val = float(nav5) if nav5 is not None else None
        except Exception:
            est_val = None
            nav5_val = None

        if est_val is None or nav5_val is None:
            logger.info(f"跳过{prefix}{fund_name}({fund_code}): 缺少估算净值或5日均值（estimated_value={est_nav}, nav_5day_avg={nav5}）")
            return False
        if not (est_val > nav5_val):
            logger.info(f"跳过{prefix}{fund_name}({fund_code}): 估算净值 {est_val:.4f} <= 5日均值 {nav5_val:.4f}，暂不加仓")
            return False
        return True

    for asset, fi, in_wind_vane, estimated_profit_rate in enriched:
        if orders_made >= fund_num:
            logger.info(f"已达本次下单上限 {fund_num} 笔，提前结束")
            break

        fund_code = asset.fund_code
        fund_name = fi.fund_name

        # 先尝试风向标路径（仅对风向标标的）
        if in_wind_vane:
            try:
                safe_asset_value = _safe_float(getattr(asset, "asset_value", 0.0), 0.0)
                if safe_asset_value < float(total_budget):
                    # 使用抽取的 5日均值判定
                    if not _nav5_gate(fi, fund_name, fund_code, label="wind_vane"):
                        continue

                    res = commit_order(user, sub_account_no, fund_code, buy_amount)
                    if res:
                        logger.info(f"风向标加仓成功: {fund_name}({fund_code}) - 金额: {buy_amount} - 订单号: {res.busin_serial_no}")
                        orders_made += 1
                        success_count += 1
                    if orders_made >= fund_num:
                        break
                else:
                    logger.info(f"跳过风向标 {fund_name}({fund_code}): 持仓资产 {safe_asset_value} >= 本次预算阈值 {total_budget}，不重复加仓")
                # 对风向标标的，不走后续“排名/收益率规则路径”
                continue
            except Exception as e:
                logger.error(f"风向标加仓失败 {fund_name}({fund_code}): {e}")
                # 不中断，继续其他标的
                continue

        # 非风向标：沿用原“排名/收益率规则路径”（增加空值与分母校验）
        try:
            # 提取收益率（需要月收益率进行判定）
            season_growth_rate = _safe_float(getattr(fi, "three_month_return", None), 0.0)
            month_growth_rate = _safe_float(getattr(fi, "month_return", None), 0.0)
            week_growth_rate = _safe_float(getattr(fi, "week_return", None), 0.0)

            # 提取百分位排名（近3年 vs 近1年）
            try:
                _, season_item_rank, season_item_sc = get_fund_growth_rate(fi, '3Y')
                _, month_item_rank, month_item_sc = get_fund_growth_rate(fi, 'Y')
            except Exception as e:
                logger.info(f"跳过 {fund_name}({fund_code}): 获取排名数据异常 {e}")
                continue

            # 基本有效性校验（空值与分母为0）
            if not season_item_rank or not season_item_sc or season_item_sc == 0 \
               or not month_item_rank or not month_item_sc or month_item_sc == 0:
                logger.info(f"跳过 {fund_name}({fund_code}): 百分位排名数据不可用（season: rank={season_item_rank}, sc={season_item_sc}; month: rank={month_item_rank}, sc={month_item_sc}）")
                continue

            # 新逻辑：仅当月收益率为正，且近1个月排名优于近3个月（排名数值小表示更靠前）时才通过
            if not (month_growth_rate > 0.0 and float(month_item_rank) < float(season_item_rank)):
                logger.info(
                    f"跳过 {fund_name}({fund_code}): 月收益率不为正或近1年排名未优于近3年"
                    f"（month_growth_rate={month_growth_rate:.2f}%, month_item_rank={month_item_rank}, season_item_rank={season_item_rank}）"
                )
                continue

            # 使用抽取的 5日均值判定（非风向标同样要求）
            if not _nav5_gate(fi, fund_name, fund_code):
                continue

            # 基础加仓
            res1 = commit_order(user, sub_account_no, fund_code, buy_amount)
            if res1:
                logger.info(f"基础加仓成功: {fund_name}({fund_code}) - 金额: {buy_amount} - 订单号: {res1.busin_serial_no}")
                orders_made += 1
                success_count += 1
            if orders_made >= fund_num:
                break
            # -5% 额外加仓
            if estimated_profit_rate < -5.0 and orders_made < fund_num:
                res2 = commit_order(user, sub_account_no, fund_code, buy_amount)
                if res2:
                    logger.info(f"额外加仓成功(-5%): {fund_name}({fund_code}) - 金额: {buy_amount} - 订单号: {res2.busin_serial_no}")
                    orders_made += 1
                    success_count += 1
        except Exception as e:
            logger.error(f"处理非风向标 {fund_name}({fund_code}) 失败: {e}")
            continue

    logger.info(f"加仓完成，本次共下单 {orders_made} 笔，成功 {success_count} 笔")
    return success_count > 0


if __name__ == "__main__":
    # 测试单个用户的加仓流程
    try:
        # 执行加仓操作
        increase_funds(DEFAULT_USER, "见龙在田", 1000000.0, None, 'non_index')  # 使用 DEFAULT_USER，并假设参数合适
        logging.info(f"用户 {DEFAULT_USER.customer_name} 加仓操作完成")
    except Exception as e:
        logging.error(f"测试用户处理失败：{str(e)}")