import os
import sys
from typing import Dict, List, Optional, Set, Tuple

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.constant import (
    DEFAULT_USER,
    RS_FUND_TYPE_INDEX,
    RS_SUB_FUND_TYPE_INDEX_EQUITY,
)
from src.API.自选基金.FavorFund import get_favor_groups, add_to_favorites, get_favor_group
from src.API.市场指数.获取追踪指数的基金 import get_tracking_funds
from src.common.logger import get_logger
from src.service.基金信息.基金信息 import get_all_fund_info
from src.service.市场指数.market_index_service import MarketIndexService

logger = get_logger(__name__)

TARGET_INDEX_TYPE_CODES = ["001001", "001002", "001003"]
INDEX_HEAT_MIN_SCORE = 20.0
INDEX_MAIN_NET_INFLOW_MIN = 50_000_000.0
INDEX_MAIN_NET_INFLOW_POSITIVE_DAYS_WINDOW = 10
INDEX_MAIN_NET_INFLOW_MIN_POSITIVE_DAYS = 5
INDEX_MAIN_NET_INFLOW_SUM_WINDOW = 3
INDEX_MAIN_NET_INFLOW_SUM_MIN = 50_000_000.0
TRACKING_FUND_MAX_REDEEM_FEE_AFTER_7 = 0.5



def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def _safe_optional_float(value) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def _is_class_c(value) -> bool:
    try:
        return float(value) == 1.0
    except Exception:
        return str(value).strip() == "1"


def _get_cached_fund_info(user, fund_code: str, cache: Dict[str, object]):
    if not fund_code:
        return None
    if fund_code not in cache:
        cache[fund_code] = get_all_fund_info(user, fund_code)
    return cache[fund_code]


def _append_theme(theme_list: List[Tuple[str, str]], seen_codes: Set[str], theme_code: str, theme_name: str) -> None:
    theme_code = str(theme_code or "").strip()
    theme_name = str(theme_name or "").strip()
    if not theme_code.upper().startswith("BK"):
        return
    if theme_code in seen_codes:
        return
    seen_codes.add(theme_code)
    theme_list.append((theme_code, theme_name))


def _resolve_candidate_themes(snapshot: Dict, fund_info) -> List[Tuple[str, str]]:
    theme_list: List[Tuple[str, str]] = []
    seen_codes: Set[str] = set()

    theme_infos = getattr(fund_info, "theme_infos", None) or []
    show_themes = [theme for theme in theme_infos if getattr(theme, "isshow", False)]
    other_themes = [theme for theme in theme_infos if not getattr(theme, "isshow", False)]
    for theme in show_themes + other_themes:
        _append_theme(
            theme_list,
            seen_codes,
            getattr(theme, "sec_code", ""),
            getattr(theme, "sec_name", ""),
        )

    relate_themes = getattr(fund_info, "relate_themes", None) or []
    relate_themes = sorted(
        relate_themes,
        key=lambda item: _safe_float(getattr(item, "corr_1y", 0.0), 0.0),
        reverse=True,
    )
    for theme in relate_themes:
        _append_theme(
            theme_list,
            seen_codes,
            getattr(theme, "sec_code", ""),
            getattr(theme, "sec_name", ""),
        )

    sec_codes = [code.strip() for code in str(snapshot.get("sec_code") or "").split(",") if code.strip()]
    sec_names = [name.strip() for name in str(snapshot.get("sec_name") or "").split(",") if name.strip()]
    for idx, sec_code in enumerate(sec_codes):
        sec_name = sec_names[idx] if idx < len(sec_names) else ""
        _append_theme(theme_list, seen_codes, sec_code, sec_name)

    return theme_list


def _build_candidate_group_keys(candidate: Dict) -> List[str]:
    themes = candidate.get("themes") or []
    if themes:
        return [f"theme:{theme_code}" for theme_code, _ in themes if theme_code]
    return [f"index:{candidate['index_code']}"]


def _passes_signal_filters(snapshot: Dict) -> bool:
    heat_score = _safe_optional_float(snapshot.get("latest_heat_score"))
    if heat_score is None or heat_score < INDEX_HEAT_MIN_SCORE:
        return False

    latest_main_net_inflow = _safe_optional_float(snapshot.get("latest_main_net_inflow"))
    if latest_main_net_inflow is None or latest_main_net_inflow < INDEX_MAIN_NET_INFLOW_MIN:
        return False

    inflow_snapshot = snapshot.get("inflow_snapshot") or {}
    if not inflow_snapshot.get("positive_days_available"):
        return False

    positive_days_count = int(inflow_snapshot.get("positive_days_count") or 0)
    if positive_days_count < INDEX_MAIN_NET_INFLOW_MIN_POSITIVE_DAYS:
        return False

    if not inflow_snapshot.get("inflow_sum_available"):
        return False

    recent_inflow_sum = _safe_optional_float(inflow_snapshot.get("recent_inflow_sum"))
    if recent_inflow_sum is None or recent_inflow_sum < INDEX_MAIN_NET_INFLOW_SUM_MIN:
        return False

    return True


