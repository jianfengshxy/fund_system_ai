from typing import Any, Dict, List, Optional, Set, Tuple


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

