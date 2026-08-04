import os
import sys
import datetime
from typing import Optional

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.domain.user.User import User
from src.service.基金信息.基金信息 import get_all_fund_info
from src.API.交易管理.trade import get_bank_shares
from src.service.交易管理.赎回基金 import (
    sell_0_fee_shares,
    sell_low_fee_shares,
    sell_usable_non_zero_fee_shares,
)
from src.service.资产管理.get_fund_asset_detail import (
    get_sub_account_asset_by_name,
    get_fund_asset_detail
)
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.API.资产管理.AssetManager import GetMyAssetMainPartAsync
from src.API.资产管理.getAssetListOfSub import get_asset_list_of_sub
from src.service.定投管理.定投查询.定投查询 import get_all_fund_plan_details
from src.service.公共服务.risk_control_service import check_hqb_risk_allowed
from src.common.constant import DEFAULT_USER, HQB_RATIO_THRESHOLD, PROFIT_THRESHOLD_FOR_LOW_BALANCE
from src.service.公共服务.nav_gate_service import nav5_fall_gate
from src.common.logger import get_logger
from src.service.公共服务.estimated_profit_service import calc_estimated_change, calc_estimated_profit_rate
from src.service.公共服务.trade_guard_service import has_buy_submission_on_dates

logger = get_logger(__name__)