def _select_best_tracking_a_share_c_fund(
    user,
    index_code: str,
    fund_info_cache: Dict[str, object],
) -> Optional[Dict]:
    resp = get_tracking_funds(user, [index_code], page_size=50)
    if not resp.success:
        logger.warning(f"[{index_code}] 获取跟踪基金失败: {resp.first_error}")
        return None

    fund_list = resp.items.get(index_code, [])
    if not fund_list:
        logger.info(f"[{index_code}] 无跟踪基金数据")
        return None

    candidates: List[Dict] = []
    for fund in fund_list:
        if getattr(fund, "ISEXCHG", "") != "0":
            continue
        if getattr(fund, "DTZT", "") != "1":
            continue
        if getattr(fund, "ISBUY", "") != "1":
            continue
        if not _is_class_c(getattr(fund, "ISCLASSC", None)):
            continue

        shrate7 = _safe_optional_float(getattr(fund, "SHRATE7", None))
        if shrate7 is None or shrate7 > TRACKING_FUND_MAX_REDEEM_FEE_AFTER_7:
            continue

        fund_code = str(getattr(fund, "FCODE", "") or "").strip()
        fund_info = _get_cached_fund_info(user, fund_code, fund_info_cache)
        if not fund_info:
            continue

        fund_type = str(getattr(fund_info, "fund_type", "") or "").strip()
        fund_sub_type = str(getattr(fund_info, "fund_sub_type", "") or "").strip()
        if fund_type != RS_FUND_TYPE_INDEX or fund_sub_type != RS_SUB_FUND_TYPE_INDEX_EQUITY:
            continue

        candidates.append({
            "fund_code": fund_code,
            "fund_name": str(getattr(fund, "SHORTNAME", "") or "").strip(),
            "fund_endnav": _safe_float(getattr(fund, "ENDNAV", None), 0.0),
            "shrate7": shrate7,
            "fund_info": fund_info,
        })

    if not candidates:
        logger.info(f"[{index_code}] 无符合条件的 A 股 C 类低赎回费跟踪基金")
        return None

    best = max(candidates, key=lambda row: (row["fund_endnav"], row["fund_code"]))
    logger.info(
        f"[{index_code}] 关联基金: {best['fund_code']} {best['fund_name']} "
        f"(规模={best['fund_endnav']:.1f}万, SHRATE7={best['shrate7']:.2f}%)"
    )
    return best


def _collect_items(obj) -> List[Dict]:
    items = []
    if isinstance(obj, dict):
        if any(k in obj for k in ["fcode", "FundCode", "fund_code", "FCODE", "code"]):
            items.append(obj)
        else:
            for v in obj.values():
                items.extend(_collect_items(v))
    elif isinstance(obj, list):
        for i in obj:
            items.extend(_collect_items(i))
    return items


def get_group_info(user, group_name: str) -> Tuple[int, Set[str]]:
    response = get_favor_groups(user=user)
    if not response.Success:
        logger.error(f"Failed to get favor groups: {response.FirstError}")
        return -1, set()

    target_group_id = -1
    existing_funds = set()

    if not response.Data:
        return -1, set()

    groups_list = []
    if isinstance(response.Data, list):
        groups_list = response.Data
    elif isinstance(response.Data, dict):
        for key in ["list_group", "ListGroup", "datas", "data", "groups", "Groups", "GroupList"]:
            if key in response.Data:
                val = response.Data[key]
                if isinstance(val, list):
                    groups_list = val
                    break
        if not groups_list:
            for v in response.Data.values():
                if isinstance(v, list):
                    groups_list = v
                    break

    for group in groups_list:
        if not isinstance(group, dict):
            continue
        name = group.get("groupName") or group.get("group_name") or group.get("GroupName") or group.get("gname") or group.get("Name")
        if name == group_name:
            target_group_id = group.get("groupId") or group.get("group_id") or group.get("GroupId") or group.get("Id")
            break

    if target_group_id != -1:
        detail_resp = get_favor_group(group_ids=str(target_group_id), user=user)
        if detail_resp.Success and detail_resp.Data:
            funds = _collect_items(detail_resp.Data)
            for f in funds:
                code = f.get("fcode") or f.get("FundCode") or f.get("FCODE") or f.get("fund_code") or f.get("code")
                if code:
                    existing_funds.add(str(code))

    return target_group_id, existing_funds


