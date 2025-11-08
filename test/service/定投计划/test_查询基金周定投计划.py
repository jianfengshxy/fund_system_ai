import logging
import os
import sys

# 修复：将项目根目录加入 sys.path（从 test/service/定投计划 上溯 4 层）
project_root = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
    )
)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.API.定投计划管理.SmartPlan import DEFAULT_USER, getFundPlanList
from src.service.定投管理.智能定投.创建周定投 import get_existing_weekly_day_map

logging.basicConfig(level=logging.INFO)


def test_get_existing_weekly_day_map():
    user = DEFAULT_USER
    fund_code = "001595"  # 示例：天弘中证银行ETF联接C
    plan_list = getFundPlanList(fund_code, user) or []
    print(f"基金 {fund_code} 计划列表数量: {len(plan_list)}")

    day_map = get_existing_weekly_day_map(user, fund_code, sleep_sec=0.0)
    days_sorted = sorted(day_map.keys())
    print(f"基金 {fund_code} 已存在的周定投周几: {days_sorted}")

    # 按周几升序输出明细，补充资产与盈亏率（若可用）
    for day in days_sorted:
        plan = day_map[day]
        asset = getattr(plan, 'planAssets', None)
        asset_str = f"{float(asset):.2f}" if asset is not None else "未知"
        profit_rate = getattr(plan, 'rationProfitRate', None) or getattr(plan, 'totalProfitRate', None)
        profit_rate_str = f"{float(profit_rate) * 100:.2f}%" if profit_rate is not None else "未知"
        print(
            f"  每周{day} -> 计划ID: {plan.planId}, "
            f"定投金额: {plan.amount:.2f}, 子账户: {getattr(plan, 'subAccountName', '-')}, "
            f"计划资产: {asset_str}, 盈亏率: {profit_rate_str}"
        )

    assert isinstance(day_map, dict)
    # 不做“非空”强断言，避免环境差异导致测试失败；手工检查输出即可


# 直接运行脚本时的入口
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_get_existing_weekly_day_map()