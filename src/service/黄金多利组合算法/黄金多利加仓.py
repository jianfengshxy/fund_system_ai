import sys
import os

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.logger import get_logger
import datetime
from typing import Optional, List, Dict

from src.domain.user.User import User
from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.service.交易管理.购买基金 import commit_order
from src.service.公共服务.trade_guard_service import has_buy_submission_on_dates
from src.service.基金信息.基金信息 import get_all_fund_info

logger = get_logger(__name__)

def increase_gold_funds(
    user: User,
    sub_account_name: str,
    amount: float = 2000.0,
    fund_list: Optional[List[Dict]] = None,
    total_limit: Optional[float] = None,
) -> bool:
    """
    黄金多利组合加仓逻辑：
    只有收益率小于-1.0% 且 没有在途交易 就买入指定基金
    """
    logger.info(f"开始执行组合加仓检查，组合: {sub_account_name}", extra={"account": user.account, "sub_account_name": sub_account_name, "action": "gold_increase"})

    def _safe_float(value, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    def _normalize_limit(raw_limit) -> Optional[float]:
        if raw_limit in (None, ""):
            return None
        try:
            return float(raw_limit)
        except Exception:
            return None

    def _get_asset_limit_metric(asset) -> float:
        asset_value = _safe_float(getattr(asset, "asset_value", 0.0), 0.0)
        profit_value = getattr(asset, "constant_profit", None)
        return asset_value + _safe_float(profit_value, 0.0)

    # 获取子账户编号
    sub_account_no = getSubAccountNoByName(user, sub_account_name)
    if not sub_account_no:
        logger.error(f"未找到组合 {sub_account_name} 的账号")
        return False

    normalized_funds: List[Dict] = []
    if isinstance(fund_list, list) and fund_list:
        for item in fund_list:
            if not isinstance(item, dict):
                continue
            fund_code = item.get("fund_code") or item.get("fundcode") or item.get("FundCode") or item.get("code")
            if not fund_code:
                continue
            try:
                fund_amount = float(item.get("amount", amount))
            except Exception:
                fund_amount = amount
            normalized_funds.append({
                "fund_code": str(fund_code),
                "amount": fund_amount,
                "limit": _normalize_limit(item.get("limit")),
            })

    # if not normalized_funds:
    #     normalized_funds = [{"fund_code": "021740", "amount": amount, "limit": None}]

    def _get_check_dates_for_fund(fund_code: str) -> set:
        fi = get_all_fund_info(user, fund_code)
        nav_date_str = getattr(fi, "nav_date", None) if fi else None
        try:
            prev_trade_day = datetime.datetime.strptime(nav_date_str, "%Y-%m-%d").date() if nav_date_str else None
        except Exception:
            prev_trade_day = None
        today = datetime.date.today()
        check_dates = {today}
        if prev_trade_day:
            check_dates.add(prev_trade_day)
        return check_dates

    def _has_pending_trade(fund_code: str) -> bool:
        check_dates = _get_check_dates_for_fund(fund_code)
        pending_trade = has_buy_submission_on_dates(user, sub_account_no, fund_code, check_dates)
        return pending_trade is not None
        
    def _get_fund_name(fund_code: str) -> str:
        fi = get_all_fund_info(user, fund_code)
        return getattr(fi, "fund_name", "") if fi else ""

    # 获取持仓并建立有效持仓索引
    user_assets = get_sub_account_asset_by_name(user, sub_account_name)
    asset_dict = {}
    if user_assets:
        for asset in user_assets:
            try:
                vol = float(getattr(asset, 'available_vol', 0) or 0)
                val = float(getattr(asset, 'asset_value', 0) or 0)
                if vol > 0.01 or val > 1.0: 
                    asset_dict[asset.fund_code] = asset
            except:
                pass

    buy_triggered = False
    
    # 建立 payload 中基金的 amount 映射，用于加仓时取金额
    payload_amt_dict = {f["fund_code"]: f["amount"] for f in normalized_funds}
    payload_limit_dict = {f["fund_code"]: f.get("limit") for f in normalized_funds}
    total_limit = _normalize_limit(total_limit)
    fund_metric_dict = {f_code: _get_asset_limit_metric(asset) for f_code, asset in asset_dict.items()}
    total_metric = sum(fund_metric_dict.values())

    logger.info(
        f"组合 {sub_account_name} 当前资产限制口径值: {total_metric:.2f}, total_limit={total_limit if total_limit is not None else '无限制'}"
    )

    # 优先验证组合总资产是否已超过限制，超过则直接输出原因并返回
    if total_limit is not None and total_metric >= total_limit:
        logger.info(f"组合 {sub_account_name} 当前资产 {total_metric:.2f} 已达到或超过组合上限 {total_limit:.2f}，停止加仓操作。")
        return True

    def _can_submit_buy(fund_code: str, fund_name: str, buy_amount: float) -> bool:
        nonlocal total_metric

        current_fund_metric = fund_metric_dict.get(fund_code, 0.0)
        fund_limit = payload_limit_dict.get(fund_code)
        projected_fund_metric = current_fund_metric + buy_amount
        projected_total_metric = total_metric + buy_amount

        if fund_limit is not None:
            if current_fund_metric >= fund_limit:
                logger.info(
                    f"基金 {fund_name}({fund_code}) 当前限制口径值 {current_fund_metric:.2f} 已达到单基金上限 {fund_limit:.2f}，跳过买入"
                )
                return False
            if projected_fund_metric > fund_limit:
                logger.info(
                    f"基金 {fund_name}({fund_code}) 本次买入后限制口径值预计为 {projected_fund_metric:.2f}，超过单基金上限 {fund_limit:.2f}，跳过买入"
                )
                return False

        if total_limit is not None:
            if total_metric >= total_limit:
                logger.info(
                    f"组合 {sub_account_name} 当前限制口径值 {total_metric:.2f} 已达到组合上限 {total_limit:.2f}，跳过买入 {fund_name}({fund_code})"
                )
                return False
            if projected_total_metric > total_limit:
                logger.info(
                    f"组合 {sub_account_name} 本次买入后限制口径值预计为 {projected_total_metric:.2f}，超过组合上限 {total_limit:.2f}，跳过买入 {fund_name}({fund_code})"
                )
                return False

        return True

    def _mark_buy_metric(fund_code: str, actual_amount: float) -> None:
        nonlocal total_metric
        total_metric += actual_amount
        fund_metric_dict[fund_code] = fund_metric_dict.get(fund_code, 0.0) + actual_amount

    # 1. 遍历传过来的基金列表，如果未持有该基金，则执行该基金的初始化建仓
    for f in normalized_funds:
        f_code = f["fund_code"]
        f_amt = f["amount"]
        f_name = _get_fund_name(f_code)
        
        # 最先校验单个基金的资产是否已超过限制，超过则跳过该基金
        current_fund_metric = fund_metric_dict.get(f_code, 0.0)
        fund_limit = payload_limit_dict.get(f_code)
        if fund_limit is not None and current_fund_metric >= fund_limit:
            logger.info(f"基金 {f_name}({f_code}) 当前资产 {current_fund_metric:.2f} 已达到单基金上限 {fund_limit:.2f}，跳过初始化建仓")
            continue

        if f_code not in asset_dict:
            if _has_pending_trade(f_code):
                logger.info(f"目标基金 {f_code} 存在在途交易，跳过初始化建仓")
                continue

            if not _can_submit_buy(f_code, f_name, f_amt):
                continue
                
            logger.info(f"基金 {f_name}({f_code}) 未持有，执行初始化建仓，准备下单金额: {f_amt}")
            res = commit_order(user, sub_account_no, f_code, f_amt)
            if res:
                actual_amount = getattr(res, "amount", f_amt)
                logger.info(f"初始化建仓成功: {f_code} - 金额: {actual_amount} - 订单号: {res.busin_serial_no}")
                _mark_buy_metric(f_code, _safe_float(actual_amount, f_amt))
                buy_triggered = True
            else:
                logger.info(f"初始化建仓未提交或失败: {f_name}({f_code}) 金额: {f_amt}")

    # 2. 遍历组合内所有持有的基金，满足条件则加仓降低成本
    for f_code, asset in asset_dict.items():
        f_name = getattr(asset, "fund_name", "") or _get_fund_name(f_code)
        
        # 最先校验单个基金的资产是否已超过限制，超过则跳过该基金
        current_fund_metric = fund_metric_dict.get(f_code, 0.0)
        fund_limit = payload_limit_dict.get(f_code)
        if fund_limit is not None and current_fund_metric >= fund_limit:
            logger.info(f"持仓基金 {f_name}({f_code}) 当前资产 {current_fund_metric:.2f} 已达到单基金上限 {fund_limit:.2f}，跳过加仓")
            continue

        if _has_pending_trade(f_code):
            logger.info(f"持仓基金 {f_name}({f_code}) 存在在途交易，跳过加仓")
            continue
            
        # 计算预估收益率
        current_profit_rate = float(getattr(asset, "constant_profit_rate", 0.0) or 0.0)
        fund_info = get_all_fund_info(user, f_code)
        estimated_change = fund_info.estimated_change if fund_info and fund_info.estimated_change is not None else 0.0
        estimated_profit_rate = current_profit_rate + estimated_change
        
        logger.info(f"持仓基金 {f_name}({f_code}) 当前收益率: {current_profit_rate}%, 估值变动: {estimated_change}%, 预估收益率: {estimated_profit_rate:.2f}%")

        if estimated_profit_rate < -1.0:
            # 取对应的下单金额，优先取 payload 中配置的金额，否则用默认传参的 amount
            base_amt = payload_amt_dict.get(f_code, amount)
            buy_multiplier = 2.0 if estimated_profit_rate < -5.0 else 1.0
            buy_amount = base_amt * buy_multiplier

            logger.info(f"持仓基金 {f_name}({f_code}) 预估收益率 {estimated_profit_rate:.2f}% < -1.0%，触发加仓判定")
            logger.info(f"满足加仓条件，准备买入 {f_name}({f_code}) 金额: {buy_amount}")

            if not _can_submit_buy(f_code, f_name, buy_amount):
                continue
            
            res = commit_order(user, sub_account_no, f_code, buy_amount)
            if res:
                actual_amount = getattr(res, "amount", buy_amount)
                logger.info(f"加仓成功: {f_code} - 金额: {actual_amount} - 订单号: {res.busin_serial_no}")
                _mark_buy_metric(f_code, _safe_float(actual_amount, buy_amount))
                buy_triggered = True
            else:
                logger.info(f"加仓未提交或失败: {f_name}({f_code}) 金额: {buy_amount}")
        else:
            logger.info(f"持仓基金 {f_name}({f_code}) 预估收益率 {estimated_profit_rate:.2f}% >= -1.0%，不满足加仓条件")


    if not buy_triggered:
        logger.info("本次检查未触发加仓操作")

    return True

if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    try:
        # 1. 构造测试用户（或者使用默认用户）
        # 这里使用 DEFAULT_USER 进行测试，确保 s.yaml 中的账号密码配置正确
        test_user = DEFAULT_USER
        
        # 2. 设置测试参数
        test_sub_account = "智投平台"
        test_amount = 10000.0

        print(f"--- 开始测试黄金多利加仓 ---")
        print(f"用户: {test_user.customer_name}")
        print(f"组合: {test_sub_account}")
        
        # 3. 调用加仓函数
        increase_gold_funds(test_user, test_sub_account, test_amount)
        
        print(f"--- 测试结束 ---")

    except Exception as e:
        logger.error(f"测试执行失败: {e}")
