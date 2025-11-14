# 顶部导入处
import logging
import os
import sys
import time
import datetime
from typing import Any, Dict, List, Optional, Union

# 先修正 sys.path，再进行 src.* 导入
project_root = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
        )
    )
)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.common.logger import get_logger
from src.domain.user.User import User
from src.API.定投计划管理.SmartPlan import createPlanV3, getFundPlanList, getPlanDetailPro
from src.domain.fund_plan import FundPlan, ApiResponse

# 在 logger 定义后新增独立函数
logger = get_logger("MonthlyPlanService")


def _normalize_amount(amount: Union[str, float, int]) -> str:
    """
    将金额统一为字符串，满足 API 要求
    """
    if isinstance(amount, str):
        return amount
    if isinstance(amount, (float, int)):
        return str(amount)
    raise ValueError("amount 必须是 str、float 或 int 类型")


def _existing_monthly_day_map(plans: List[FundPlan], fund_code: str) -> Dict[int, FundPlan]:
    """
    提取该基金已存在的月定投计划的映射：day -> FundPlan（periodType=3）
    """
    day_map: Dict[int, FundPlan] = {}
    for p in plans or []:
        try:
            if p.fundCode == fund_code and int(p.periodType) == 3:
                day_map[int(p.periodValue)] = p
        except Exception:
            # 某些数据可能缺失或类型不一致，忽略即可
            continue
    return day_map


def create_monthly_plans_for_fund(
    user: User,
    fund_code: str,
    amount: Union[str, float, int],
    days: Optional[List[int]] = None,
    sub_account_name: Optional[str] = None,
    skip_existing: bool = True,
    sleep_sec: float = 3,
) -> Dict[str, Any]:
    """
    为指定基金创建每月 1–28 号的月定投计划（periodType=3, periodValue=day）

    Args:
        user: 已登录用户对象
        fund_code: 基金代码
        amount: 定投金额（str/float/int），会转换为 str 传给 API
        days: 指定需要创建的日列表，默认 [1..28]
        sub_account_name: 可选，指定子账户名称
        skip_existing: 是否跳过已存在的同基金同日月定投计划
        sleep_sec: 每次创建之间的间隔，避免接口限流

    Returns:
        汇总字典，包含 success_list / failed_list / summary 等
    """
    amount_str = _normalize_amount(amount)
    if days is None:
        days = list(range(1, 29))

    # 查询该基金已有定投计划，用于去重（可选）
    existing_day_map: Dict[int, FundPlan] = {}
    if skip_existing:
        try:
            # 使用新的“详情级”查询函数，避免列表期字段缺失导致为空
            existing_day_map = get_existing_monthly_day_map(user, fund_code, sleep_sec=0.0)
        except Exception as e:
            logger.warning(f"获取基金 {fund_code} 月定投详情失败，将不进行去重。错误: {e}")

    success_list: List[Dict[str, Any]] = []
    failed_list: List[Dict[str, Any]] = []
    created_count = 0
    skipped_count = 0

    for day in days:
        if skip_existing and day in existing_day_map:
            existing_plan = existing_day_map.get(day)
            msg = (
                f"基金 {fund_code} 的月定投计划（每月{day}号）已存在，跳过。"
                f"已有计划ID: {getattr(existing_plan, 'planId', '')}, 金额: {getattr(existing_plan, 'amount', '')}"
            )
            logger.info(msg)
            print(msg)
            success_list.append({
                "fund_code": fund_code,
                "day": day,
                "skipped": True,
                "message": msg,
                "plan_id": getattr(existing_plan, "planId", None),
                "amount": getattr(existing_plan, "amount", None),
            })
            skipped_count += 1
            continue

        try:
            resp: ApiResponse[FundPlan] = createPlanV3(
                user=user,
                fund_code=fund_code,
                amount=amount_str,
                period_type=3,            # 3 表示每月
                period_value=str(day),    # 每月的第几天
                sub_account_name=sub_account_name,
                strategy_type=0           # 目标止盈定投（默认值）
            )

            if resp and resp.Success and resp.Data:
                plan: FundPlan = resp.Data
                logger.info(f"创建成功：基金 {fund_code} 每月{day}号，计划ID: {plan.planId}，金额: {plan.amount}")
                success_list.append({
                    "fund_code": fund_code,
                    "day": day,
                    "plan_id": plan.planId,
                    "amount": plan.amount,
                    "skipped": False
                })
                created_count += 1
            else:
                err = (resp.FirstError if resp else "未知错误") or "未知错误"
                logger.warning(f"创建失败：基金 {fund_code} 每月{day}号，错误: {err}")
                failed_list.append({
                    "fund_code": fund_code,
                    "day": day,
                    "error": err
                })

        except Exception as e:
            logger.error(f"创建失败：基金 {fund_code} 每月{day}号，异常: {e}")
            failed_list.append({
                "fund_code": fund_code,
                "day": day,
                "error": str(e)
            })

        # 适当休眠，避免触发限流
        if sleep_sec and sleep_sec > 0:
            time.sleep(sleep_sec)

    summary = {
        "fund_code": fund_code,
        "amount": amount_str,
        "days_total": len(days),
        "created": created_count,
        "skipped": skipped_count,
        "failed": len(failed_list),
    }

    return {
        "summary": summary,
        "success_list": success_list,
        "failed_list": failed_list,
    }




# 新增：独立的查询函数（day -> FundPlan 映射）
def get_existing_monthly_day_map(
    user: User,
    fund_code: str,
    sleep_sec: float = 0.15
) -> Dict[int, FundPlan]:
    logger.info(f"开始查询基金 {fund_code} 已有的月定投计划详情（periodType=3）")
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
            detail = resp.Data
            ration_plan = detail.rationPlan
            period_type = int(getattr(ration_plan, "periodType", 0) or 0)
            period_value = int(getattr(ration_plan, "periodValue", 0) or 0)

            if period_type == 3 and period_value > 0:
                day_map[period_value] = ration_plan

        except Exception as e:
            logger.warning(f"计划 {plan_id} 详情解析异常：{e}")
        finally:
            if sleep_sec and sleep_sec > 0:
                time.sleep(sleep_sec)

    details = {
        day: {
            "plan_id": getattr(plan, "planId", None),
            "amount": getattr(plan, "amount", None),
        } for day, plan in day_map.items()
    }
    logger.info(f"基金 {fund_code} 已存在的月定投日: {sorted(day_map.keys())}")
    logger.info(f"基金 {fund_code} 已存在的月定投详情: {details}")
    return day_map


if __name__ == "__main__":
    # 示例：在控制台运行时打印日志
    logging.basicConfig(level=logging.INFO)
    try:
        from src.API.定投计划管理.SmartPlan import DEFAULT_USER
        # 批量创建 1–28 号的月定投（已存在则跳过）
        result = create_monthly_plans_for_fund(
            user=DEFAULT_USER,
            fund_code="021740",
            amount="10000.0",
            sub_account_name=None,
            skip_existing=True
        )
        print("执行汇总:", result["summary"])
        print("成功/跳过:", len(result["success_list"]))
        print("失败:", len(result["failed_list"]))

    except Exception as e:
        logger.error(f"示例运行失败: {e}")
