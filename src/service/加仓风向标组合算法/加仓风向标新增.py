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
from src.common.errors import TradePasswordError  # 新增：捕获密码错误异常

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def _get_max_funds_threshold() -> int:
    """
    读取最大基金数量阈值：
    - 优先读取环境变量 MAX_FUNDS_THRESHOLD
    - 非法或未设置时回退为 30
    """
    env_val = os.environ.get('MAX_FUNDS_THRESHOLD')
    if env_val is None or env_val == "":
        return 30
    try:
        return int(env_val)
    except ValueError:
        logger.warning(f"环境变量 MAX_FUNDS_THRESHOLD 非法值: {env_val}，回退为默认 30")
        return 30


def add_new_funds(
    user: User,
    sub_account_name: str,
    total_budget: float,
    amount: Optional[float] = None,
    fund_type: str = 'all',
    fund_num: int = 1,
    spread_days: int = 5
) -> bool:
    """
    新增基金策略（最小集成落地）：
    - fund_num: 本次最多买入的基金只数（默认5）
    - spread_days: 预算摊薄天数（默认5）；仅当未传入amount时生效
    - fund_type: 'all' | 'index' | 'non_index'
    流程：
      1) 获取组合资产与持仓
      2) 若“基金数>=阈值”且“资产总和>总预算的80%”，停止新增（联合条件）
      3) 获取风向标并按 fund_type 过滤，去除已持有及重复指数
      4) 按排名排序并截取前 fund_num 只
      5) 根据余额可用性下调买入只数
      6) 下单
    """
    import time
    import random

    if not sub_account_name:
        raise ValueError("sub_account_name 是必填参数，不能为空")
    if total_budget is None:
        raise ValueError("total_budget 是必填参数，不能为空")

    logger.info(
        f"开始为用户 {user.customer_name} 执行新增基金操作，总预算：{total_budget}元，基金类型：{fund_type}，"
        f"fund_num={fund_num}，spread_days={spread_days}"
    )
    # 读取最大基金数阈值（本地/云端统一）
    MAX_FUNDS_THRESHOLD = _get_max_funds_threshold()

    # 计算预算分配
    if amount is None:
        base_per_fund = round(total_budget / max(MAX_FUNDS_THRESHOLD, 1) / max(spread_days, 1), 2)
    else:
        base_per_fund = float(amount)
    logger.info(f"单只基金基础买入金额: {base_per_fund}元")



    logger.info("========== 开始执行新增基金算法（最小落地版） ===========")
    logger.info(f"用户: {user.customer_name}，组合名称: {sub_account_name}")

    try:
        # 1) 获取组合资产与持仓
        user_assets = get_sub_account_asset_by_name(user, sub_account_name)
        if user_assets is None:
            logger.error(f"获取用户组合 {sub_account_name} 资产失败")
            return False

        user_fund_codes: Set[str] = set()
        user_index_codes: Set[str] = set()
        for asset in user_assets:
            # 记录已持有基金代码
            if getattr(asset, 'fund_code', None):
                user_fund_codes.add(asset.fund_code)
            # 如果是指数基金，记录其跟踪指数，避免重复
            try:
                fund_info = get_all_fund_info(user, asset.fund_code)
                if fund_info and getattr(fund_info, 'fund_type', None) == "000" and getattr(fund_info, 'index_code', None):
                    user_index_codes.add(fund_info.index_code)
            except Exception as e:
                logger.warning(f"获取基金 {getattr(asset, 'fund_code', 'N/A')} 信息失败: {e}")

        # 仅当“基金数量过多”且“资产总和超过80%”两个条件同时满足时，才退出
        total_asset_value = sum(
            (asset.asset_value or 0.0) for asset in user_assets
            if hasattr(asset, 'asset_value')
        )
        if len(user_assets) >= MAX_FUNDS_THRESHOLD and total_asset_value > total_budget * 0.8:
            logger.info(
                f"用户 {user.customer_name} 的基金数量已达到{MAX_FUNDS_THRESHOLD}个，且资产总和({total_asset_value}元)"
                f"已超过总预算({total_budget}元)的80%({total_budget * 0.8}元)，停止新增基金"
            )
            return True
        else:
            count = len(user_assets)
            ratio = (total_asset_value / total_budget) if total_budget else None
            ratio_pct_str = f"{ratio*100:.2f}%" if ratio is not None else "N/A"

            reasons = []
            if count < MAX_FUNDS_THRESHOLD:
                reasons.append(f"基金数量未达到{MAX_FUNDS_THRESHOLD}个(当前{count}个)")
            if total_budget and total_asset_value <= total_budget * 0.8:
                reasons.append(f"资产占比未超过80%(当前{total_asset_value}元/{total_budget}元={ratio_pct_str})")
            if not total_budget:
                reasons.append("总预算为0或未设置，无法计算资产占比")

            reason_text = "；".join(reasons) if reasons else "条件计算异常"
            logger.info(f"用户 {user.customer_name} 未满足停止新增条件：{reason_text}，继续执行新增流程")

        # 2) 获取加仓风向标数据并按 fund_type 过滤
        wind_vane_funds = get_fund_investment_indicators()
        if not wind_vane_funds:
            logger.error("获取加仓风向标数据失败")
            return False

        if fund_type == 'index':
            wind_vane_funds = [f for f in wind_vane_funds if getattr(f, 'fund_type', None) == '000']
        elif fund_type == 'non_index':
            wind_vane_funds = [f for f in wind_vane_funds if getattr(f, 'fund_type', None) != '000']
        # 'all' 不过滤

        # 去除已持有的基金；指数基金避免重复跟踪同一指数
        candidates = []
        for f in wind_vane_funds:
            code = getattr(f, 'fund_code', None)
            if not code or code in user_fund_codes:
                continue

            ftype = getattr(f, 'fund_type', None)
            if ftype == '000':
                try:
                    info = get_all_fund_info(user, code)
                    idx_code = getattr(info, 'index_code', None) if info else None
                    if idx_code and idx_code in user_index_codes:
                        # 已持有同指数的基金，跳过
                        continue
                except Exception as e:
                    logger.warning(f"获取指数基金 {code} 信息失败，仍纳入候选：{e}")

            candidates.append(f)

        if not candidates:
            logger.info("候选基金为空：风向标基金均已持有或重复指数，退出新增流程")
            return True

        # 按产品排名升序（越小越优），无排名置于末尾
        try:
            candidates.sort(key=lambda f: getattr(f, 'product_rank', float('inf')))
        except Exception as e:
            logger.warning(f"按排名排序候选基金失败，将按原顺序处理：{e}")

        # 限制本次最多买入 fund_num 只
        selected_funds = candidates[:max(fund_num, 1)]
        logger.info(f"候选基金数: {len(candidates)}，计划买入: {len(selected_funds)} 只")

        # 3) 查询余额并按余额下调买入只数
        try:
            asset_response = GetMyAssetMainPartAsync(user)
            if getattr(asset_response, 'Success', False) and getattr(asset_response, 'Data', None):
                available_balance = asset_response.Data.get('HqbValue', 0.0)
                logger.info(f"从资产API获取HqbValue: {available_balance}元")
            else:
                raise Exception("资产API调用失败")
        except Exception as e:
            logger.error(f"获取用户资产失败: {e}")
            return False

        if available_balance <= 0:
            logger.info("可用余额为0，退出新增流程")
            return True

        if base_per_fund <= 0:
            logger.info(f"单只基金买入金额无效({base_per_fund})，退出新增流程")
            return True

        max_count_by_balance = int(available_balance // base_per_fund)
        if max_count_by_balance <= 0:
            logger.info(f"余额({available_balance}元)不足以买入一只基金({base_per_fund}元)，退出新增流程")
            return True

        if len(selected_funds) > max_count_by_balance:
            logger.info(f"根据余额限制，将本次买入只数从{len(selected_funds)}下调为{max_count_by_balance}")
            selected_funds = selected_funds[:max_count_by_balance]

        # 4) 获取子账户编号
        sub_account_no = getSubAccountNoByName(user, sub_account_name)
        if not sub_account_no:
            logger.error(f"获取子账户编号失败: {sub_account_name}")
            return False

        # 5) 下单
        success_count = 0
        for f in selected_funds:
            code = getattr(f, 'fund_code', None)
            name = getattr(f, 'fund_name', code or 'N/A')
            buy_amount = base_per_fund

            # 判断是否可申购（若可获取）
            try:
                info = get_all_fund_info(user, code)
                if info and hasattr(info, 'can_purchase') and not info.can_purchase:
                    logger.warning(f"基金 {name}({code}) 当前不可申购，跳过")
                    continue
            except Exception as e:
                logger.warning(f"获取基金 {code} 申购状态失败，继续尝试下单：{e}")

            try:
                result = commit_order(user, sub_account_no, code, buy_amount)
                if result:
                    order_no = getattr(result, 'busin_serial_no', 'N/A')
                    logger.info(f"买入成功: {name}({code}) - 金额: {buy_amount}元 - 订单号: {order_no}")
                    success_count += 1
                else:
                    logger.error(f"买入失败: {name}({code})")
            except Exception as e:
                logger.error(f"买入基金 {name}({code}) 时发生异常: {e}")

            # 控制频率，防止过快请求
            time.sleep(random.uniform(0.3, 0.8))

        logger.info(f"本次新增完成，成功买入 {success_count}/{len(selected_funds)} 只基金")
        return success_count > 0

    except Exception as e:
        logger.error(f"新增基金算法执行失败: {e}")
        import traceback
        logger.error(f"异常堆栈: {traceback.format_exc()}")
        return False
        