def redeem_funds(user: User, sub_account_name: str, fund_list: Optional[list] = None) -> bool:
    """自定义组合算法止盈：从 payload 传入的 fund_list 获取要交易的基金及其金额，
    不依赖定投计划；止盈逻辑与 bussiness 层保持一致。
    """
    customer_name = user.customer_name
    logger.info(f"开始为用户 {customer_name} 执行止盈操作，组合: {sub_account_name}")

    # 获取组合账号
    sub_account_no = getSubAccountNoByName(user, sub_account_name)
    if not sub_account_no:
        logger.error(f"未找到组合 {sub_account_name} 的账号")
        return False

    success_count = 0

    assets = get_asset_list_of_sub(user, sub_account_no)
    for asset in assets:
        try:
            fund_code = asset.fund_code

            fund_info = get_all_fund_info(user, fund_code)
            fund_name = fund_info.fund_name
            logger.info(f"基金信息：{fund_name}({fund_code})，可申购：{fund_info.can_purchase}，可赎回：{fund_info.can_redeem}")

            shares = get_bank_shares(user, sub_account_no, fund_code)

            # 资产详情（复制业务层字段与日志）
            try:
                asset_detail = get_fund_asset_detail(user, sub_account_no, fund_code)
                if asset_detail is not None:
                    plan_assets = asset_detail.asset_value
                    fund_type = fund_info.fund_type
                    constant_profit_rate = asset_detail.constant_profit_rate
                    logger.info(
                        f"{fund_name}资产详情获取成功 - 资产价值: {asset_detail.asset_value}, 基金类型:{fund_type},收益率: {constant_profit_rate}%, 估值增长率: {fund_info.estimated_change}%, 在途交易数: {asset_detail.on_way_transaction_count}"
                    )
                else:
                    logger.info(f"组合{sub_account_no}的{fund_name}{fund_code}资产为空。Skip .........")
                    continue
            except Exception as e:
                logger.error(f"获取资产详情失败: {e}")
                continue

            try:
                # 尝试从传入的 fund_list 中获取单次投资金额
                fund_amount = 0.0
                if fund_list:
                    for item in fund_list:
                        if item.get("fund_code") == fund_code:
                            fund_amount = float(item.get("amount", 0.0))
                            break
                
                # 如果没找到或为0，则默认使用当前资产（此时 times = 1.0，即不触发低仓位保护）
                if fund_amount <= 0:
                     fund_amount = float(plan_assets) if plan_assets and float(plan_assets) > 0 else 1.0

                times = round(float(plan_assets) / float(fund_amount), 2)
            except Exception:
                logger.info(f"基金 {fund_name}{fund_code} 的资产解析失败，跳过")
                continue
            volatility = fund_info.volatility 

            # 收益率计算（与业务层一致）
            current_profit_rate = constant_profit_rate if constant_profit_rate is not None else 0.0
            estimated_change, label_est = calc_estimated_change(fund_info)
            estimated_profit_rate = current_profit_rate + estimated_change
            rank_100 = fund_info.rank_100day

            logger.info(f"收益率计算：当前收益率{current_profit_rate}%，估值变化{estimated_change}%，预估收益率{estimated_profit_rate}%（{label_est}）")
            logger.info(f"其他指标：波动率{volatility}%，100日排名{rank_100}，投资次数{times}")

            if shares == []:
                logger.info(f"组合{sub_account_name}的{fund_name}{fund_code}当前份额为空，跳过该计划")
                continue

            nav_date_str = getattr(fund_info, "nav_date", None)
            if nav_date_str:
                try:
                    prev_trade_day = datetime.datetime.strptime(str(nav_date_str)[:10], "%Y-%m-%d").date()
                except Exception:
                    prev_trade_day = None
            else:
                prev_trade_day = None

            def _has_pending_trade() -> bool:
                prev_trade_record = has_buy_submission_on_dates(user, sub_account_no, fund_code, prev_trade_day)
                if prev_trade_record:
                    state = getattr(prev_trade_record, "app_state_text", None) or getattr(prev_trade_record, "status", None)
                    logger.info(f"[在途检查] 基金 {fund_code} 上一个交易日({nav_date_str})已有有效交易（状态={state}），跳过止盈")
                    return True

                today = datetime.date.today()
                today_trade_record = has_buy_submission_on_dates(user, sub_account_no, fund_code, today)
                if today_trade_record:
                    state = getattr(today_trade_record, "app_state_text", None) or getattr(today_trade_record, "status", None)
                    logger.info(f"[在途检查] 基金 {fund_code} 今日({today})已有有效交易（状态={state}），跳过止盈")
                    return True

                logger.info(f"[在途检查] 基金 {fund_code} nav_date={nav_date_str}, prev_trade_day={prev_trade_day}, 查询结果: 无交易")
                return False
            
            # --- 止盈逻辑更新：对齐全局智能定投 (redeem.py) ---
            
            # 2. 计算动态止盈点：min(max(30日年化波动率, 3.0%), 10.0%)
            stop_rate = min(max(float(volatility), 3.0), 10.0)
            logger.info(f"组合{sub_account_name}的{fund_name}{fund_code}波动率={volatility:.2f}，设置止盈点={stop_rate:.2f}（3.0~10.0之间）")

            # 3. 检查基本止盈条件
            # 记录基本止盈条件检查结果
            basic_stop_condition_checks = []
            
            if estimated_profit_rate > stop_rate:
                basic_stop_condition_checks.append(f"✓ 预估收益率检查通过（{estimated_profit_rate:.2f}% > {stop_rate:.2f}%）")
                if _has_pending_trade():
                    continue
                logger.info(f"{customer_name}的止盈操作开始：基金{fund_name}{fund_code}预估收益{estimated_profit_rate},实际止盈点:{stop_rate}")
                res = sell_0_fee_shares(user, sub_account_no, fund_code, shares)
                if res is not None and getattr(res, 'busin_serial_no', None):
                    success_count += 1
                # 打印过滤条件汇总信息
                logger.info(f"[过滤条件汇总] 基金 {fund_name}({fund_code}) 满足基本止盈条件:")
                for check in basic_stop_condition_checks:
                    logger.info(f"  {check}")
            else:
                basic_stop_condition_checks.append(f"✗ 预估收益率检查失败（{estimated_profit_rate:.2f}% ≤ {stop_rate:.2f}%）")
                logger.info(f"基本止盈条件未满足 ({fund_name} {fund_code})，原因: 预估收益 {estimated_profit_rate:.2f}% <= 止盈点 {stop_rate:.2f}%")
                # 打印过滤条件汇总信息
                logger.info(f"[过滤条件汇总] 基金 {fund_name}({fund_code}) 基本止盈条件检查结果:")
                for check in basic_stop_condition_checks:
                    logger.info(f"  {check}")
            
            # 4. 现金流紧张时的紧急止盈逻辑
            # 获取活期宝占比 (此处需要调用公共服务或直接计算，为了保持一致性建议调用 risk_control_service 中的逻辑)
            # 但 check_hqb_risk_allowed 只返回 bool，我们需要具体的比率。
            # 这里先手动计算一下 hqb_ratio_percent，或者假设 check_hqb_risk_allowed 内部逻辑
            # 为了更准确，我们重新获取资产总额计算占比
            from src.API.资产管理.AssetManager import GetMyAssetMainPart
            try:
                my_asset = GetMyAssetMainPart(user)
                if my_asset.Success and my_asset.Data:
                    # 兼容不同API返回结构，尝试获取 TotalValue/HqbValue 或 TotalAsset/HqbAsset
                    total_asset = float(my_asset.Data.get('TotalValue', 0.0) or my_asset.Data.get('TotalAsset', 0.0) or 1.0)
                    hqb_asset = float(my_asset.Data.get('HqbValue', 0.0) or my_asset.Data.get('HqbAsset', 0.0) or 0.0)
                else:
                    # 获取失败回退逻辑
                    total_asset = 1.0
                    hqb_asset = 0.0
                    logger.warning(f"获取资产失败: {my_asset.FirstError}，使用默认值")
            except Exception as e:
                logger.warning(f"获取资产异常: {e}，使用默认值")
                total_asset = 1.0
                hqb_asset = 0.0
                
            hqb_ratio_percent = (hqb_asset / total_asset) * 100
            
            # 指数基金且非QDII，若仓位不重且今日上涨，立即止盈
            # 条件:
            # 1. 类型为指数 (000) 且非 QDII
            # 2. 投资次数 < 5.0 (仓位还不重)
            # 3. 今日估值上涨 > 0.5% (趁反弹跑路)
            # if fund_type == '000' and "QDII" not in fund_name:
            #     if (times < 5.0 and 
            #         estimated_change > 0.5 and
            #         estimated_profit_rate > 3.0):
                    
            #         logger.info(f"{customer_name}的指数基金快速止盈操作：基金{fund_name}({fund_code})预估收益{estimated_profit_rate:.2f}%，"
            #                     f"投资次数:{times}, 估值增长率:{estimated_change}%.")
            #         res = sell_0_fee_shares(user, sub_account_no, fund_code, shares)
            #         if res is not None and getattr(res, 'busin_serial_no', None):
            #             success_count += 1
            #         continue
            #     else:
            #         logger.info(f"指数基金快速止盈条件未满足: 基金{fund_name}({fund_code}) "
            #                     f"投资次数:{times}(需<5.0), 估值增长:{estimated_change:.2f}%(需>0.5%), 收益率:{estimated_profit_rate:.2f}%(需>3.0%)")

        
            # 取消对小额资产的止盈保护
            # if times < 0.98 and times > 0.0:
            #     logger.info(f"组合{sub_account_no}，基金{fund_name}({fund_code})资产{plan_assets:.2f}，当前资产倍数{times},满足限购保护，停止止盈。")
            #     continue
            if estimated_profit_rate < 1.0:
                logger.info(f"额外止盈及兜底止盈被拦截 ({fund_name} {fund_code})，原因: 收益率 {estimated_profit_rate:.2f}% < 1.0%")
                continue

            # 赎回 0 费率份额 (额外补充逻辑，针对QDII)
            # if fund_type == 'a' and estimated_profit_rate > 3.0: # 参照 redeem.py 逻辑: QDII基金 > 3.0% 赎回0费率
            #      logger.info(f"{customer_name}的止盈操作开始：QDII基金{fund_name}{fund_code}预估收益{estimated_profit_rate},赎回0费率份额,实际止盈点:3.0")
            #      sell_0_fee_shares(user, sub_account_no, fund_code, shares)

            # 记录指数基金额外止盈条件检查结果
            index_fund_stop_condition_checks = []
            
            # 检查是否为指数基金
            if fund_type == '000':
                index_fund_stop_condition_checks.append("✓ 基金类型检查通过（指数基金）")
                
                # 检查是否为QDII基金
                if fund_type != 'a' and "QDII" not in fund_name:
                    index_fund_stop_condition_checks.append("✓ QDII检查通过（非QDII基金）")
                else:
                    index_fund_stop_condition_checks.append("✗ QDII检查失败（是QDII基金）")
                
                # 检查活期宝占比
                if hqb_ratio_percent < HQB_RATIO_THRESHOLD:
                    index_fund_stop_condition_checks.append(f"✓ 活期宝占比检查通过（{hqb_ratio_percent:.2f}% < {HQB_RATIO_THRESHOLD}%）")
                else:
                    index_fund_stop_condition_checks.append(f"✗ 活期宝占比检查失败（{hqb_ratio_percent:.2f}% ≥ {HQB_RATIO_THRESHOLD}%）")
                
                # 检查今日估值上涨
                if estimated_change > 0.5:
                    index_fund_stop_condition_checks.append(f"✓ 估值上涨检查通过（{estimated_change:.2f}% > 0.5%）")
                else:
                    index_fund_stop_condition_checks.append(f"✗ 估值上涨检查失败（{estimated_change:.2f}% ≤ 0.5%）")
                
                # 检查收益率
                if estimated_profit_rate > 1.0:
                    index_fund_stop_condition_checks.append(f"✓ 收益率检查通过（{estimated_profit_rate:.2f}% > 1.0%）")
                else:
                    index_fund_stop_condition_checks.append(f"✗ 收益率检查失败（{estimated_profit_rate:.2f}% ≤ 1.0%）")
                
                # 检查100日排名
                if rank_100 is not None and rank_100 > 90:
                    index_fund_stop_condition_checks.append(f"✓ 100日排名检查通过（{rank_100} > 90）")
                else:
                    index_fund_stop_condition_checks.append(f"✗ 100日排名检查失败（{rank_100} ≤ 90 或为空）")
                
                # 检查所有条件是否都满足
                if fund_type == '000' and fund_type != 'a' and "QDII" not in fund_name and hqb_ratio_percent < HQB_RATIO_THRESHOLD and estimated_change > 0.5 and estimated_profit_rate > 1.0 and rank_100 is not None and rank_100 > 90:
                    if _has_pending_trade():
                        continue
                    logger.info(
                        f"{customer_name}的止盈操作开始：指数基金{fund_name}{fund_code}且非QDII，"
                        f"活期宝占比{hqb_ratio_percent:.2f}%<{HQB_RATIO_THRESHOLD}%，"
                        f"100日排名{rank_100}>90，"
                        f"今日估值上涨{estimated_change:.2f}%，且收益率{estimated_profit_rate:.2f}%>1.0%，赎回0费率份额"
                    )
                    res = sell_0_fee_shares(user, sub_account_no, fund_code, shares)
                    if res is not None and getattr(res, 'busin_serial_no', None):
                        success_count += 1
                    # 打印过滤条件汇总信息
                    logger.info(f"[过滤条件汇总] 基金 {fund_name}({fund_code}) 满足指数基金额外止盈条件:")
                    for check in index_fund_stop_condition_checks:
                        logger.info(f"  {check}")
                else:
                    # 打印过滤条件汇总信息
                    logger.info(f"[过滤条件汇总] 基金 {fund_name}({fund_code}) 指数基金额外止盈条件检查结果:")
                    for check in index_fund_stop_condition_checks:
                        logger.info(f"  {check}")
                    
                    # 记录指数基金止盈未满足的原因
                    reasons = []
                    if fund_type == 'a' or "QDII" in fund_name:
                        reasons.append("是QDII基金")
                    if hqb_ratio_percent >= HQB_RATIO_THRESHOLD:
                        reasons.append(f"活期宝占比 {hqb_ratio_percent:.2f}% >= 阈值 {HQB_RATIO_THRESHOLD}%")
                    if estimated_change <= 0.5:
                        reasons.append(f"估值上涨 {estimated_change:.2f}% <= 0.5%")
                    if estimated_profit_rate <= 1.0:
                        reasons.append(f"收益率 {estimated_profit_rate:.2f}% <= 1.0%")
                    if rank_100 is None or rank_100 <= 90:
                        reasons.append(f"100日排名 {rank_100} <= 90 或为空")
                    
                    if reasons:
                        logger.info(f"指数基金额外止盈条件未满足 ({fund_name} {fund_code})，原因: {', '.join(reasons)}")
            else:
                index_fund_stop_condition_checks.append(f"✗ 基金类型检查失败（非指数基金，类型为 {fund_type}）")
                logger.info(f"非指数基金不适用额外止盈条件 ({fund_name} {fund_code})，原因: 基金类型为 {fund_type}")
                # 打印过滤条件汇总信息
                logger.info(f"[过滤条件汇总] 基金 {fund_name}({fund_code}) 指数基金额外止盈条件检查结果:")
                for check in index_fund_stop_condition_checks:
                    logger.info(f"  {check}")

            # 兜底止盈逻辑：当预期收益率 > 10.0 的时候 卖出低费率份额
            # 记录兜底止盈条件检查结果
            fallback_stop_condition_checks = []
            
            if estimated_profit_rate > 10.0:
                fallback_stop_condition_checks.append(f"✓ 预估收益率检查通过（{estimated_profit_rate:.2f}% > 10.0%）")
                if _has_pending_trade():
                    continue
                logger.info(f"{customer_name}的兜底止盈操作开始：基金{fund_name}{fund_code}预估收益{estimated_profit_rate:.2f}% > 10.0%，赎回低费率份额")
                res = sell_low_fee_shares(user, sub_account_no, fund_code, shares)
                if res is not None and getattr(res, 'busin_serial_no', None):
                    success_count += 1
                # 打印过滤条件汇总信息
                logger.info(f"[过滤条件汇总] 基金 {fund_name}({fund_code}) 满足兜底止盈条件:")
                for check in fallback_stop_condition_checks:
                    logger.info(f"  {check}")
            else:
                fallback_stop_condition_checks.append(f"✗ 预估收益率检查失败（{estimated_profit_rate:.2f}% ≤ 10.0%）")
                logger.info(f"兜底止盈条件未满足 ({fund_name} {fund_code})，原因: 预估收益率 {estimated_profit_rate:.2f}% <= 10.0%")
                # 打印过滤条件汇总信息
                logger.info(f"[过滤条件汇总] 基金 {fund_name}({fund_code}) 兜底止盈条件检查结果:")
                for check in fallback_stop_condition_checks:
                    logger.info(f"  {check}")

        except Exception as e:
            logger.error(f"处理 {fund_code} 失败: {e}")

    logger.info(f"止盈完成：{customer_name} 成功执行 {success_count} 次赎回操作")
    return success_count > 0


