import logging
import sys
import os
from typing import List, Optional, Set

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.domain.user.User import User
from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.service.基金信息.基金信息 import get_all_fund_info
from src.domain.asset.asset_details import AssetDetails
from src.service.定投管理.组合定投.组合定投管理 import create_period_investment_by_group
from src.service.大数据.加仓风向标服务 import get_fund_investment_indicators
from src.service.交易管理.购买基金 import commit_order
from src.common.constant import DEFAULT_USER  # 添加导入，如果需要
from src.API.资产管理.AssetManager import GetMyAssetMainPartAsync
from src.API.基金信息.FundRank import get_fund_growth_rate

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def add_new_funds(user: User, sub_account_name: str, total_budget: float, amount: Optional[float] = None, fund_type: str = 'all') -> bool:
    if not sub_account_name:
        raise ValueError("sub_account_name 是必填参数，不能为空")
    if total_budget is None:
        raise ValueError("total_budget 是必填参数，不能为空")
    
    logger.info(f"开始为用户 {user.customer_name} 执行新增基金操作，总预算：{total_budget}元，基金类型：{fund_type}")
    
    # 使用increase.py的公式计算每个基金的购买金额
    fund_num = 5  #每天购买的基金个数
    budget_per_fund = round(total_budget / fund_num / 20, 2)
    logger.info(f"计算得出单个基金购买金额：{budget_per_fund}元")
    
    customer_name = user.customer_name
    logger.info(f"========== 开始执行新增基金算法 ===========")
    logger.info(f"用户: {customer_name}")
    logger.info(f"组合名称: {sub_account_name}")
    logger.info(f"每个基金预算: {budget_per_fund}元")
    
    try:
        # 步骤1: 获取用户对应组合里面所有的基金
        logger.info("=== 步骤1: 获取用户组合中的所有基金 ===")
        user_assets = get_sub_account_asset_by_name(user, sub_account_name)
        if user_assets is None:
            logger.error(f"获取用户组合 {sub_account_name} 资产失败")
            return False
        
        # 提取用户持有的基金代码和跟踪指数
        user_fund_codes = set()
        user_index_codes = set()
        
        logger.info(f"用户组合中共有 {len(user_assets)} 个基金")
        for i, asset in enumerate(user_assets, 1):
            user_fund_codes.add(asset.fund_code)
            logger.info(f"  持有基金{i}: {asset.fund_name}({asset.fund_code}) - 份额:{asset.available_vol}")
            
            # 如果是指数基金，获取跟踪指数
            try:
                fund_info = get_all_fund_info(user, asset.fund_code)
                if fund_info and hasattr(fund_info, 'fund_type') and fund_info.fund_type == "000":
                    if hasattr(fund_info, 'index_code') and fund_info.index_code:
                        user_index_codes.add(fund_info.index_code)
                        logger.info(f"    指数基金跟踪指数: {fund_info.index_code}")
            except Exception as e:
                logger.warning(f"获取基金 {asset.fund_code} 详细信息失败: {e}")
        
        logger.info(f"用户持有基金代码: {user_fund_codes}")
        logger.info(f"用户持有指数基金跟踪的指数: {user_index_codes}")
        
        # 步骤2: 判断用户所有的基金数量是否大于等于50
        logger.info("=== 步骤2: 检查用户基金数量限制 ===")
        if len(user_assets) >= 50:
            logger.info(f"用户 {customer_name} 的基金数量已达到50个，无需新增基金，退出操作")
            return True
        
        logger.info(f"用户当前基金数量: {len(user_assets)}，可以继续新增基金")
        
        # 步骤3: 获取加仓风向标数据
        logger.info("=== 步骤3: 获取加仓风向标数据 ===")
        wind_vane_funds = get_fund_investment_indicators()
        if not wind_vane_funds:
            logger.error("获取加仓风向标数据失败")
            return False
        
        # 根据fund_type过滤
        if fund_type == 'index':
            wind_vane_funds = [f for f in wind_vane_funds if f.fund_type == '000']
        elif fund_type == 'non_index':
            wind_vane_funds = [f for f in wind_vane_funds if f.fund_type != '000']
        # 'all' 不需要过滤
        
        logger.info(f"过滤后获取到 {len(wind_vane_funds)} 个加仓风向标基金")
        for i, fund in enumerate(wind_vane_funds, 1):
            logger.info(f"  风向标基金{i}: {fund.fund_name}({fund.fund_code}) - 类型:{fund.fund_type} - 排名:{fund.product_rank}")
        
        # 步骤4: 检查用户预算
        logger.info("=== 步骤4: 检查用户可用资金 ===")
        try:
            asset_response = GetMyAssetMainPartAsync(user)
            if asset_response.Success and asset_response.Data:
                available_balance = asset_response.Data.get('HqbValue', 0.0)
                logger.info(f"从资产API获取HqbValue: {available_balance}元")
            else:
                raise Exception("资产API调用失败")
        except Exception as e:
            logger.error(f"获取用户资产失败: {e}")
            return False
        
        if available_balance < budget_per_fund:
            logger.warning(f"用户可用余额 {available_balance}元 小于单个基金预算 {budget_per_fund}元")
            budget_per_fund = min(available_balance * 0.8, budget_per_fund)  # 使用80%的可用余额
            logger.info(f"调整单个基金预算为: {budget_per_fund}元")
        
        # 获取组合账号
        sub_account_no = getSubAccountNoByName(user, sub_account_name)
        if not sub_account_no:
            logger.error(f"未找到组合名称 {sub_account_name} 对应的组合账号")
            return False
        
        logger.info(f"组合账号: {sub_account_no}")
        
        # 步骤5: 筛选需要买入的基金
        logger.info("=== 步骤5: 筛选需要买入的基金 ===")
        funds_to_buy = []
        
        for fund in wind_vane_funds:
            should_buy = False
            reason = ""
            
            # 检查基金是否已在用户组合中
            if fund.fund_code in user_fund_codes:
                logger.info(f"跳过基金 {fund.fund_name}({fund.fund_code}): 用户已持有")
                continue
            
            # 如果是指数基金（类型000），检查跟踪指数是否重复
            if fund.fund_type == "000":
                try:
                    fund_info = get_all_fund_info(user, fund.fund_code)
                    if fund_info and hasattr(fund_info, 'index_code') and fund_info.index_code:
                        if fund_info.index_code in user_index_codes:
                            logger.info(f"跳过指数基金 {fund.fund_name}({fund.fund_code}): 用户已持有跟踪相同指数({fund_info.index_code})的基金")
                            continue
                        else:
                            should_buy = True
                            reason = f"指数基金，跟踪指数 {fund_info.index_code} 用户未持有"
                    else:
                        should_buy = True
                        reason = "指数基金，无法获取跟踪指数信息，但用户未持有该基金"
                except Exception as e:
                    logger.warning(f"获取指数基金 {fund.fund_code} 详细信息失败: {e}")
                    should_buy = True
                    reason = "指数基金，获取详细信息失败，但用户未持有该基金"
            else:
                # 非指数基金，直接买入
                should_buy = True
                reason = f"非指数基金（类型:{fund.fund_type}），用户未持有"
            
            if should_buy:
                funds_to_buy.append(fund)
                logger.info(f"选择买入基金: {fund.fund_name}({fund.fund_code}) - 原因: {reason}")
        
        if not funds_to_buy:
            logger.info("没有需要买入的新基金")
            return True
        
        logger.info(f"共选择 {len(funds_to_buy)} 个基金进行买入")
        
        # 执行买入操作
        logger.info("=== 开始执行买入操作 ===")
        success_count = 0
        buy_amount = amount if amount is not None else budget_per_fund
        for i, fund in enumerate(funds_to_buy, 1):
            logger.info(f"正在买入第 {i}/{len(funds_to_buy)} 个基金: {fund.fund_name}({fund.fund_code})")
            
            try:
                # 检查基金是否可申购
                fund_info = get_all_fund_info(user, fund.fund_code)
                if fund_info and hasattr(fund_info, 'can_purchase') and not fund_info.can_purchase:
                    logger.warning(f"基金 {fund.fund_name}({fund.fund_code}) 当前不可申购，跳过")
                    continue
                
                # 执行买入
                trade_result = commit_order(user, sub_account_no, fund.fund_code, buy_amount)
                
                if trade_result:
                    logger.info(f"买入成功: {fund.fund_name}({fund.fund_code}) - 金额: {budget_per_fund}元 - 订单号: {trade_result.busin_serial_no}")
                    success_count += 1
                else:
                    logger.error(f"买入失败: {fund.fund_name}({fund.fund_code})")
                    
            except Exception as e:
                logger.error(f"买入基金 {fund.fund_name}({fund.fund_code}) 时发生异常: {e}")
        
        logger.info(f"=== 新增基金操作完成 ===")
        logger.info(f"成功买入 {success_count}/{len(funds_to_buy)} 个基金")
        
        return success_count > 0
        
    except Exception as e:
        logger.error(f"新增基金算法执行失败: {e}")
        import traceback
        logger.error(f"异常堆栈: {traceback.format_exc()}")
        return False

