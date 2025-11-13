import logging
from src.common.logger import get_logger
from typing import Any


def nav5_gate(fi: Any, fund_name: str, fund_code: str, logger: logging.Logger) -> bool:
    """
    公共净值门槛判定：估算净值（缺失则用最近交易日净值nav）必须大于5日均值。
    保持统一的日志输出。
    """
    est_nav = getattr(fi, 'estimated_value', None)
    nav_prev = getattr(fi, 'nav', None)
    nav5 = getattr(fi, 'nav_5day_avg', None)
    used_prev = False
    try:
        if est_nav is None:
            est_val = float(nav_prev) if nav_prev is not None else None
            used_prev = True
        else:
            est_val = float(est_nav)
        nav5_val = float(nav5) if nav5 is not None else None
    except Exception:
        est_val = None
        nav5_val = None

    if est_val is None or nav5_val is None:
        logger.info(
            f"跳过{fund_name}({fund_code}): 缺少用于对比的净值（estimated_value={est_nav}, prev_nav={nav_prev}, nav_5day_avg={nav5}）",
            extra={"fund_code": fund_code, "action": "nav5_gate"}
        )
        return False

    if used_prev:
        logger.info(
            f"{fund_name}({fund_code})缺少估值，使用上一交易日净值 {est_val:.4f} 与5日均值 {nav5_val:.4f} 进行对比",
            extra={"fund_code": fund_code, "action": "nav5_gate"}
        )
    else:
        logger.info(
            f"{fund_name}({fund_code})使用估算净值 {est_val:.4f} 与5日均值 {nav5_val:.4f} 进行对比",
            extra={"fund_code": fund_code, "action": "nav5_gate"}
        )

    if not (est_val > nav5_val):
        logger.info(
            f"跳过{fund_name}({fund_code}): 对比净值 {est_val:.4f} <= 5日均值 {nav5_val:.4f}",
            extra={"fund_code": fund_code, "action": "nav5_gate"}
        )
        return False
    return True

def nav5_fall_gate(fi: Any, fund_name: str, fund_code: str, logger: logging.Logger) -> bool:
    """
    止盈净值门槛判定：估算净值（缺失则用最近交易日净值nav）必须低于5日均值。
    保持统一的日志输出。
    """
    est_nav = getattr(fi, 'estimated_value', None)
    nav_prev = getattr(fi, 'nav', None)
    nav5 = getattr(fi, 'nav_5day_avg', None)
    used_prev = False
    try:
        if est_nav is None:
            est_val = float(nav_prev) if nav_prev is not None else None
            used_prev = True
        else:
            est_val = float(est_nav)
        nav5_val = float(nav5) if nav5 is not None else None
    except Exception:
        est_val = None
        nav5_val = None

    if est_val is None or nav5_val is None:
        logger.info(
            f"跳过{fund_name}({fund_code}): 缺少用于对比的净值（estimated_value={est_nav}, prev_nav={nav_prev}, nav_5day_avg={nav5}）",
            extra={"fund_code": fund_code, "action": "nav5_fall_gate"}
        )
        return False

    if used_prev:
        logger.info(
            f"{fund_name}({fund_code})缺少估值，使用上一交易日净值 {est_val:.4f} 与5日均值 {nav5_val:.4f} 进行对比",
            extra={"fund_code": fund_code, "action": "nav5_fall_gate"}
        )
    else:
        logger.info(
            f"{fund_name}({fund_code})使用估算净值 {est_val:.4f} 与5日均值 {nav5_val:.4f} 进行对比",
            extra={"fund_code": fund_code, "action": "nav5_fall_gate"}
        )

    if not (est_val < nav5_val):
        logger.info(
            f"跳过{fund_name}({fund_code}): 当前对比净值 {est_val:.4f} ≥ 5日均值 {nav5_val:.4f}，未进入下跌态（不止盈）",
            extra={"fund_code": fund_code, "action": "nav5_fall_gate"}
        )
        return False
    return True