def get_qualified_fund_candidates(user) -> List[Dict]:
    market_index_service = MarketIndexService()
    snapshots = market_index_service.fetch_all_indices_realtime_market_snapshots(
        user,
        type_codes=TARGET_INDEX_TYPE_CODES,
        positive_days_window=INDEX_MAIN_NET_INFLOW_POSITIVE_DAYS_WINDOW,
        min_positive_days=INDEX_MAIN_NET_INFLOW_MIN_POSITIVE_DAYS,
        inflow_sum_window=INDEX_MAIN_NET_INFLOW_SUM_WINDOW,
    )
    if not snapshots:
        logger.info("市场指数接口未返回可用指数数据。")
        return []

    latest_trade_date = max(
        [str(row.get("latest_trade_date") or "") for row in snapshots if row.get("latest_trade_date")],
        default="",
    )
    logger.info(
        f"市场指数实时接口数据共 {len(snapshots)} 个，"
        f"最新净流入交易日: {latest_trade_date or '-'}"
    )

    signal_qualified = [row for row in snapshots if _passes_signal_filters(row)]
    logger.info(
        f"热度/净流入筛选后剩余 {len(signal_qualified)} 个指数 "
        f"(热度>={INDEX_HEAT_MIN_SCORE:.0f}, 当日净流入>={INDEX_MAIN_NET_INFLOW_MIN:.0f}, "
        f"近{INDEX_MAIN_NET_INFLOW_POSITIVE_DAYS_WINDOW}日正流入天数>={INDEX_MAIN_NET_INFLOW_MIN_POSITIVE_DAYS}, "
        f"近{INDEX_MAIN_NET_INFLOW_SUM_WINDOW}日净流入合计>={INDEX_MAIN_NET_INFLOW_SUM_MIN:.0f})"
    )
    if not signal_qualified:
        return []

    fund_info_cache: Dict[str, object] = {}
    mapped_candidates: List[Dict] = []
    for snapshot in signal_qualified:
        best_fund = _select_best_tracking_a_share_c_fund(user, snapshot["index_code"], fund_info_cache)
        if not best_fund:
            continue

        themes = _resolve_candidate_themes(snapshot, best_fund["fund_info"])
        primary_theme_code = themes[0][0] if themes else ""
        primary_theme_name = themes[0][1] if themes else ""
        mapped_candidates.append({
            **snapshot,
            **best_fund,
            "theme_code": primary_theme_code,
            "theme_name": primary_theme_name,
            "themes": themes,
        })

    logger.info(f"完成指数基金关联后，剩余 {len(mapped_candidates)} 只基金候选")
    if not mapped_candidates:
        return []

    # 候选优先级改为热度优先，避免不同指数规模差异导致净流入绝对值不可直接横向比较。
    # 同热度下，再用净流入与基金规模做次级排序。
    mapped_candidates.sort(
        key=lambda row: (
            _safe_float(row.get("latest_heat_score"), 0.0),
            _safe_float(row.get("latest_main_net_inflow"), 0.0),
            _safe_float(row.get("fund_endnav"), 0.0),
        ),
        reverse=True,
    )

    occupied_group_keys: Dict[str, Dict] = {}
    result: List[Dict] = []
    for candidate in mapped_candidates:
        group_keys = _build_candidate_group_keys(candidate)
        conflicted_keys = [group_key for group_key in group_keys if group_key in occupied_group_keys]
        if conflicted_keys:
            conflicted_candidates = []
            seen_funds: Set[str] = set()
            for group_key in conflicted_keys:
                existing = occupied_group_keys[group_key]
                fund_code = str(existing.get("fund_code") or "")
                if fund_code and fund_code not in seen_funds:
                    conflicted_candidates.append(existing)
                    seen_funds.add(fund_code)
            conflict_desc = "; ".join(
                f"{existing['fund_code']} {existing['fund_name']}({','.join(_build_candidate_group_keys(existing))})"
                for existing in conflicted_candidates
            )
            logger.info(
                f"[BK去重] 跳过 {candidate['fund_code']} {candidate['fund_name']} "
                f"(index={candidate['index_code']}, heat={_safe_float(candidate.get('latest_heat_score')):.2f}, "
                f"main_net_inflow={_safe_float(candidate.get('latest_main_net_inflow')):.2f})，"
                f"与已保留候选主题重叠: {conflict_desc}"
            )
            continue

        for group_key in group_keys:
            occupied_group_keys[group_key] = candidate
        result.append(candidate)

    logger.info(f"BK 主题去重后最终保留 {len(result)} 只基金")
    for row in result:
        theme_desc = ", ".join(
            f"{theme_code}:{theme_name or '-'}"
            for theme_code, theme_name in (row.get("themes") or [])
        ) or "-"
        logger.info(
            f"[候选] {row['fund_code']} {row['fund_name']} <- "
            f"{row['index_code']} {row['index_name']} "
            f"(themes={theme_desc}, "
            f"heat={_safe_float(row.get('latest_heat_score')):.2f}, "
            f"main_net_inflow={_safe_float(row.get('latest_main_net_inflow')):.2f}, "
            f"3日合计={_safe_float((row.get('inflow_snapshot') or {}).get('recent_inflow_sum')):.2f})"
        )
    return result


