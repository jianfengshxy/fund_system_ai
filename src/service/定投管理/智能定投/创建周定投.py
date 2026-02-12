# 顶部导入处（补充 time 与 FundPlan 类型）
import os
import sys
import logging
from typing import Dict, Any, Optional, List, Union
import time

# 动态注入项目根目录，避免 ModuleNotFoundError: No module named 'src'
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.common.logger import get_logger

from src.domain.user.User import User
from src.common.constant import DEFAULT_USER
from src.API.定投计划管理.SmartPlan import (
    getFundPlanList,
    getPlanDetailPro,
    createPlanV3,
)
from src.domain.fund_plan.fund_plan import FundPlan
from src.domain.fund_plan.fund_plan_detail import FundPlanDetail

logger = get_logger("WeeklySmartPlanCreate")


def _period_text(period_type: int, period_value: Optional[int]) -> str:
    # periodType 对照：
    # 1：周定投（weekly）
    # 2：双周定投（biweekly）
    # 3：月定投（monthly）
    # 4：日定投（daily）
    if period_type == 3:
        return f"每月{str(period_value).rjust(2)}号" if period_value else "每月"
    elif period_type == 1:
        return f"每周{period_value}" if period_value else "每周"
    elif period_type == 2:
        return f"双周{period_value}" if period_value else "双周"
    elif period_type == 4:
        return "每日"
    return f"周期{period_type}(值={period_value})"


def get_existing_weekly_day_map(
    user: User,
    fund_code: str,
    sleep_sec: float = 3
) -> Dict[int, FundPlan]:
    """
    查询指定基金的现有“周定投”（periodType=1）详情，返回 {weekday -> rationPlan} 映射。
    - weekday：周几（通常 1..7）
    - 去重仅基于 periodType + periodValue（金额不参与判定）
    """
    logger.info(f"开始查询基金 {fund_code} 已有的周定投计划详情（periodType=1）")
    plans = getFundPlanList(fund_code, user) or []
    day_map: Dict[int, FundPlan] = {}

    for p in plans:
        plan_id = getattr(p, "planId", "")
        if not plan_id:
            continue
        try:
            resp = getPlanDetailPro(plan_id, user)
            if not resp or not resp.Success or not resp.Data:
                logger.warning(f"计划 {plan_id} 详情获取失败或为空，跳过。")
                continue
            detail: FundPlanDetail = resp.Data
            rp: FundPlan = detail.rationPlan
            
            # 将 shares 信息附加到 rationPlan 对象上，以便后续使用
            if hasattr(detail, 'shares') and detail.shares:
                rp.shares = detail.shares

            period_type = int(getattr(rp, "periodType", 0) or 0)
            period_value = int(getattr(rp, "periodValue", 0) or 0)

            if period_type == 1 and period_value > 0:
                day_map[period_value] = rp

        except Exception as e:
            logger.warning(f"计划 {plan_id} 详情解析异常：{e}")
        finally:
            if sleep_sec and sleep_sec > 0:
                time.sleep(sleep_sec)

    details = {
        day: {
            "plan_id": getattr(rp, "planId", None),
            "amount": getattr(rp, "amount", None),
        } for day, rp in day_map.items()
    }
    logger.info(f"基金 {fund_code} 已存在的周定投周几: {sorted(day_map.keys())}")
    logger.info(f"基金 {fund_code} 已存在的周定投详情: {details}")
    return day_map


