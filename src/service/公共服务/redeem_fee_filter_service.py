from typing import Any, Dict, List, Optional, Set, Tuple

from src.API.交易管理.feeMrg import getFee
from src.common.logger import get_logger

logger = get_logger(__name__)


def _parse_rate_to_float(rate: Optional[object]) -> Optional[float]:
    if rate is None:
        return None
    try:
        if isinstance(rate, (int, float)):
            return float(rate)
        s = str(rate).strip()
        if not s:
            return None
        if s.endswith("%"):
            s = s[:-1].strip()
        return float(s)
    except Exception:
        return None


def extract_redemption_rate_set(fee_data: Optional[Dict[str, Any]]) -> Tuple[Optional[Set[float]], List[str], str]:
    if not isinstance(fee_data, dict):
        return None, [], "fee_data_invalid"
    details = fee_data.get("RedemptionFractionalChargeDetailList")
    if not isinstance(details, list) or not details:
        return None, [], "fee_detail_missing"

    rates: Set[float] = set()
    raw_rates: List[str] = []
    for item in details:
        if not isinstance(item, dict):
            continue
        raw = item.get("Rate")
        raw_rates.append(str(raw))
        v = _parse_rate_to_float(raw)
        if v is None:
            continue
        rates.add(round(v, 4))
    return rates, raw_rates, "ok"


def is_redemption_rate_set_allowed(
    fee_data: Optional[Dict[str, Any]],
    allowed_rates: Set[float],
) -> Tuple[bool, str]:
    rates, raw_rates, status = extract_redemption_rate_set(fee_data)
    if rates is None:
        return False, status
    normalized_allowed = {round(float(x), 4) for x in allowed_rates}
    if rates == normalized_allowed:
        return True, f"ok rates={sorted(rates)}"
    return False, f"reject rates={sorted(rates)} raw_rates={raw_rates}"


def is_high_frequency_index_fee_ok(fee_data: Optional[Dict[str, Any]]) -> Tuple[bool, str]:
    return is_redemption_rate_set_allowed(fee_data, {0.0, 1.5})


def filter_indices_by_tracking_fund_fee(
    user,
    indices: List[Dict[str, Any]],
    scene_name: str,
) -> List[Dict[str, Any]]:
    """
    过滤跟踪基金赎回费率不适合高频轮动的指数。

    仅保留赎回费率分段集合严格等于 {0.0, 1.5} 的基金：
      - 1.5%: 持有不足 7 天
      - 0.0%: 持有满 7 天

    若某指数的 track_fund_code 不满足该条件，则视为“该指数当前无合格跟踪基金”，
    直接从候选中放弃，不再尝试回退到其他基金。
    """
    if not indices:
        return []

    fee_cache: Dict[str, Dict[str, Any]] = {}
    filtered: List[Dict[str, Any]] = []

    for idx in indices:
        index_code = str(idx.get("index_code") or "")
        index_name = str(idx.get("index_name") or "Unknown")
        fund_code = str(idx.get("track_fund_code") or "").strip()
        fund_name = str(idx.get("track_fund_name") or "Unknown")

        if not fund_code:
            logger.info(f"[{scene_name}] 跳过 {index_code} {index_name}: 无跟踪基金代码")
            continue

        try:
            if fund_code not in fee_cache:
                fee_cache[fund_code] = getFee(user, fund_code)
            ok, reason = is_high_frequency_index_fee_ok(fee_cache.get(fund_code))
        except Exception as e:
            logger.warning(
                f"[{scene_name}] 放弃 {index_code} {index_name}: "
                f"跟踪基金 {fund_code} {fund_name} 费率查询失败 ({e})"
            )
            continue

        if not ok:
            logger.info(
                f"[{scene_name}] 放弃 {index_code} {index_name}: "
                f"跟踪基金 {fund_code} {fund_name} 不满足“持有7天后赎回费为0”要求 ({reason})"
            )
            continue

        filtered.append(idx)

    return filtered
