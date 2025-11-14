import os
import sys
import time
import logging
from typing import Dict, List, Optional, Set

# 将项目根目录加入 sys.path，支持直接运行此脚本
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.common.logger import get_logger
from src.domain.user.User import User
from src.common.constant import DEFAULT_USER
from src.API.定投计划管理.SmartPlan import getFundPlanList, getPlanDetailPro, operateRation
from src.domain.fund_plan.fund_plan import FundPlan
from src.domain.fund_plan.fund_plan_detail import FundPlanDetail

logger = get_logger("BatchMonthlyDissolve")


def get_existing_monthly_day_map(user: User, fund_code: str, sleep_sec: float = 0.15) -> Dict[int, FundPlan]:
    """
    查询指定基金现有的“月定投”计划映射（day -> FundPlan），需要逐个拉取详情判断 periodType/periodValue。

    Args:
        user: 用户对象
        fund_code: 基金代码
        sleep_sec: 每次详情查询之间的节流时间（秒）

    Returns:
        Dict[int, FundPlan]: 按月定投日映射已有计划
    """
    plans = getFundPlanList(fund_code, user)
    logger.info(f"基金 {fund_code} 计划列表数量: {len(plans)}")

    day_map: Dict[int, FundPlan] = {}
    for idx, plan in enumerate(plans, start=1):
        try:
            # 拉详情以获取 periodType/periodValue/planAssets 等关键字段
            detail_resp = getPlanDetailPro(plan.planId, user)
            if not getattr(detail_resp, "Success", False) or detail_resp.Data is None:
                logger.warning(f"[{idx}/{len(plans)}] 计划 {plan.planId} 详情获取失败或为空，跳过")
                continue

            detail: FundPlanDetail = detail_resp.Data
            rp: FundPlan = detail.rationPlan

            # 月定投 periodType == 3
            if rp.periodType == 3:
                day = int(rp.periodValue or 0)
                if day <= 0:
                    logger.warning(f"[{idx}/{len(plans)}] 计划 {rp.planId} 的月定投日无效({rp.periodValue})，跳过")
                else:
                    # 保存详情版 FundPlan（包含 planAssets、profitRate 等）
                    day_map[day] = rp
            else:
                # 非月定投，忽略
                pass
        except Exception as e:
            logger.error(f"[{idx}/{len(plans)}] 获取详情异常，计划ID={plan.planId}，原因: {str(e)}")
        finally:
            time.sleep(sleep_sec)

    # 打印已存在的月定投日（升序）
    if day_map:
        logger.info(f"基金 {fund_code} 已存在的月定投日: {sorted(day_map.keys())}")
        for day in sorted(day_map.keys()):
            rp = day_map[day]
            asset = rp.planAssets
            profit_rate = rp.rationProfitRate if rp.rationProfitRate is not None else rp.totalProfitRate
            profit_rate_str = f"{float(profit_rate) * 100:.2f}%" if profit_rate is not None else "未知"
            logger.info(
                f"  每月{day:>2}号 -> 计划ID: {rp.planId}, 金额: {rp.amount:.2f}, "
                f"子账户: {rp.subAccountName}, 计划资产: {asset:.2f}, 盈亏率: {profit_rate_str}"
            )
    else:
        logger.info(f"基金 {fund_code} 未查询到月定投计划")

    return day_map


