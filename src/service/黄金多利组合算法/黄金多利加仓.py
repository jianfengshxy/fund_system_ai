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
from src.service.公共服务.nav_gate_service import nav5_gate
from src.service.公共服务.estimated_profit_service import calc_estimated_change, calc_estimated_profit_rate

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

    def _normalize_limit(raw_limit, default_val: Optional[float] = None) -> Optional[float]:
        if raw_limit in (None, ""):
            return default_val
        try:
            return float(raw_limit)
        except Exception:
            return default_val

    def _get_asset_limit_metric(asset) -> float:
        # 只使用资产值进行上限检查，忽略浮动盈亏
        asset_value = _safe_float(getattr(asset, "asset_value", 0.0), 0.0)
        return asset_value

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
                # 获取基金买入金额，遵循优先级规则：
                # 1. 基金级别的amount优先级最高（在item中配置）
                # 2. 如果没有基金级别的amount，则使用组合级别的amount（函数参数amount）
                fund_amount = float(item.get("amount", amount))
            except Exception:
                fund_amount = amount
            normalized_funds.append({
                "fund_code": str(fund_code),
                "amount": fund_amount,
                # 没有配置limit时返回None，表示不做限制
                "limit": _normalize_limit(item.get("limit"), None),
            })

    # if not normalized_funds:
    #     normalized_funds = [{"fund_code": "021740", "amount": amount, "limit": None}]

    def _has_pending_trade(fund_code: str) -> bool:
        fi = get_all_fund_info(user, fund_code)
        nav_date_str = getattr(fi, "nav_date", None) if fi else None
        if nav_date_str:
            try:
                prev_trade_day = datetime.datetime.strptime(str(nav_date_str), "%Y-%m-%d").date()
            except Exception:
                prev_trade_day = None
        else:
            prev_trade_day = None
        
        # 步骤1: 检查上一个交易日是否有有效买入/定投
        prev_trade_record = has_buy_submission_on_dates(user, sub_account_no, fund_code, prev_trade_day)
        if prev_trade_record:
            state = getattr(prev_trade_record, "app_state_text", None) or getattr(prev_trade_record, "status", None)
            logger.info(f"[在途检查] 基金 {fund_code} 上一个交易日({nav_date_str})已有有效交易（状态={state}），跳过加仓")
            return True
        
        # 步骤2: 检查今天是否有有效买入/定投（当日不重复交易）
        today = datetime.date.today()
        today_trade_record = has_buy_submission_on_dates(user, sub_account_no, fund_code, today)
        if today_trade_record:
            state = getattr(today_trade_record, "app_state_text", None) or getattr(today_trade_record, "status", None)
            logger.info(f"[在途检查] 基金 {fund_code} 今日({today})已有有效交易（状态={state}），跳过加仓")
            return True
        
        logger.info(f"[在途检查] 基金 {fund_code} nav_date={nav_date_str}, prev_trade_day={prev_trade_day}, 查询结果: 无交易")
        return False
        
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
        # 只在有配置limit时进行检查，没有配置就不限制
        fund_limit = payload_limit_dict.get(fund_code)
        projected_fund_metric = current_fund_metric + buy_amount
        projected_total_metric = total_metric + buy_amount

        if fund_limit is not None:
            if current_fund_metric >= fund_limit:
                logger.info(
                    f"基金 {fund_name}({fund_code}) 当前资产值 {current_fund_metric:.2f} 已达到单基金上限 {fund_limit:.2f}，跳过买入"
                )
                return False
            if projected_fund_metric > fund_limit:
                logger.info(
                    f"基金 {fund_name}({fund_code}) 本次买入后资产值预计为 {projected_fund_metric:.2f}，超过单基金上限 {fund_limit:.2f}，跳过买入"
                )
                return False

        if total_limit is not None:
            if total_metric >= total_limit:
                logger.info(
                    f"组合 {sub_account_name} 当前资产值 {total_metric:.2f} 已达到组合上限 {total_limit:.2f}，跳过买入 {fund_name}({fund_code})"
                )
                return False
            if projected_total_metric > total_limit:
                logger.info(
                    f"组合 {sub_account_name} 本次买入后资产值预计为 {projected_total_metric:.2f}，超过组合上限 {total_limit:.2f}，跳过买入 {fund_name}({fund_code})"
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
        # 只在有配置limit时进行检查，没有配置就不限制
        fund_limit = payload_limit_dict.get(f_code)
        if fund_limit is not None and current_fund_metric >= fund_limit:
            logger.info(f"基金 {f_name}({f_code}) 当前资产值 {current_fund_metric:.2f} 已达到单基金上限 {fund_limit:.2f}，跳过初始化建仓")
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
        # 只在有配置limit时进行检查，没有配置就不限制
        fund_limit = payload_limit_dict.get(f_code)
        if fund_limit is not None and current_fund_metric >= fund_limit:
            logger.info(f"持仓基金 {f_name}({f_code}) 当前资产值 {current_fund_metric:.2f} 已达到单基金上限 {fund_limit:.2f}，跳过加仓")
            continue

        if _has_pending_trade(f_code):
            logger.info(f"持仓基金 {f_name}({f_code}) 存在在途交易，跳过加仓")
            continue
            
        # 计算预估收益率
        current_profit_rate = float(getattr(asset, "constant_profit_rate", 0.0) or 0.0)
        fund_info = get_all_fund_info(user, f_code)
        estimated_change, label_est = calc_estimated_change(fund_info)
        estimated_profit_rate = current_profit_rate + estimated_change

        week_growth_rate = _safe_float(getattr(fund_info, "week_return", None) if fund_info else None, 0.0)
        month_growth_rate = _safe_float(getattr(fund_info, "month_return", None) if fund_info else None, 0.0)
        
        logger.info(f"持仓基金 {f_name}({f_code}) 当前收益率: {current_profit_rate}%, 估值变动: {estimated_change}%, 预估收益率: {estimated_profit_rate:.2f}%（{label_est}）")

        # 获取当前资产值和该基金的买入金额
        current_asset_value = _safe_float(getattr(asset, "asset_value", 0.0), 0.0)
        # 获取该基金的买入金额，遵循优先级规则：
        # 1. 基金级别的amount优先级最高（在fund_list中配置）
        # 2. 如果没有基金级别的amount，则使用组合级别的amount（函数参数amount）
        # payload_amt_dict是从normalized_funds构建的，已经遵循了这个优先级
        base_amt = payload_amt_dict.get(f_code, amount)
        
        # 检查是否满足加仓条件：
        # 1. 如果当前资产值 <= 买入金额（可能是因为限购导致持仓不足），则允许加仓（忽略-1%过滤器）
        # 2. 否则，需要满足预估收益率 < -1.0% 的条件
        should_increase = False
        increase_reason = ""
        
        if current_asset_value <= base_amt:
            # 持有资产小于或等于一次性买入量，可能是因为限购，允许加仓
            should_increase = True
            increase_reason = f"持仓资产({current_asset_value:.2f}) <= 买入金额({base_amt:.2f})，可能因限购导致持仓不足"
        elif estimated_profit_rate < -1.0:
            # 满足原来的-1%过滤器条件
            should_increase = True
            increase_reason = f"预估收益率({estimated_profit_rate:.2f}%) < -1.0%"
        
        if should_increase:
            logger.info(f"持仓基金 {f_name}({f_code}) {increase_reason}，触发加仓判定")
            
            # 检查是否跌幅过大（小于-5.0%），如果是则跳过加仓，防止单边下跌
            if estimated_profit_rate < -5.0:
                # 特殊豁免：如果基金被限购且限购金额 < 2000，说明持仓上不去，即使跌幅过大也继续加仓
                _max_purchase = _safe_float(getattr(fund_info, 'max_purchase', 0.0) if fund_info else 0.0, 0.0)
                if _max_purchase > 0 and _max_purchase < 2000:
                    logger.info(f"持仓基金 {f_name}({f_code}) 预估收益率 {estimated_profit_rate:.2f}% < -5.0%，但限购金额 {_max_purchase} < 2000，突破限购加仓")
                else:
                    if (
                        estimated_profit_rate < -10.0
                        and week_growth_rate > 0.0
                        and month_growth_rate > 0.0
                        and current_asset_value > 0.0
                        and nav5_gate(fund_info, f_name, f_code, logger)
                    ):
                        buy_amount = float(current_asset_value)
                        logger.info(
                            f"持仓基金 {f_name}({f_code}) 触发深度回撤反弹加倍加仓："
                            f"estimated_profit_rate={estimated_profit_rate:.2f}%, week={week_growth_rate:.2f}%, month={month_growth_rate:.2f}%, buy_amount={buy_amount:.2f}"
                        )
                        if not _can_submit_buy(f_code, f_name, buy_amount):
                            continue
                        res = commit_order(user, sub_account_no, f_code, buy_amount)
                        if res:
                            actual_amount = getattr(res, "amount", buy_amount)
                            logger.info(f"深度回撤反弹加倍加仓成功: {f_code} - 金额: {actual_amount} - 订单号: {res.busin_serial_no}")
                            _mark_buy_metric(f_code, _safe_float(actual_amount, buy_amount))
                            buy_triggered = True
                        else:
                            logger.info(f"深度回撤反弹加倍加仓未提交或失败: {f_name}({f_code}) 金额: {buy_amount}")
                        continue
                    logger.info(f"持仓基金 {f_name}({f_code}) 预估收益率 {estimated_profit_rate:.2f}% < -5.0%，跌幅过大，暂停加仓等待反弹")
                    continue
            
            # 加仓金额计算（统一处理）：
            #   预估收益率: [-1%, -4%) → 1倍 base_amt
            #               [-4%, -5%) → 2倍 base_amt
            #               < -5%  → 已在上方跳过，不买入
            # 注：base_amt 已遵循优先级: fund_list 中该基金的 amount > 组合默认 amount
            buy_multiplier = 2.0 if estimated_profit_rate < -4.0 else 1.0
            buy_amount = base_amt * buy_multiplier
            logger.info(
                f"满足加仓条件，准备买入 {f_name}({f_code}) "
                f"金额: {buy_amount}（base_amt={base_amt}，倍率={buy_multiplier}，预估收益率 {estimated_profit_rate:.2f}%）"
            )

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
            logger.info(f"持仓基金 {f_name}({f_code}) 预估收益率 {estimated_profit_rate:.2f}% >= -1.0%，且持仓资产({current_asset_value:.2f}) > 买入金额({base_amt:.2f})，不满足加仓条件")


    if not buy_triggered:
        logger.info("本次检查未触发加仓操作")

    return True

if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    try:
        # 1. 构造测试用户（或者使用默认用户）
        test_user = DEFAULT_USER
        test_user.account = "13918199137"
        test_user.password = "sWX15706"
        
        # 2. 设置测试参数
        test_sub_account = "智投平台"
        test_amount = 10000.0
        test_total_limit = 500000.0
        test_fund_list = [ 
            { 
                "fund_code": "011707", 
                "amount": 2000.0 
            }, 
            { 
                "fund_code": "012769", 
                "amount": 2000.0,
                "limit": 50000.0 
            }, 
            { 
                "fund_code": "004753", 
                "amount": 2000.0, 
                "limit": 20000.0 
            } 
        ]

        print(f"--- 开始测试黄金多利加仓 ---")
        print(f"用户: {test_user.customer_name}")
        print(f"组合: {test_sub_account}")
        
        # 3. 调用加仓函数
        increase_gold_funds(
            user=test_user, 
            sub_account_name=test_sub_account, 
            amount=test_amount, 
            fund_list=test_fund_list,
            total_limit=test_total_limit
        )
        
        print(f"--- 测试结束 ---")

    except Exception as e:
        logger.error(f"测试执行失败: {e}")
