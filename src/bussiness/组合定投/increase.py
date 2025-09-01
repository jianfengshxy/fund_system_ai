import logging
import os
import sys

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.domain.user.User import User
from src.service.大数据.加仓风向标服务 import get_fund_investment_indicators
from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name
from src.service.基金信息.基金信息 import get_all_fund_info
from src.API.交易管理.buyMrg import commit_order
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.common.constant import DEFAULT_USER
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def increase(user: User, sub_account_name: str = "低风险组合", amount: int = 10000.0) -> bool:
    """组合定投加仓实现"""
    # 第一步：获取加仓风向标
    indicators = get_fund_investment_indicators(days=10, threshold=3)
    logger.info(f"获取加仓风向标: {indicators}")

    # 获取组合账号
    sub_account_no = getSubAccountNoByName(user, sub_account_name)

    # 第二步：找到对应组合的资产并遍历
    asset_details_list = get_sub_account_asset_by_name(user, sub_account_name)
    if asset_details_list is None:
        logger.info(f"{user.customer_name} 在组合 {sub_account_name} 中没有基金资产.")
        return True

    for asset_detail in asset_details_list:
        if asset_detail.fund_code is None:
            continue
        fund_code = asset_detail.fund_code
        fund_name = asset_detail.fund_name

        # 获取基金信息
        fund_info = get_all_fund_info(user, fund_code)

        # 计算预估收益率
        estimated_profit_rate = asset_detail.constant_profit_rate + fund_info.estimated_change
        logger.info(f"基金 {fund_name} ({fund_code}) 预估收益率: {estimated_profit_rate}")

        # 如果预估收益率 > -1.0% 跳过
        if estimated_profit_rate > -1.0:
            logger.info(f"预估收益率 {estimated_profit_rate} > -1.0%，跳过 {fund_name}")
            continue

        # 如果有在途交易跳过
        if asset_detail.on_way_transaction_count > 0:
            logger.info(f"{fund_name} 有在途交易，跳过")
            continue

        # 如果不在加仓风向标跳过（增强逻辑：对于指数基金，检查追踪指数）
        in_indicators = fund_code in [ind.fund_code for ind in indicators]
        if not in_indicators:
            fund_info = get_all_fund_info(user, fund_code)
            if fund_info and fund_info.fund_type == "000" and fund_info.index_code:
                if any(ind.index_code == fund_info.index_code for ind in indicators if hasattr(ind, 'index_code')):
                    in_indicators = True

        if not in_indicators:
            logger.info(f"{fund_name} 不在加仓风向标中，跳过")
            continue

        # 如果都成立则买入基金
        try:
            commit_order(user, sub_account_no, fund_code, amount)
            logger.info(f"{user.customer_name} 在组合 {sub_account_name} 中购买基金 {fund_name} ({fund_code})，金额: {amount} 成功")
        except Exception as e:
            logger.error(f"购买失败: {str(e)}")
            return False

    return True

if __name__ == "__main__":
    # 直接运行测试
    increase(DEFAULT_USER)