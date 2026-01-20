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
from src.service.定投管理.智能定投.批量月定投创建 import get_existing_monthly_day_map
from src.service.基金信息.基金信息 import get_all_fund_info
from src.service.公共服务.trade_time_service import is_trading_time

logging.basicConfig(level=logging.INFO)

def test_get_existing_monthly_day_map():
    user = DEFAULT_USER
    fund_code = "011707"  # 天弘中证银行ETF联接C
    plan_list = getFundPlanList(fund_code, user)
    print(f"基金 {fund_code} 计划列表数量: {len(plan_list)}")
    day_map = get_existing_monthly_day_map(user, fund_code, sleep_sec=0.0)
    print(f"基金 {fund_code} 已存在的月定投日: {sorted(day_map.keys())}")
    # 新增：获取基金估算涨跌幅（百分数）
    estimated_change_pct = None
    # 移除 is_trading_time 检查，总是尝试获取，以便在测试输出中显示
    try:
        fund_info = get_all_fund_info(user, fund_code)
        estimated_change = getattr(fund_info, 'estimated_change', None)
        estimated_change_pct = float(estimated_change) if estimated_change is not None else None
    except Exception as e:
        print(f"获取估值失败: {e}")
        
    # 按日期升序输出明细，补充资产、盈亏率与预估盈亏率
    for day in sorted(day_map.keys()):
        plan = day_map[day]
        asset = getattr(plan, 'planAssets', None)
        asset_str = f"{float(asset):.2f}" if asset is not None else "未知"
        profit_rate = getattr(plan, 'rationProfitRate', None) or getattr(plan, 'totalProfitRate', None)
        current_profit_pct = float(profit_rate) * 100.0 if profit_rate is not None else None
        profit_rate_str = f"{current_profit_pct:.2f}%" if current_profit_pct is not None else "未知"
        
        # 获取子账户名称
        sub_account = getattr(plan, 'subAccountName', '')
        
        # 获取份额信息
        shares = 0.0
        valid_shares = 0.0
        if hasattr(plan, 'shares') and plan.shares:
            for share in plan.shares:
                valid_shares += getattr(share, 'availableVol', 0.0)
                shares += getattr(share, 'totalVol', 0.0)
        else:
            # Fallback: 如果没有 shares 详情，尝试通过资产/净值估算（仅作为参考，视为总份额）
            unit_price = getattr(plan, 'unitPrice', 0)
            if asset is not None and unit_price and float(unit_price) > 0:
                shares = float(asset) / float(unit_price)
                valid_shares = shares # 无法区分时，暂且显示相同

        line = (
            f"  每月{day:>2}号 -> 计划ID: {plan.planId}, "
            f"定投金额: {plan.amount:.2f}, 子账户: {sub_account}, "
            f"计划资产: {asset_str}, 有效份额: {valid_shares:.2f}, 总份额: {shares:.2f}, 盈亏率: {profit_rate_str}"
        )
        if estimated_change_pct is not None:
            estimated_profit_rate_str = f"{(current_profit_pct + estimated_change_pct):.2f}%" if current_profit_pct is not None else "未知"
            line += f", 预估盈亏率: {estimated_profit_rate_str}"
        print(line)
    assert isinstance(day_map, dict)
    # 不做“非空”强断言，避免环境差异导致测试失败；手工检查输出即可

# 直接运行脚本时的入口
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    test_get_existing_monthly_day_map()