def dissolve_monthly_plans_for_fund(
    user: User,
    fund_code: str,
    target_days: Optional[Set[int]] = None,
    sub_account_name: Optional[str] = None,
    dry_run: bool = False,
    allow_nonzero_assets: bool = False,
    sleep_sec: float = 0.15
) -> Dict[str, List[str]]:
    """
    批量解散某基金的月定投计划（满足条件才解散）。

    条件（默认严格）:
    - 仅处理 periodType == 3 的“月定投”
    - 若指定了 target_days，仅处理这些日期
    - 若指定了 sub_account_name，仅处理该子账户下的计划
    - 默认仅在计划资产为空或为0时解散（资产>0则跳过）。如需强制解散，设置 allow_nonzero_assets=True

    Args:
        user: 用户对象
        fund_code: 基金代码
        target_days: 目标日期集合（如 {1,2,3}），None 表示所有已存在的月定投日
        sub_account_name: 限定子账户名称
        dry_run: 仅预览，不执行解散
        allow_nonzero_assets: 允许资产>0也解散（默认 False，推荐保持 False）
        sleep_sec: 每次操作之间的节流时间（秒）

    Returns:
        Dict[str, List[str]]: 结果统计，包含 dissolved_ids、skipped_ids、failed_ids 等列表
    """
    result = {
        "dissolved_ids": [],
        "skipped_ids": [],
        "failed_ids": [],
    }

    day_map = get_existing_monthly_day_map(user, fund_code, sleep_sec=sleep_sec)
    if not day_map:
        logger.info(f"基金 {fund_code} 无可处理的月定投计划")
        return result

    days = sorted(day_map.keys()) if not target_days else sorted(d for d in day_map.keys() if d in target_days)
    logger.info(f"准备处理基金 {fund_code} 的月定投日: {days if days else '无匹配日期'}")

    for day in days:
        rp = day_map[day]
        plan_id = rp.planId
        asset = rp.planAssets

        # 子账户过滤
        if sub_account_name and rp.subAccountName != sub_account_name:
            logger.info(f"计划 {plan_id} 每月{day}号 子账户不匹配({rp.subAccountName} != {sub_account_name})，跳过")
            result["skipped_ids"].append(plan_id)
            continue

        # 资产条件：默认仅资产为空或0时才解散
        if not allow_nonzero_assets and (asset is not None and asset != 0.0):
            logger.info(f"计划 {plan_id} 每月{day}号 资产不为空({asset})，跳过解散")
            result["skipped_ids"].append(plan_id)
            continue

        # dry-run 仅预览
        if dry_run:
            logger.info(f"[DRY-RUN] 计划 {plan_id} 每月{day}号 将要解散（资产={asset}，子账户={rp.subAccountName}）")
            result["dissolved_ids"].append(plan_id)
            continue

        # 执行解散
        try:
            logger.info(f"正在解散计划 {plan_id} 每月{day}号（资产={asset}，子账户={rp.subAccountName}）")
            op_resp = operateRation(user, plan_id=plan_id, operation="2")
            # 成功标识使用 ApiResponse.Success
            if getattr(op_resp, "Success", False):
                logger.info(f"✓ 成功解散 计划ID={plan_id} 每月{day}号")
                result["dissolved_ids"].append(plan_id)
            else:
                logger.warning(f"✗ 解散失败 计划ID={plan_id} 每月{day}号，错误：{getattr(op_resp, 'FirstError', None)}")
                result["failed_ids"].append(plan_id)
        except Exception as e:
            logger.error(f"✗ 解散异常 计划ID={plan_id} 每月{day}号，原因: {str(e)}")
            result["failed_ids"].append(plan_id)
        finally:
            time.sleep(sleep_sec)

    # 结果摘要
    logger.info("=== 批量月定投解散结果 ===")
    logger.info(f"基金 {fund_code} 需处理: {len(days)}")
    logger.info(f"已解散: {len(result['dissolved_ids'])}")
    logger.info(f"跳过: {len(result['skipped_ids'])}")
    logger.info(f"失败: {len(result['failed_ids'])}")
    return result


if __name__ == "__main__":
    # 示例：解散基金 001595 的所有月定投（仅资产为空或0），不限定子账户
    summary = dissolve_monthly_plans_for_fund(
        user=DEFAULT_USER,
        fund_code="021740",
        target_days=None,          # 传 {1,2,3} 可限定日期
        sub_account_name=None,     # 传入组合名称可限定子账户
        dry_run=False,             # True 仅预览，不执行
        allow_nonzero_assets=False, # False 表示资产>0不解散
        sleep_sec=0.15
    )
    logger.info(summary)
