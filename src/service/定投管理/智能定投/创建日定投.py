import os
import sys

# 将项目根目录加入 sys.path，解决直接运行时无法找到 src 包
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import logging
from typing import Optional, Union, List

from src.domain.user.User import User
from src.domain.fund_plan import ApiResponse, FundPlan
from src.API.定投计划管理.SmartPlan import (
    getFundPlanList,
    getPlanDetailPro,
    createPlanV3,
)
from src.common.constant import DEFAULT_USER


logger = logging.getLogger("CreateDailyRation")
logger.setLevel(logging.INFO)


def find_existing_daily_plans(user: User, fund_code: str) -> List[FundPlan]:
    """
    查询指定基金是否已存在“日定投”计划（periodType == 4）
    """
    plans = getFundPlanList(fund_code, user) or []
    daily_plans: List[FundPlan] = []

    for plan in plans:
        # 先快速判断（列表里通常已带 periodType），尽量减少详情查询次数
        if plan.periodType == 4:
            daily_plans.append(plan)
            continue

        # 兜底：如果列表未正常带出周期类型，则查询详情再判断
        try:
            detail_resp = getPlanDetailPro(plan.planId, user)
            if getattr(detail_resp, "Success", False) and detail_resp.Data:
                detail = detail_resp.Data
                period_type = getattr(detail, "periodType", None)
                # 有的实现 periodType 在 detail.rationPlan 上
                if period_type is None and getattr(detail, "rationPlan", None):
                    period_type = getattr(detail.rationPlan, "periodType", None)
                if period_type == 4:
                    daily_plans.append(plan)
        except Exception as e:
            logger.warning(f"获取计划详情失败: {plan.planId} - {e}")

    return daily_plans


def create_daily_smart_investment(
    user: User,
    fund_code: str,
    amount: Union[int, float, str],
    period_value: int = 1,
    sub_account_name: Optional[str] = None,
    allow_duplicate: bool = False,
) -> ApiResponse[FundPlan]:
    """
    给指定基金创建“日定投”。
    - 默认避免重复创建（allow_duplicate=False 时若存在则直接返回错误码）
    - period_type 固定为 4（按日），period_value 默认为 1（每天）
    - 可选 sub_account_name 指定子账户创建

    Returns:
        ApiResponse[FundPlan]
    """
    # 查重复：是否已存在日定投
    existing_daily = find_existing_daily_plans(user, fund_code)
    if existing_daily and not allow_duplicate:
        logger.info(f"基金 {fund_code} 已存在日定投计划数: {len(existing_daily)}，跳过创建")
        # 返回一个失败响应，表达“已存在”
        return ApiResponse(
            Success=False,
            ErrorCode="ALREADY_EXISTS",
            Data=None,
            FirstError="该基金已存在日定投计划，未执行重复创建",
            DebugError=None,
        )

    # 规范化金额为字符串（createPlanV3 使用字符串金额）
    amount_str = str(amount)

    # 直接复用 createPlanV3（其内部已做限额检查与自动调整）
    resp = createPlanV3(
        user=user,
        fund_code=fund_code,
        amount=amount_str,
        period_type=4,
        period_value=str(period_value),
        sub_account_name=sub_account_name,
        strategy_type=0,  # 目标止盈策略（与 Metersphere 场景一致）
    )

    if getattr(resp, "Success", False) and resp.Data:
        plan = resp.Data
        logger.info(
            f"创建成功: 计划ID={plan.planId}, 基金={plan.fundCode}-{plan.fundName}, "
            f"金额={plan.amount}, 周期={plan.periodType}({plan.periodValue}), 子账户={plan.subAccountName or ''}"
        )
    else:
        logger.error(f"创建失败: ErrorCode={getattr(resp, 'ErrorCode', '')}, FirstError={getattr(resp, 'FirstError', '')}")

    return resp


if __name__ == "__main__":
    # 控制台日志输出
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        logger.addHandler(console_handler)

    # 示例调用：按需替换 fund_code/amount/sub_account_name
    result = create_daily_smart_investment(
        user=DEFAULT_USER,
        fund_code="001595",
        amount=200.0,
        period_value=1,
        sub_account_name=None,
        allow_duplicate=False
    )

    # 打印结果摘要
    print(f"Success={getattr(result, 'Success', False)}, ErrorCode={getattr(result, 'ErrorCode', '')}, FirstError={getattr(result, 'FirstError', '')}")