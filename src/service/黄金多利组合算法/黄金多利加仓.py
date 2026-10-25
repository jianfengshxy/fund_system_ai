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
from src.service.公共服务.estimated_profit_service import calc_estimated_change
from src.service.公共服务.risk_control_service import check_hqb_risk_allowed
from src.API.市场指数.指数资金热度与价格走势 import get_index_price_flow

logger = get_logger(__name__)

HQB_NEW_POSITION_THRESHOLD = 20.0
INDEX_HEAT_FILTER_MIN = 20.0
INDEX_HEAT_FILTER_MAX = 100.0


def _get_primary_theme(fund_info) -> Optional[tuple]:
    """
    提取主动型基金主主题，口径与已有主题去重逻辑保持一致：
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
        theme = max(relate_themes, key=lambda item: float(getattr(item, "corr_1y", 0.0) or 0.0))
        sec_code = str(getattr(theme, "sec_code", "") or "").strip()
        sec_name = str(getattr(theme, "sec_name", "") or "").strip()
        if sec_code or sec_name:
            return sec_code, sec_name

    return None

def increase_gold_funds(
    user: User,
    sub_account_name: str,
    amount: float = 2000.0,
    init_amount: Optional[float] = None,
    fund_list: Optional[List[Dict]] = None,
    limit: Optional[float] = None,
    total_limit: Optional[float] = None,
    hqb_ratio_limit_enabled: bool = True,
    index_heat_filter_enabled: bool = False,
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

    def _normalize_optional_bool(raw_value) -> Optional[bool]:
        if raw_value in (None, ""):
            return None
        if isinstance(raw_value, bool):
            return raw_value
        if isinstance(raw_value, (int, float)):
            return bool(raw_value)
        text = str(raw_value).strip().lower()
        if text in {"true", "1", "yes", "y", "on"}:
            return True
        if text in {"false", "0", "no", "n", "off"}:
            return False
        return None

    def _get_asset_limit_metric(asset) -> float:
        # 只使用资产值进行上限检查，忽略浮动盈亏
        asset_value = _safe_float(getattr(asset, "asset_value", 0.0), 0.0)
        return asset_value

    fund_info_cache: Dict[str, Optional[object]] = {}

    def _get_cached_fund_info(fund_code: str):
        if not fund_code:
            return None
        if fund_code not in fund_info_cache:
            fund_info_cache[fund_code] = get_all_fund_info(user, fund_code)
        return fund_info_cache[fund_code]

    def _get_group_key_and_label(fund_info) -> tuple[Optional[str], Optional[str]]:
        if not fund_info:
            return None, None

        fund_type = str(getattr(fund_info, "fund_type", "") or "").strip()
        if fund_type == "000":
            index_code = str(getattr(fund_info, "index_code", "") or "").strip()
            if index_code:
                return f"index:{index_code}", f"同指数({index_code})"
            return None, None

        theme = _get_primary_theme(fund_info)
        if not theme:
            return None, None

        sec_code, sec_name = theme
        if sec_code:
            return f"theme_code:{sec_code}", f"同主题({sec_name or sec_code})"
        if sec_name:
            return f"theme_name:{sec_name}", f"同主题({sec_name})"
        return None, None

    def _calc_add_effect_score(current_asset_value: float, estimated_profit_rate: float, buy_amount: float) -> float:
        """
        计算“按当前黄金多利标准金额再加一笔后，预估收益率改善多少百分点”。
        分值越高，说明当前这笔资金用在该基金上的降本效率越高。
        """
        asset_value = _safe_float(current_asset_value, 0.0)
        buy = _safe_float(buy_amount, 0.0)
        rate_pct = _safe_float(estimated_profit_rate, 0.0)
        rate = rate_pct / 100.0

        if asset_value <= 0.0 or buy <= 0.0 or rate >= 0.0 or rate <= -0.999:
            return 0.0

        current_cost = asset_value / (1.0 + rate)
        if current_cost <= 0.0:
            return 0.0

        new_rate = ((asset_value + buy) / (current_cost + buy)) - 1.0
        return (new_rate - rate) * 100.0

    def _preview_efficiency_buy_amount(
        *,
        current_asset_value: float,
        estimated_profit_rate: float,
        base_amt: float,
    ) -> float:
        min_asset_value_for_limited = base_amt * 0.95
        should_increase = (
            current_asset_value < min_asset_value_for_limited
            or estimated_profit_rate < -1.0
        )
        if not should_increase:
            return 0.0

        if estimated_profit_rate < -10.0:
            return 0.0

        if estimated_profit_rate < -4.0:
            return base_amt * 2.0

        return base_amt

    # 获取子账户编号
    sub_account_no = getSubAccountNoByName(user, sub_account_name)
    if not sub_account_no:
        logger.error(f"未找到组合 {sub_account_name} 的账号")
        return False

    portfolio_limit = _normalize_limit(limit)
    normalized_funds: List[Dict] = []
    if isinstance(fund_list, list) and fund_list:
        for item in fund_list:
            if not isinstance(item, dict):
                continue
            fund_code = item.get("fund_code") or item.get("fundcode") or item.get("FundCode") or item.get("code")
            if not fund_code:
                continue
            try:
                # 加仓金额（amount）计算规则：
                # - 优先使用基金级别 amount（fund_list 每个 item 内配置）
                # - 若基金级别未配置，则使用组合级别 amount（函数入参 amount）
                fund_amount = float(item.get("amount", amount))
            except Exception:
                fund_amount = amount

            # 初始化建仓金额（init_amount）计算规则（用于“未持有时的首次买入”）：
            # 1) 基金级别 init_amount 优先（兼容键 init_amount / initAmount）
            # 2) 若基金级别未配置，则使用组合级别 init_amount（函数入参 init_amount，来自 payload）
            # 3) 若两者都未配置，为保持兼容：init_amount 取“最终生效的 amount”
            #    - 即：基金级别 amount（如有）优先，否则组合级别 amount
            if "init_amount" in item:
                raw_init_amount = item.get("init_amount")
            elif "initAmount" in item:
                raw_init_amount = item.get("initAmount")
            else:
                raw_init_amount = None
            if raw_init_amount not in (None, ""):
                try:
                    fund_init_amount = float(raw_init_amount)
                except Exception:
                    fund_init_amount = fund_amount
            elif init_amount not in (None, ""):
                try:
                    fund_init_amount = float(init_amount)
                except Exception:
                    fund_init_amount = fund_amount
            else:
                fund_init_amount = fund_amount
            # 单基金持仓上限（limit）优先级规则：
            # 1) 基金级别 limit 优先（fund_list 每个 item 内配置）
            # 2) 若基金级别未配置或解析失败，则使用组合级别 limit（函数入参 limit）
            resolved_limit = portfolio_limit
            if "limit" in item:
                resolved_limit = _normalize_limit(item.get("limit"), portfolio_limit)
            fund_index_heat_filter_enabled = _normalize_optional_bool(
                item.get("index_heat_filter_enabled")
            )
            normalized_funds.append({
                "fund_code": str(fund_code),
                "amount": fund_amount,
                "init_amount": fund_init_amount,
                # 没有配置limit时返回None，表示不做限制
                "limit": resolved_limit,
                "index_heat_filter_enabled": fund_index_heat_filter_enabled,
            })

    # if not normalized_funds:
    #     normalized_funds = [{"fund_code": "021740", "amount": amount, "limit": None}]

    def _has_pending_trade(fund_code: str) -> bool:
        fi = _get_cached_fund_info(fund_code)
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
        fi = _get_cached_fund_info(fund_code)
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
    payload_index_heat_filter_dict = {
        f["fund_code"]: f.get("index_heat_filter_enabled") for f in normalized_funds
    }
    total_limit = _normalize_limit(total_limit)
    fund_metric_dict = {f_code: _get_asset_limit_metric(asset) for f_code, asset in asset_dict.items()}
    total_metric = sum(fund_metric_dict.values())
    representative_candidates: Dict[str, Dict] = {}
    index_heat_cache: Dict[str, Optional[float]] = {}

    def _get_effective_fund_limit(fund_code: str) -> Optional[float]:
        fund_limit = payload_limit_dict.get(fund_code)
        if fund_limit is not None:
            return fund_limit
        return portfolio_limit

    def _get_effective_index_heat_filter_enabled(fund_code: str) -> bool:
        fund_level_switch = payload_index_heat_filter_dict.get(fund_code)
        if fund_level_switch is not None:
            return bool(fund_level_switch)
        return index_heat_filter_enabled

    def _get_latest_realtime_index_heat(index_code: str) -> Optional[float]:
        if not index_code:
            return None
        if index_code in index_heat_cache:
            return index_heat_cache[index_code]

        try:
            resp = get_index_price_flow(user, index_code=index_code, range_type="w")
            latest_score = None
            if resp.success and resp.items:
                for item in reversed(resp.items):
                    if item.XLFLOW_SCORE is not None:
                        latest_score = float(item.XLFLOW_SCORE)
                        break
            index_heat_cache[index_code] = latest_score
            return latest_score
        except Exception as exc:
            logger.warning(f"获取指数 {index_code} 实时资金热度失败: {exc}")
            index_heat_cache[index_code] = None
            return None

    def _passes_index_heat_filter(
        *,
        fund_code: str,
        fund_name: str,
        fund_info,
        buy_context: str,
    ) -> bool:
        if not _get_effective_index_heat_filter_enabled(fund_code):
            return True

        if not fund_info:
            logger.info(f"持仓基金 {fund_name}({fund_code}) 未获取到基金信息，跳过资金热度过滤")
            return True

        fund_type = str(getattr(fund_info, "fund_type", "") or "").strip()
        index_code = str(getattr(fund_info, "index_code", "") or "").strip()
        if fund_type != "000" or not index_code:
            logger.info(
                f"持仓基金 {fund_name}({fund_code}) 非有效指数基金或无跟踪指数，"
                f"跳过资金热度过滤（fund_type={fund_type or '-'}, index_code={index_code or '-'}）"
            )
            return True

        latest_heat_score = _get_latest_realtime_index_heat(index_code)
        if latest_heat_score is None:
            logger.info(
                f"持仓基金 {fund_name}({fund_code}) 跟踪指数 {index_code} 当前无资金热度值，"
                f"跳过资金热度过滤"
            )
            return True

        if INDEX_HEAT_FILTER_MIN <= latest_heat_score <= INDEX_HEAT_FILTER_MAX:
            logger.info(
                f"持仓基金 {fund_name}({fund_code}) {buy_context} 通过资金热度过滤："
                f"index_code={index_code}, heat_score={latest_heat_score:.2f}"
            )
            return True

        logger.info(
            f"持仓基金 {fund_name}({fund_code}) {buy_context} 未通过资金热度过滤："
            f"index_code={index_code}, heat_score={latest_heat_score:.2f}, "
            f"要求范围=[{INDEX_HEAT_FILTER_MIN:.0f}, {INDEX_HEAT_FILTER_MAX:.0f}]"
        )
        return False

    logger.info(
        f"组合 {sub_account_name} 当前资产限制口径值: {total_metric:.2f}, "
        f"limit={portfolio_limit if portfolio_limit is not None else '无限制'}, "
        f"total_limit={total_limit if total_limit is not None else '无限制'}"
    )

    # 活期宝风控仅用于阻止首次开新仓，不影响已有持仓的后续加仓。
    if hqb_ratio_limit_enabled:
        hqb_new_position_allowed = check_hqb_risk_allowed(user, threshold=HQB_NEW_POSITION_THRESHOLD)
        logger.info(
            f"[黄金多利] 组合 {sub_account_name} 启用活期宝新仓限制，阈值={HQB_NEW_POSITION_THRESHOLD:.1f}% ，"
            f"校验结果={'通过' if hqb_new_position_allowed else '未通过'}"
        )
    else:
        hqb_new_position_allowed = True
        logger.info(f"[黄金多利] 组合 {sub_account_name} 已关闭活期宝新仓限制，允许跳过活期宝占比校验")

    # 优先验证组合总资产是否已超过限制，超过则直接输出原因并返回
    if total_limit is not None and total_metric >= total_limit:
        logger.info(f"组合 {sub_account_name} 当前资产 {total_metric:.2f} 已达到或超过组合上限 {total_limit:.2f}，停止加仓操作。")
        return True

    def _can_submit_buy(fund_code: str, fund_name: str, buy_amount: float) -> bool:
        nonlocal total_metric

        current_fund_metric = fund_metric_dict.get(fund_code, 0.0)
        # 只在有配置limit时进行检查，没有配置就不限制
        fund_limit = _get_effective_fund_limit(fund_code)
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

    for f_code, asset in asset_dict.items():
        fund_info = _get_cached_fund_info(f_code)
        group_key, group_label = _get_group_key_and_label(fund_info)
        if not group_key:
            continue

        current_asset_value = _safe_float(getattr(asset, "asset_value", 0.0), 0.0)
        current_profit_rate = _safe_float(getattr(asset, "constant_profit_rate", 0.0), 0.0)
        estimated_change, _ = calc_estimated_change(fund_info)
        estimated_profit_rate = current_profit_rate + estimated_change
        base_amt = _safe_float(payload_amt_dict.get(f_code, amount), _safe_float(amount, 0.0))
        preview_buy_amount = _preview_efficiency_buy_amount(
            current_asset_value=current_asset_value,
            estimated_profit_rate=estimated_profit_rate,
            base_amt=base_amt,
        )
        effect_score = _calc_add_effect_score(
            current_asset_value=current_asset_value,
            estimated_profit_rate=estimated_profit_rate,
            buy_amount=preview_buy_amount,
        )
        candidate = {
            "fund_code": f_code,
            "fund_name": getattr(asset, "fund_name", "") or _get_fund_name(f_code),
            "group_label": group_label,
            "effect_score": effect_score,
            "estimated_profit_rate": estimated_profit_rate,
            "asset_value": current_asset_value,
            "preview_buy_amount": preview_buy_amount,
        }
        best = representative_candidates.get(group_key)
        if (
            best is None
            or candidate["effect_score"] > best["effect_score"]
            or (
                abs(candidate["effect_score"] - best["effect_score"]) <= 1e-9
                and candidate["estimated_profit_rate"] < best["estimated_profit_rate"]
            )
            or (
                abs(candidate["effect_score"] - best["effect_score"]) <= 1e-9
                and abs(candidate["estimated_profit_rate"] - best["estimated_profit_rate"]) <= 1e-9
                and candidate["asset_value"] < best["asset_value"]
            )
        ):
            representative_candidates[group_key] = candidate

    for candidate in representative_candidates.values():
        logger.info(
            f"[同类优先] {candidate['group_label']} 当前仅保留 "
            f"{candidate['fund_name']}({candidate['fund_code']}) 作为加仓代表，"
            f"effect_score={candidate['effect_score']:.4f}pct, "
            f"estimated_profit_rate={candidate['estimated_profit_rate']:.2f}%, "
            f"asset_value={candidate['asset_value']:.2f}, "
            f"preview_buy_amount={candidate['preview_buy_amount']:.2f}"
        )

    # 1. 遍历传过来的基金列表，如果未持有该基金，则执行该基金的初始化建仓
    for f in normalized_funds:
        f_code = f["fund_code"]
        f_amt = f["init_amount"]
        f_name = _get_fund_name(f_code)
        
        # 最先校验单个基金的资产是否已超过限制，超过则跳过该基金
        current_fund_metric = fund_metric_dict.get(f_code, 0.0)
        # 只在有配置limit时进行检查，没有配置就不限制
        fund_limit = _get_effective_fund_limit(f_code)
        if fund_limit is not None and current_fund_metric >= fund_limit:
            logger.info(f"基金 {f_name}({f_code}) 当前资产值 {current_fund_metric:.2f} 已达到单基金上限 {fund_limit:.2f}，跳过初始化建仓")
            continue

        if f_code not in asset_dict:
            if not hqb_new_position_allowed:
                logger.info(
                    f"[黄金多利] 活期宝占比不足 {HQB_NEW_POSITION_THRESHOLD:.1f}%，"
                    f"跳过新仓初始化建仓: {f_name}({f_code})，init_amount={f_amt}"
                )
                continue

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
        fund_info = _get_cached_fund_info(f_code)
        f_name = getattr(asset, "fund_name", "") or _get_fund_name(f_code)
        group_key, group_label = _get_group_key_and_label(fund_info)
        representative = representative_candidates.get(group_key) if group_key else None
        if representative and representative["fund_code"] != f_code:
            logger.info(
                f"[同类跳过] {f_name}({f_code}) 属于 {group_label}，"
                f"当前优先处理 {representative['fund_name']}({representative['fund_code']}) "
                f"(effect_score={representative['effect_score']:.4f}pct)"
            )
            continue
        
        # 最先校验单个基金的资产是否已超过限制，超过则跳过该基金
        current_fund_metric = fund_metric_dict.get(f_code, 0.0)
        # 只在有配置limit时进行检查，没有配置就不限制
        fund_limit = _get_effective_fund_limit(f_code)
        if fund_limit is not None and current_fund_metric >= fund_limit:
            logger.info(f"持仓基金 {f_name}({f_code}) 当前资产值 {current_fund_metric:.2f} 已达到单基金上限 {fund_limit:.2f}，跳过加仓")
            continue

        if _has_pending_trade(f_code):
            logger.info(f"持仓基金 {f_name}({f_code}) 存在在途交易，跳过加仓")
            continue
            
        # 计算预估收益率
        current_profit_rate = float(getattr(asset, "constant_profit_rate", 0.0) or 0.0)
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
        min_asset_value_for_limited = base_amt * 0.95
        
        # 检查是否满足加仓条件：
        # 1. 如果当前资产值 <= 买入金额（可能是因为限购导致持仓不足），则允许加仓（忽略-1%过滤器）
        # 2. 否则，需要满足预估收益率 < -1.0% 的条件
        should_increase = False
        increase_reason = ""
        
        if current_asset_value < min_asset_value_for_limited:
            # 持有资产小于或等于一次性买入量，可能是因为限购，允许加仓
            should_increase = True
            increase_reason = (
                f"持仓资产({current_asset_value:.2f}) < 买入金额*0.95({min_asset_value_for_limited:.2f})，可能因限购导致持仓不足"
            )
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
                    # ---------- 深度回撤反弹加仓 ----------
                    # 触发条件（两个必须同时成立）：
                    #   1) is_deep_drawdown    : 回撤 > 5%（estimated_profit_rate < -5.0）
                    #   2) has_reversal_signal : 周线 > 0、月线 > 0、持仓市值 > 0，且净值站上 5 日均线
                    # 加仓额度：固定为 base_amt 的 2 倍。
                    # 这样若反弹持续，可通过连续 2 倍买入逐步降低成本；
                    # 若反弹终止，则下一轮会立刻回到熔断等待，避免一次性消耗过多现金。
                    is_deep_drawdown = estimated_profit_rate < -5.0
                    has_reversal_signal = (
                        week_growth_rate > 0.0
                        and month_growth_rate > 0.0
                        and current_asset_value > 0.0
                        and nav5_gate(fund_info, f_name, f_code, logger)
                    )

                    if is_deep_drawdown and has_reversal_signal:
                        if estimated_profit_rate >= -10.0:
                            buy_amount = float(base_amt) * 2.0
                        else:
                            logger.info(
                                f"持仓基金 {f_name}({f_code}) 回撤 {estimated_profit_rate:.2f}% 低于 -10%，疑似基本面风险，放弃抄底"
                            )
                            continue

                        logger.info(
                            f"持仓基金 {f_name}({f_code}) 触发深度回撤反弹加仓："
                            f"estimated_profit_rate={estimated_profit_rate:.2f}%, week={week_growth_rate:.2f}%, "
                            f"month={month_growth_rate:.2f}%, base_amt={base_amt:.2f}, "
                            f"buy_multiplier=2.0, buy_amount={buy_amount:.2f}"
                        )
                        if not _passes_index_heat_filter(
                            fund_code=f_code,
                            fund_name=f_name,
                            fund_info=fund_info,
                            buy_context="深度回撤反弹加仓",
                        ):
                            continue
                        if not _can_submit_buy(f_code, f_name, buy_amount):
                            continue
                        res = commit_order(user, sub_account_no, f_code, buy_amount)
                        if res:
                            actual_amount = getattr(res, "amount", buy_amount)
                            logger.info(f"深度回撤反弹加仓成功: {f_code} - 金额: {actual_amount} - 订单号: {res.busin_serial_no}")
                            _mark_buy_metric(f_code, _safe_float(actual_amount, buy_amount))
                            buy_triggered = True
                        else:
                            logger.info(f"深度回撤反弹加仓未提交或失败: {f_name}({f_code}) 金额: {buy_amount}")
                        continue

                    # 深跌但无反弹信号 → 熔断，不抄底
                    if is_deep_drawdown:
                        logger.info(
                            f"持仓基金 {f_name}({f_code}) 深度回撤 {estimated_profit_rate:.2f}% 但无反弹信号"
                            f"(week={week_growth_rate:.2f}%, month={month_growth_rate:.2f}%)，继续熔断等待"
                        )
                    else:
                        # 注意：此分支为 [-10%, -5%) 的「死区」——深跌分支的门槛是 < -10%，
                        # 所以这一段够不到抄底通道，此时即便三信号全部转好也一律不买。
                        logger.info(
                            f"持仓基金 {f_name}({f_code}) 预估收益率 {estimated_profit_rate:.2f}% 在 [-10%, -5%) 死区，"
                            f"熔断暂停，等待回收至 -5% 以上或触发深度反弹信号"
                        )
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

            if not _passes_index_heat_filter(
                fund_code=f_code,
                fund_name=f_name,
                fund_info=fund_info,
                buy_context="常规加仓",
            ):
                continue

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
            logger.info(
                f"持仓基金 {f_name}({f_code}) 预估收益率 {estimated_profit_rate:.2f}% >= -1.0%，"
                f"且持仓资产({current_asset_value:.2f}) >= 买入金额*0.95({min_asset_value_for_limited:.2f})，不满足加仓条件"
            )


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
        index_heat_filter_enabled = True
        # 2. 设置测试参数
        test_sub_account = "大数定律"
        test_amount = 10000.0
        test_limit = 100000.0
        test_total_limit = 1000000.0
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
            limit=test_limit,
            total_limit=test_total_limit,
            index_heat_filter_enabled=index_heat_filter_enabled,
            hqb_ratio_limit_enabled=True,
        )
        
        print(f"--- 测试结束 ---")

    except Exception as e:
        logger.error(f"测试执行失败: {e}")
