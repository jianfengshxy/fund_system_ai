import pytest
import os
import sys
import logging
import datetime

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.service.公共服务.trade_guard_service import has_buy_submission_on_dates
from src.service.用户管理.用户信息 import get_user_all_info
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.service.基金信息.基金信息 import get_all_fund_info
from src.service.加仓风向标组合算法.加仓风向标加仓 import increase_funds

# 日志配置与风格保持一致
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)d)')
logger = logging.getLogger(__name__)

def _desc_trade(t):
    if not t:
        return "无交易"
    state = getattr(t, "app_state_text", None) or getattr(t, "status", None)
    serial = getattr(t, "busin_serial_no", None) or getattr(t, "id", None)
    strike_date = getattr(t, "strike_start_date", None) or getattr(t, "apply_work_day", None)
    display = getattr(t, "display_business_code", None) or getattr(t, "business_type", None)
    amount = getattr(t, "amount", None)
    product_name = getattr(t, "product_name", None) or getattr(t, "fund_name", None)
    return f"交易存在: 基金={product_name}, 状态={state}, 业务={display}, 金额={amount}, 日期={strike_date}, 单号={serial}"

def test_has_buy_submission_on_prev_nav_and_today():
    """验证“最优止盈”组合里 招商中证白酒指数(LOF)A(161725) 今天与上一个交易日是否有买入/定投（排除撤单）"""
    logger.info("开始测试：基金161725在上一个交易日(nav_date)与今天是否存在买入/定投提交记录（排除撤单）")

    # 登录指定用户
    user = get_user_all_info("13500819290","guojing1985")
    assert user is not None, "登录失败，user为None"

    sub_account_name = "最优止盈"
    sub_account_no = getSubAccountNoByName(user, sub_account_name)
    assert sub_account_no, f"获取子账户编号失败: {sub_account_name}"

    fund_code = "161725"
    fi = get_all_fund_info(user, fund_code)
    assert fi is not None, f"获取基金信息失败: {fund_code}"

    nav_date_str = getattr(fi, "nav_date", None)
    try:
        prev_trade_day = datetime.datetime.strptime(nav_date_str, "%Y-%m-%d").date() if nav_date_str else None
    except Exception:
        prev_trade_day = None
    today = datetime.date.today()

    logger.info(f"基金 {fi.fund_name}({fund_code}) nav_date={nav_date_str or '未知'}, 今天={today.isoformat()}")

    # 加仓前检查
    prev_trade_pre = has_buy_submission_on_dates(user, sub_account_no, fund_code, {d for d in [prev_trade_day] if d})
    today_trade_pre = has_buy_submission_on_dates(user, sub_account_no, fund_code, {today})
    logger.info(f"[加仓前] 上一个交易日: {_desc_trade(prev_trade_pre)}")
    logger.info(f"[加仓前] 今天: {_desc_trade(today_trade_pre)}")

    # 断言：两天都存在交易（符合你给出的实际记录）
    assert prev_trade_pre is not None, "上一个交易日(nav_date)应存在买入/定投提交记录（非撤）"
    assert today_trade_pre is not None, "今天应存在买入/定投提交记录（非撤）"




if __name__ == "__main__":
    logger.info("直接运行公共服务守卫测试")
    test_has_buy_submission_on_prev_nav_and_today()