def add_new_funds(user: User, sub_account_name: str, total_budget: float, amount: Optional[float] = None, fund_type: str = 'all', fund_num: int = 5, spread_days: int = 20) -> bool:
    """
    新增基金策略（最小集成落地）：
    - fund_num: 本次最多买入的基金只数（默认5）
    - spread_days: 预算摊薄天数（默认20）；仅当未传入amount时生效
    """
    import time, random  # 局部导入，减少全局影响
    if not sub_account_name:
        raise ValueError("sub_account_name 是必填参数，不能为空")
    if total_budget is None:
        raise ValueError("total_budget 是必填参数，不能为空")

    logger.info(f"开始为用户 {user.customer_name} 执行新增基金操作，总预算：{total_budget}元，基金类型：{fund_type}，fund_num={fund_num}，spread_days={spread_days}")

    # 计算预算分配
    if amount is None:
        base_per_fund = round(total_budget / max(fund_num, 1) / max(spread_days, 1), 2)
    else:
        base_per_fund = float(amount)
    logger.info(f"单只基金基础买入金额: {base_per_fund}元")

    customer_name = user.customer_name
    logger.info("========== 开始执行新增基金算法（最小落地版） ===========")
    logger.info(f"用户: {customer_name}，组合名称: {sub_account_name}")

    try:
        # 1) 获取组合资产与持仓
        user_assets = get_sub_account_asset_by_name(user, sub_account_name)
        if user_assets is None:
            logger.error(f"获取用户组合 {sub_account_name} 资产失败")
            return False

        user_fund_codes: Set[str] = set()
        user_index_codes: Set[str] = set()
        for asset in user_assets:
            user_fund_codes.add(asset.fund_code)
            try:
                fund_info = get_all_fund_info(user, asset.fund_code)
                if fund_info and getattr(fund_info, 'fund_type', None) == "000" and getattr(fund_info, 'index_code', None):
                    user_index_codes.add(fund_info.index_code)
            except Exception as e:
                logger.warning(f"获取基金 {asset.fund_code} 信息失败: {e}")

        # 仅当“基金数量过多”且“资产总和超过80%”两个条件同时满足时，才退出
        total_asset_value = sum(asset.asset_value for asset in user_assets if asset.asset_value is not None)
        if len(user_assets) >= 30 and total_asset_value > total_budget * 0.8:
            logger.info(f"用户 {customer_name} 的基金数量已达到30个，且资产总和({total_asset_value}元)已超过总预算({total_budget}元)的80%({total_budget * 0.8}元)，停止新增基金")
            return True
        else:
            count = len(user_assets)
            # 避免除零错误
            ratio = (total_asset_value / total_budget) if total_budget else None
            ratio_pct_str = f"{ratio*100:.2f}%" if ratio is not None else "N/A"

            reasons = []
            if count < 30:
                reasons.append(f"基金数量未达到30个(当前{count}个)")
            # 仅当 total_budget 有效时才判断占比
            if total_budget and total_asset_value <= total_budget * 0.8:
                reasons.append(f"资产占比未超过80%(当前{total_asset_value}元/{total_budget}元={ratio_pct_str})")
            if not total_budget:
                reasons.append("总预算为0或未设置，无法计算资产占比")

            reason_text = "；".join(reasons) if reasons else "条件计算异常"
            logger.info(f"用户 {customer_name} 未满足停止新增条件：{reason_text}，继续执行新增流程")

        # 2) 获取风向标并按基金类型过滤
        wind_vane_funds = get_fund_investment_indicators()
        if not wind_vane_funds:
            logger.error("获取加仓风向标数据失败")
            return False

        if fund_type == 'index':
            wind_vane_funds = [f for f in wind_vane_funds if f.fund_type == '000']
        elif fund_type == 'non_index':
            wind_vane_funds = [f for f in wind_vane_funds if f.fund_type != '000']

        # 3) 过滤：去重已持有 + 避免指数重复
        candidates = []
        for f in wind_vane_funds:
            if f.fund_code in user_fund_codes:
                continue
            try:
                fi = get_all_fund_info(user, f.fund_code)
                if fi and getattr(fi, 'fund_type', None) == "000":
                    idx = getattr(fi, 'index_code', None)
                    if idx and idx in user_index_codes:
                        continue
            except Exception as e:
                logger.warning(f"获取指数基金 {f.fund_code} 信息失败: {e}")
            candidates.append(f)

        if not candidates:
            logger.info("没有需要买入的新基金")
            return True

        # 4) 选择前 N 只（按 product_rank 升序，如无则靠后）
        selected = sorted(candidates, key=lambda x: getattr(x, 'product_rank', 1e9))[:max(fund_num, 1)]
        logger.info(f"选择 {len(selected)} 只基金进行买入（最多 {fund_num} 只）")

        # 5) 获取余额，若不足则动态下调 buy_amount
        asset_response = GetMyAssetMainPartAsync(user)
        if not (asset_response.Success and asset_response.Data):
            logger.error("资产API调用失败")
            return False
        available_balance = float(asset_response.Data.get('HqbValue', 0.0))
        logger.info(f"可用余额 HqbValue: {available_balance}元")

        buy_amount = base_per_fund
        total_need = round(buy_amount * len(selected), 2)
        if available_balance < total_need:
            # 预留10%冗余，动态下调
            cap = max(10.0, round((available_balance * 0.9) / len(selected), 2))
            if cap < buy_amount:
                logger.warning(f"余额不足以覆盖计划买入（需要{total_need}元），将单只金额下调为 {cap} 元")
                buy_amount = cap

        # 6) 获取组合账号
        sub_account_no = getSubAccountNoByName(user, sub_account_name)
        if not sub_account_no:
            logger.error(f"未找到组合名称 {sub_account_name} 对应的组合账号")
            return False

        # 7) 下单（服务层 commit_order 已含交易时间/限额/余额保护）
        success_count = 0
        for i, f in enumerate(selected, 1):
            try:
                fi = get_all_fund_info(user, f.fund_code)
                if fi and hasattr(fi, 'can_purchase') and not fi.can_purchase:
                    logger.info(f"跳过不可申购基金: {f.fund_name}({f.fund_code})")
                    continue

                res = commit_order(user, sub_account_no, f.fund_code, buy_amount)
                if res:
                    logger.info(f"买入成功: {f.fund_name}({f.fund_code}) - 金额: {buy_amount}元 - 订单号: {res.busin_serial_no}")
                    success_count += 1
                else:
                    logger.error(f"买入失败: {f.fund_name}({f.fund_code})")

                time.sleep(random.uniform(0.2, 0.8))  # 轻微限流
            except Exception as e:
                logger.error(f"买入基金 {f.fund_name}({f.fund_code}) 异常: {e}")

        logger.info(f"新增基金完成，成功买入 {success_count}/{len(selected)} 只")
        return success_count > 0

    except Exception as e:
        logger.error(f"新增基金算法执行失败: {e}")
        import traceback
        logger.error(f"异常堆栈: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    # 测试单个用户的新增基金流程
    try:
        # 执行新增基金操作
        add_new_funds(DEFAULT_USER, "低风险组合", 1000000.0, None, 'non_index')  # 使用 DEFAULT_USER，并假设其有 budget 属性
        logging.info(f"用户 {DEFAULT_USER.customer_name} 新增基金操作完成")
    except Exception as e:
        logging.error(f"测试用户处理失败：{str(e)}")
        