if __name__ == "__main__":
    try:
        redeem_funds(
            DEFAULT_USER,
            "快速止盈",
            fund_list=[
                {"fund_code": "016702", "fund_name": "银华海外数字经济量化选股混合发起式(QDII)C", "amount": 5000.0},
                {"fund_code": "006105", "fund_name": "宏利印度股票(QDII)", "amount": 5000.0},
                {"fund_code": "161226", "fund_name": "国投瑞银白银期货(LOF)A", "amount": 5000.0},
                {"fund_code": "017873", "fund_name": "汇添富香港优势精选混合(QDII)C", "amount": 5000.0},
                {"fund_code": "019449", "fund_name": "摩根日本精选股票(QDII)C", "amount": 5000.0},
                {"fund_code": "501018", "fund_name": "南方原油A", "amount": 5000.0},
                {"fund_code": "016453", "fund_name": "南方纳斯达克100指数发起(QDII)C", "amount": 5000.0},
                {"fund_code": "000614", "fund_name": "华安德国(DAX)联接(QDII)A", "amount": 5000.0},
                {"fund_code": "021539", "fund_name": "华安法国CAC40ETF发起式联接(QDII)A", "amount": 5000.0},
                {"fund_code": "015016", "fund_name": "华安德国(DAX)联接(QDII)C", "amount": 5000.0},
                {"fund_code": "008764", "fund_name": "天弘越南市场股票发起(QDII)C", "amount": 5000.0},
                {"fund_code": "501312", "fund_name": "华宝海外科技股票(QDII-LOF)A", "amount": 5000.0},
                {"fund_code": "017204", "fund_name": "华宝海外科技股票(QDII-LOF)C", "amount": 5000.0},
                {"fund_code": "021540", "fund_name": "华安法国CAC40ETF发起式联接(QDII)C", "amount": 5000.0},
                {"fund_code": "009975", "fund_name": "华宝标普美国消费人民币C", "amount": 5000.0},
                {"fund_code": "008706", "fund_name": "建信富时100指数(QDII)C人民币", "amount": 5000.0},
                {"fund_code": "007844", "fund_name": "华宝标普油气上游股票人民币C", "amount": 5000.0}
            ]
        )
        logger.info(f"用户 {DEFAULT_USER.customer_name} 止盈操作完成")
    except Exception as e:
        logger.error(f"测试用户处理失败：{str(e)}")
