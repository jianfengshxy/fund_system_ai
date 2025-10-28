# 顶部导入片段
import logging
import os
import sys
from typing import Optional

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.domain.user.User import User
from src.service.基金信息.基金信息 import get_all_fund_info
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.service.资产管理.get_fund_asset_detail import (
    get_sub_account_asset_by_name,
    get_fund_asset_detail,
)
from src.service.交易管理.购买基金 import commit_order
from src.common.constant import DEFAULT_USER
from src.service.交易管理.交易查询 import count_success_trades_on_prev_nav_day
from src.service.公共服务.nav_gate_service import nav5_gate

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def increase_funds(user: User, sub_account_name: str, fund_list: Optional[list] = None) -> bool:
    """自定义组合算法加仓：仅针对组合中已持有的基金执行加仓。
    从 payload 传入的 fund_list 获取基金代码与金额；未持有基金在此逻辑中跳过。
    """
    customer_name = user.customer_name
    logger.info(f"开始为用户 {customer_name} 执行加仓操作，组合: {sub_account_name}")

    # 获取组合账号
    sub_account_no = getSubAccountNoByName(user, sub_account_name)
    if not sub_account_no:
        logger.error(f"未找到组合 {sub_account_name} 的账号")
        return False

    # 校验 payload 的基金列表
    if not fund_list or not isinstance(fund_list, list):
        logger.info(f"未提供 fund_list 或格式不正确，跳过自定义组合加仓")
        return False

    # 获取组合资产，构建已持有基金集合
    asset_details = get_sub_account_asset_by_name(user, sub_account_name) or []
    held_codes = {getattr(a, 'fund_code', '') for a in asset_details if getattr(a, 'fund_code', None)}
    logger.info(f"组合 {sub_account_name} 当前持有基金数: {len(held_codes)}")

    # 辅助：安全数值转换与 5 日均值门槛（无估值时用上一交易日净值）
    def _safe_float(v, default=0.0):
        try:
            if v is None:
                return default
            return float(v)
        except Exception:
            return default

    success_count = 0

    for fund_item in fund_list:
        try:
            fund_code = (fund_item or {}).get('fund_code')
            fund_amount = (fund_item or {}).get('amount')
            if not fund_code:
                logger.info("fund_code 缺失，跳过该条目")
                continue
            if not fund_amount or float(fund_amount) <= 0:
                logger.info(f"基金 {fund_code} 的 amount 缺失或无效，跳过该基金")
                continue

            fund_info = get_all_fund_info(user, fund_code)
            fund_name = getattr(fund_info, 'fund_name', fund_code)
            logger.info(f"基金信息：{fund_name}({fund_code})，可申购：{getattr(fund_info, 'can_purchase', None)}")

            # 仅对已持有基金执行加仓
            if fund_code in held_codes:
                try:
                    asset = get_fund_asset_detail(user, sub_account_no, fund_code)
                    if asset is None:
                        logger.info(f"组合{sub_account_no}的{fund_name}{fund_code}资产为空。Skip .........")
                        continue
                except Exception as e:
                    logger.error(f"获取资产详情失败: {e}")
                    continue
                # 使用“昨日净值日(nav_date)+今天”的守卫：任一天存在非撤的买入/定投则跳过
                from src.service.公共服务.trade_guard_service import has_buy_submission_on_dates
                import datetime
                nav_date_str = getattr(fund_info, "nav_date", None)
                try:
                    prev_trade_day = datetime.datetime.strptime(nav_date_str, "%Y-%m-%d").date() if nav_date_str else None
                except Exception:
                    prev_trade_day = None
                today = datetime.date.today()
                prev_trade_pre = has_buy_submission_on_dates(user, sub_account_no, fund_code, {d for d in [prev_trade_day] if d})
                today_trade_pre = has_buy_submission_on_dates(user, sub_account_no, fund_code, {today})
                if prev_trade_pre is not None or today_trade_pre is not None:
                    logger.info(f"跳过 {fund_name}({fund_code}): 昨日(nav_date)或今日存在买入/定投提交（非撤）")
                    continue

                current_profit_rate = _safe_float(getattr(asset, 'constant_profit_rate', None), 0.0)
                estimated_change = _safe_float(getattr(fund_info, 'estimated_change', None), 0.0)
                estimated_profit_rate = current_profit_rate + estimated_change
                safe_asset_value = _safe_float(getattr(asset, "asset_value", 0.0), 0.0)
                times = round(safe_asset_value / float(fund_amount), 2)
                if times < 0.98 and times > 0.0:
                    logger.info(f"组合{sub_account_no}，基金{fund_name}({fund_code})资产{safe_asset_value:.2f}，当前资产倍数{times},满足加仓条件。")
                    res0 = commit_order(user, sub_account_no, fund_code, float(fund_amount))
                    if res0 and getattr(res0, 'busin_serial_no', None):
                        success_count += 1
                        actual_amount = getattr(res0, 'amount', fund_amount)
                        logger.info(
                            f"限购加仓成功: {fund_name}({fund_code}) - 金额: {actual_amount} - 订单号: {getattr(res0, 'busin_serial_no', '')}"
                        )
                    else:
                        logger.info(f"限购加仓失败{fund_name}({fund_code})")
                    continue
                
                # 提前进行五日均值过滤（候选阶段）
                if not nav5_gate(fund_info, fund_name, fund_code, logger):
                    logger.info(f"未处于上升趋势（估算净值≤5日均值），跳过候选加仓：{fund_name}({fund_code})")
                    continue

                # 回撤不足直接跳过（阈值：-1%）
                if estimated_profit_rate >= -1.0:
                    logger.info(
                        f"跳过 {fund_name}({fund_code}): 回撤不达标 estimated_profit_rate={estimated_profit_rate:.2f}% ，阈值<-1.00%"
                    )
                    continue

                # 原先此处的净值门槛判断已提前到候选阶段，这里不再重复

                r100 = _safe_float(getattr(fund_info, 'rank_100day', None), 0.0)
                r30 = _safe_float(getattr(fund_info, 'rank_30day', None), 0.0)
                if r100 and r100 < 20:
                    logger.info(f"100日排名过低 - {fund_name} rank_100 {int(r100)} < 20, 跳过加仓")
                    continue
                if r100 and r100 > 90:
                    logger.info(f"100日排名过高 - {fund_name} rank_100 {int(r100)} > 90, 跳过加仓")
                    continue
                if r30 and r30 < 5:
                    logger.info(f"30日排名过低 - {fund_name} rank_30 {int(r30)} < 5, 跳过加仓")
                    continue

                week_growth_rate = _safe_float(getattr(fund_info, 'week_return', None), 0.0)
                month_growth_rate = _safe_float(getattr(fund_info, 'month_return', None), 0.0)
                season_growth_rate = _safe_float(getattr(fund_info, 'three_month_return', None), 0.0)
                logger.info(
                    f"收益率数据 - {fund_name}周收益率预估:{week_growth_rate},月收益率预估:{month_growth_rate},季度收益率预估:{season_growth_rate}"
                )

                if week_growth_rate < 0.0 and month_growth_rate < 0.0 and season_growth_rate < 0.0:
                    logger.info("全部收益率为负 - 周、月、季度收益率均为负数，跳过加仓")
                    continue

                if season_growth_rate < 0.0 and (month_growth_rate < 0.0 or week_growth_rate < 0.0):
                    logger.info("季度收益率为负且月/周收益率至少一个为负 - 跳过加仓")
                    continue

                if season_growth_rate > 0.0 and (month_growth_rate < 0.0 and week_growth_rate < 0.0):
                    logger.info("季度为正但月、周均为负 - 跳过加仓")
                    continue

                # 方法: increase_funds
                # 修复基础加仓与额外加仓成功判断
                try:
                    res1 = commit_order(user, sub_account_no, fund_code, float(fund_amount))
                    if res1 and getattr(res1, 'busin_serial_no', None):
                        success_count += 1
                        actual_amount = getattr(res1, 'amount', fund_amount)
                        logger.info(
                            f"基础加仓成功: {fund_name}({fund_code}) - 金额: {actual_amount} - 订单号: {getattr(res1, 'busin_serial_no', '')}"
                        )
                    else:
                        logger.info(f"基础加仓未成功或被系统保护跳过：{fund_name}({fund_code})")

                    if estimated_profit_rate < -5.0:
                        res2 = commit_order(user, sub_account_no, fund_code, float(fund_amount))
                        if res2 and getattr(res2, 'busin_serial_no', None):
                            success_count += 1
                            actual_amount = getattr(res2, 'amount', fund_amount)
                            logger.info(
                                f"额外加仓成功(-5%): {fund_name}({fund_code}) - 金额: {actual_amount} - 订单号: {getattr(res2, 'busin_serial_no', '')}"
                            )
                        else:
                            logger.info(f"额外加仓未成功或被系统保护跳过：{fund_name}({fund_code})")
                except Exception as e:
                    logger.error(f"加仓失败：{fund_name}({fund_code})，异常: {e}")
            else:
                logger.info(f"未持有基金，当前文件逻辑跳过：{fund_name}({fund_code})；请在新增文件中处理该基金的购买")
        except Exception as e:
            logger.error(f"处理 {fund_item} 失败: {e}")

    logger.info(f"加仓完成：{customer_name} 成功执行 {success_count} 次加仓购买")
    return success_count > 0


if __name__ == "__main__":
    try:
        increase_funds(
            DEFAULT_USER,
            "海外基金组合",
            fund_list=[
                # {"fund_code": "016702", "fund_name": "银华海外数字经济量化选股混合发起式(QDII)C", "amount": 5000.0},
                # {"fund_code": "006105", "fund_name": "宏利印度股票(QDII)", "amount": 5000.0},
                # {"fund_code": "161226", "fund_name": "国投瑞银白银期货(LOF)A", "amount": 5000.0},
                # {"fund_code": "017873", "fund_name": "汇添富香港优势精选混合(QDII)C", "amount": 5000.0},
                {"fund_code": "100055", "fund_name": "富国全球科技互联网股票(QDII)A", "amount": 5000.0}
            ]
        )
        logging.info(f"用户 {DEFAULT_USER.customer_name} 加仓操作完成")
    except Exception as e:
        logging.error(f"测试用户处理失败：{str(e)}")