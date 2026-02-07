import logging
import sys
import os

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.domain.user.User import User
from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.service.交易管理.赎回基金 import sell_0_fee_shares

logger = get_logger(__name__)

def redeem_gold_funds(user: User, sub_account_name: str) -> bool:
    """
    黄金多利止盈逻辑：
    收益率大于1.0% 就买出0费率份额
    """
    logger.info(f"开始执行黄金多利止盈检查，组合: {sub_account_name}", extra={"account": user.account, "sub_account_name": sub_account_name, "action": "gold_redeem"})

    # 获取子账户编号
    sub_account_no = getSubAccountNoByName(user, sub_account_name)
    if not sub_account_no:
        logger.error(f"未找到组合 {sub_account_name} 的账号")
        return False

    # 获取持仓
    user_assets = get_sub_account_asset_by_name(user, sub_account_name)
    if not user_assets:
        logger.info(f"组合 {sub_account_name} 中没有基金资产")
        return True

    redeem_count = 0

    for asset in user_assets:
        try:
            current_profit_rate = float(getattr(asset, "constant_profit_rate", 0.0) or 0.0)
            fund_code = asset.fund_code
            fund_name = asset.fund_name

            if current_profit_rate > 1.0:
                logger.info(f"基金 {fund_name}({fund_code}) 收益率 {current_profit_rate}% > 1.0%，尝试赎回0费率份额")
                
                # 执行0费率赎回
                # 注意：sell_0_fee_shares 内部会判断是否有0费率份额，如果有则赎回，没有则跳过
                result = sell_0_fee_shares(user, sub_account_no, fund_code)
                
                if result: # 假设返回True表示成功提交或处理
                    # 由于 sell_0_fee_shares 可能会打印日志，这里简单记录
                    redeem_count += 1
            else:
                 logger.info(f"基金 {fund_name}({fund_code}) 收益率 {current_profit_rate}% <= 1.0%，不满足止盈条件")

        except Exception as e:
            logger.error(f"处理基金 {asset.fund_code} 止盈时发生错误: {e}")
            continue

    logger.info(f"止盈检查完成，共触发 {redeem_count} 只基金的赎回尝试")
    return True

if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    try:
        # 1. 构造测试用户
        test_user = DEFAULT_USER
        
        # 2. 设置测试参数
        test_sub_account = "黄金多利"

        print(f"--- 开始测试黄金多利止盈 ---")
        print(f"用户: {test_user.customer_name}")
        print(f"组合: {test_sub_account}")
        
        # 3. 调用止盈函数
        redeem_gold_funds(test_user, test_sub_account)
        
        print(f"--- 测试结束 ---")

    except Exception as e:
        logger.error(f"测试执行失败: {e}")