def get_qualified_fund_codes(user) -> Set[str]:
    return {
        str(row["fund_code"])
        for row in get_qualified_fund_candidates(user)
        if row.get("fund_code")
    }


def add_qualified_funds_to_group(user, group_name: str = "智投平台", dry_run: bool = False) -> Dict[str, int]:
    logger.info(f"开始筛选满足条件的基金，目标组合: '{group_name}'...")

    qualified_candidates = get_qualified_fund_candidates(user)
    if not qualified_candidates:
        logger.info("没有满足条件的指数基金。")
        return {"total_qualified": 0, "added": 0, "skipped": 0, "no_track_fund": 0}

    group_id, existing_funds = get_group_info(user, group_name)
    if group_id == -1:
        logger.error(f"目标组合 '{group_name}' 未找到，请先在天天基金中创建该自选组合。")
        return {"total_qualified": len(qualified_candidates), "added": 0, "skipped": 0, "no_track_fund": 0}

    logger.info(f"目标组合: {group_name} (ID: {group_id})")
    logger.info(f"组合当前基金数: {len(existing_funds)}")
    logger.info(f"满足条件的基金: {len(qualified_candidates)} 个")

    stats = {
        "total_qualified": len(qualified_candidates),
        "added": 0,
        "skipped": 0,
        "no_track_fund": 0,
    }

    for candidate in qualified_candidates:
        index_code = candidate["index_code"]
        index_name = candidate["index_name"]
        fund_code = str(candidate["fund_code"]) if candidate.get("fund_code") else ""
        fund_name = candidate.get("fund_name", "Unknown")

        if not fund_code:
            stats["no_track_fund"] += 1
            continue

        logger.info(
            f"[{index_code} {index_name}] 跟踪基金: {fund_code} {fund_name} "
            f"(theme={candidate.get('theme_code') or '-'} {candidate.get('theme_name') or ''}, "
            f"heat={_safe_float(candidate.get('latest_heat_score')):.2f}, "
            f"main_net_inflow={_safe_float(candidate.get('latest_main_net_inflow')):.2f}, "
            f"近10日正流入天数={int((candidate.get('inflow_snapshot') or {}).get('positive_days_count') or 0)}, "
            f"近3日净流入合计={_safe_float((candidate.get('inflow_snapshot') or {}).get('recent_inflow_sum')):.2f}, "
            f"规模={_safe_float(candidate.get('fund_endnav')):.1f}万, "
            f"SHRATE7={_safe_float(candidate.get('shrate7')):.2f}%)"
        )

        if fund_code in existing_funds:
            logger.info("  -> 跳过: 已在组合中")
            stats["skipped"] += 1
            continue

        if dry_run:
            logger.info("  -> dry_run: 不执行添加")
            stats["skipped"] += 1
            continue

        try:
            resp = add_to_favorites(fund_code=fund_code, group_id=int(group_id), user=user)
            if resp.Success:
                logger.info("  -> 添加成功")
                stats["added"] += 1
            else:
                if resp.ErrorCode == 63117 or "已存在" in str(resp.FirstError):
                    logger.info("  -> 已存在 (API 返回重复提示)")
                    stats["skipped"] += 1
                else:
                    logger.error(f"  -> 添加失败: {resp.FirstError} (Code: {resp.ErrorCode})")
        except Exception as e:
            logger.error(f"  -> 异常: {e}")

    logger.info("-" * 40)
    logger.info(f"智投平台组合更新完成. 统计: {stats}")
    return stats


if __name__ == "__main__":
    from src.API.登录接口.login import ensure_user_fresh

    user = ensure_user_fresh(DEFAULT_USER)
    add_qualified_funds_to_group(user=user, group_name="智投平台")