def create_weekly_smart_investment_plans(
    user: User,
    fund_code: str,
    amount: str = "1000.0",
    days: Optional[List[int]] = None,
    sub_account_name: Optional[str] = None,
    strategy_type: int = 0,
    target_profit_rate: Optional[Union[str, float, int]] = None,
    throttle_sec: float = 5.0,   # 新增：相邻创建之间的节流秒数
    max_retries: int = 1         # 新增：遇到“重复提交”时的重试次数
) -> Dict[str, Any]:
    """
    为指定基金创建周定投（默认周一到周五）。
    - 创建前先查询同基金下 periodType=2 + periodValue=周几 的计划，存在则跳过
    - amount: 统一定投金额（字符串或数字），默认 "1000.0"
    - days: 指定周几列表，默认 [1,2,3,4,5]
    - sub_account_name: 子账户名（可选），传入则按 SmartPlan.createPlanV3 自动匹配子账户编号
    - strategy_type: 策略类型（默认 0=目标止盈定投）
    """
    if days is None:
        days = [1, 2, 3, 4, 5]

    logger.info(f"准备为基金 {fund_code} 创建周定投：周几={days}，金额={amount}，子账户={sub_account_name or '-'}，策略={strategy_type}")

    existing_map = get_existing_weekly_day_map(user, fund_code)
    results: List[Dict[str, Any]] = []

    for idx, day in enumerate(days or [1, 2, 3, 4, 5], start=1):
        # 重复检测：同基金 + 周定投(periodType=1) + 同一周几(periodValue)
        if day in existing_map:
            rp = existing_map[day]
            label = _period_text(1, day)
            logger.info(f"跳过 {label}：已存在周定投计划 planId={rp.planId}（金额不参与重复判定）")
            results.append({
                "day": day,
                "action": "skip",
                "reason": "exists",
                "planId": rp.planId,
                "amount": getattr(rp, "amount", None),
                "verified": True,
                "success": True
            })
            continue

        label = _period_text(1, day)

        # 节流：相邻创建之间等待，避免后端判定短时间重复提交
        if throttle_sec and throttle_sec > 0 and idx > 1:
            time.sleep(throttle_sec)

        attempt = 0
        last_error = None
        plan_id = None
        verified = False
        ok = False

        while attempt <= max_retries:
            try:
                logger.info(f"开始创建 {label} 周定投，金额={amount}（尝试 {attempt+1}/{max_retries+1}）")
                resp = createPlanV3(
                    user=user,
                    fund_code=fund_code,
                    amount=str(amount),
                    period_type=1,
                    period_value=str(day),
                    sub_account_name=sub_account_name,
                    strategy_type=strategy_type,
                    target_profit_rate=target_profit_rate
                )
                ok = getattr(resp, "Success", False)
                plan_id = getattr(resp.Data, "planId", None) if ok and getattr(resp, "Data", None) else None

                # 二次校验
                if ok and plan_id:
                    try:
                        verify = getPlanDetailPro(plan_id, user)
                        if getattr(verify, "Success", False) and getattr(verify, "Data", None):
                            vrp = verify.Data.rationPlan
                            verified = (int(getattr(vrp, "periodType", 0)) == 1 and int(getattr(vrp, "periodValue", 0)) == int(day))
                    except Exception as ve:
                        logger.warning(f"[校验] {label} 新建计划二次查询异常：{ve}")

                # 成功或非重复错误则跳出
                first_error = getattr(resp, "FirstError", None)
                if ok or not (first_error and "重复提交" in str(first_error)):
                    last_error = first_error
                    break

                # 遇到“重复提交”，等待后重试
                last_error = first_error
                if attempt < max_retries:
                    logger.warning(f"检测到短时间重复提交（{first_error}），等待 {throttle_sec:.1f}s 后重试...")
                    time.sleep(throttle_sec)
                attempt += 1

            except Exception as e:
                last_error = str(e)
                break

        if ok and verified:
            logger.info(f"✓ {label} 创建并已验证生效 (planId={plan_id})")
        elif ok and not verified:
            logger.warning(f"⚠ {label} 创建返回成功，但校验未生效 (planId={plan_id})")
        else:
            logger.error(f"✗ {label} 创建失败: {last_error}")

        results.append({
            "day": day,
            "action": "create",
            "success": ok,
            "verified": verified,
            "planId": plan_id,
            "error": last_error
        })

    # 汇总输出
    created_ok = sum(1 for r in results if r["action"] == "create" and r["success"])
    created_verified = sum(1 for r in results if r["action"] == "create" and r["success"] and r["verified"])
    skipped = sum(1 for r in results if r["action"] == "skip")

    logger.info(f"完成周定投创建，跳过已有: {skipped}，创建成功: {created_ok}（已验证: {created_verified}）")

    return {
        "fundCode": fund_code,
        "amount": amount,
        "days": days,
        "results": results,
        "summary": {
            "skipped": skipped,
            "created_ok": created_ok,
            "created_verified": created_verified
        }
    }


if __name__ == "__main__":
    info = create_weekly_smart_investment_plans(
        user=DEFAULT_USER,
        fund_code="012729",
        amount="10000.0",
        days=[1, 2, 3, 4, 5],
        sub_account_name=None,
        strategy_type=0,
        target_profit_rate="10%"
    )
    print(f"基金 {info['fundCode']} 周定投创建结果：")
    for r in info["results"]:
        label = _period_text(1, r["day"])
        status = "成功" if r["success"] else f"失败({r.get('error')})"
        verify_status = "已生效" if r.get("verified") else "未生效"
        print(f"- {label} {r['action']} -> {status} / 校验:{verify_status}, planId={r.get('planId')}")
    print(f"汇总：跳过已有={info['summary']['skipped']}，创建成功={info['summary']['created_ok']}，验证成功={info['summary']['created_verified']}")
