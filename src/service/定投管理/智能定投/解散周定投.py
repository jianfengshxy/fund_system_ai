import os
import sys
import time
import logging
from typing import Dict, List, Optional, Set

# 将项目根目录加入 sys.path，支持直接运行此脚本
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.domain.user.User import User
from src.common.constant import DEFAULT_USER
from src.API.定投计划管理.SmartPlan import getFundPlanList, getPlanDetailPro, operateRation
from src.domain.fund_plan.fund_plan import FundPlan
from src.domain.fund_plan.fund_plan_detail import FundPlanDetail

logger = logging.getLogger("WeeklyDissolve")
logging.basicConfig(level=logging.INFO)


def get_existing_weekly_day_map(user: User, fund_code: str, sleep_sec: float = 0.15) -> Dict[int, FundPlan]:
    """
    查询指定基金现有的“周定投”计划映射（weekday -> FundPlan），需逐个拉详情判断 periodType/periodValue。

    约定:
    - 周定投 periodType == 1（严格以周定投识别）
    - 仅以 periodType + periodValue(周几) 判断是否已存在，与金额无关

    Args:
        user: 用户对象
        fund_code: 基金代码
        sleep_sec: 每次详情查询之间的节流时间（秒）

    Returns:
        Dict[int, FundPlan]: 按周几映射已有的周定投计划
    """
    plans = getFundPlanList(fund_code, user)
    logger.info(f"基金 {fund_code} 计划列表数量: {len(plans)}")

    day_map: Dict[int, FundPlan] = {}
    for idx, plan in enumerate(plans, start=1):
        try:
            detail_resp = getPlanDetailPro(plan.planId, user)
            if not getattr(detail_resp, "Success", False) or detail_resp.Data is None:
                logger.warning(f"[{idx}/{len(plans)}] 计划 {plan.planId} 详情获取失败或为空，跳过")
                continue

            detail: FundPlanDetail = detail_resp.Data
            rp: FundPlan = detail.rationPlan

            # 周定投 periodType == 1
            if rp.periodType == 1:
                weekday = int(rp.periodValue or 0)
                if weekday <= 0:
                    logger.warning(f"[{idx}/{len(plans)}] 计划 {rp.planId} 的周几无效({rp.periodValue})，跳过")
                else:
                    # 保存详情版 FundPlan（包含 planAssets、profitRate 等）
                    day_map[weekday] = rp
            else:
                # 非周定投，忽略
                pass
        except Exception as e:
            logger.error(f"[{idx}/{len(plans)}] 获取详情异常，计划ID={plan.planId}，原因: {str(e)}")
        finally:
            time.sleep(sleep_sec)

    # 打印已存在的周定投（升序）
    if day_map:
        logger.info(f"基金 {fund_code} 已存在的周定投周几: {sorted(day_map.keys())}")
        for weekday in sorted(day_map.keys()):
            rp = day_map[weekday]
            asset = rp.planAssets
            profit_rate = rp.rationProfitRate if rp.rationProfitRate is not None else rp.totalProfitRate
            profit_rate_str = f"{float(profit_rate) * 100:.2f}%" if profit_rate is not None else "未知"
            logger.info(
                f"  每周{weekday} -> 计划ID: {rp.planId}, 金额: {rp.amount:.2f}, "
                f"子账户: {rp.subAccountName}, 计划资产: {asset:.2f}, 盈亏率: {profit_rate_str}"
            )
    else:
        logger.info(f"基金 {fund_code} 未查询到周定投计划")

    return day_map


def dissolve_weekly_plans_for_fund(
    user: User,
    fund_code: str,
    target_days: Optional[Set[int]] = None,
    sub_account_name: Optional[str] = None,
    dry_run: bool = False,
    sleep_sec: float = 0.15
) -> Dict[str, List[str]]:
    """
    批量解散某基金的周定投计划（仅资产“为0.0或者为空”的计划会解散）。

    条件:
    - 仅处理 periodType == 1 的“周定投”
    - 若指定了 target_days，仅处理这些周几
    - 若指定了 sub_account_name，仅处理该子账户下的计划
    - 解散条件：asset is None 或 asset == 0.0（“0.0 或者为空”的解散）
    """
    result = {
        "dissolved_ids": [],
        "skipped_ids": [],
        "failed_ids": [],
    }

    day_map = get_existing_weekly_day_map(user, fund_code, sleep_sec=sleep_sec)
    if not day_map:
        logger.info(f"基金 {fund_code} 无可处理的周定投计划")
        return result

    days = sorted(day_map.keys()) if not target_days else sorted(d for d in day_map.keys() if d in target_days)
    logger.info(f"准备处理基金 {fund_code} 的周几: {days if days else '无匹配周几'}")

    for weekday in days:
        rp = day_map[weekday]
        plan_id = rp.planId
        asset = rp.planAssets

        # 子账户过滤
        if sub_account_name and rp.subAccountName != sub_account_name:
            logger.info(f"计划 {plan_id} 每周{weekday} 子账户不匹配({rp.subAccountName} != {sub_account_name})，跳过")
            result["skipped_ids"].append(plan_id)
            continue

        # 解散条件：资产为空(None) 或 资产等于 0.0
        should_dissolve = (asset is None) or (float(asset) == 0.0)

        if not should_dissolve:
            logger.info(f"计划 {plan_id} 每周{weekday} 资产不为0.0，按规则跳过解散")
            result["skipped_ids"].append(plan_id)
            continue

        # dry-run 仅预览
        if dry_run:
            logger.info(f"[DRY-RUN] 计划 {plan_id} 每周{weekday} 将要解散（资产={asset}，子账户={rp.subAccountName}）")
            result["dissolved_ids"].append(plan_id)
            continue

        # 执行解散
        try:
            logger.info(f"正在解散计划 {plan_id} 每周{weekday}（资产={asset}，子账户={rp.subAccountName}）")
            op_resp = operateRation(user, plan_id=plan_id, operation="2")
            if getattr(op_resp, "Success", False):
                logger.info(f"✓ 成功解散 计划ID={plan_id} 每周{weekday}")
                result["dissolved_ids"].append(plan_id)
            else:
                logger.warning(f"✗ 解散失败 计划ID={plan_id} 每周{weekday}，错误：{getattr(op_resp, 'FirstError', None)}")
                result["failed_ids"].append(plan_id)
        except Exception as e:
            logger.error(f"✗ 解散异常 计划ID={plan_id} 每周{weekday}，原因: {str(e)}")
            result["failed_ids"].append(plan_id)
        finally:
            time.sleep(sleep_sec)

    # 结果摘要
    logger.info("=== 批量周定投解散结果 ===")
    logger.info(f"基金 {fund_code} 需处理: {len(days)}")
    logger.info(f"已解散: {len(result['dissolved_ids'])}")
    logger.info(f"跳过: {len(result['skipped_ids'])}")
    logger.info(f"失败: {len(result['failed_ids'])}")
    return result


if __name__ == "__main__":
    # 示例：解散基金 001595 的周定投（解散“资产不为0或者为空”的计划）
    summary = dissolve_weekly_plans_for_fund(
        user=DEFAULT_USER,
        fund_code="002112",
        target_days=None,          # 传 {1,2,3,4,5} 可限定周几
        sub_account_name=None,     # 传入组合名称可限定子账户
        dry_run=False,             # True 仅预览，不执行
        sleep_sec=0.15
    )
    logger.info(summary)