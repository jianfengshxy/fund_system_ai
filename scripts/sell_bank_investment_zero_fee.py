import sys
import os
import time

# Add root dir to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.constant import DEFAULT_USER
from src.API.组合管理.SubAccountMrg import getSubAccountList
from src.service.资产管理.get_fund_asset_detail import get_asset_list_of_sub
from src.service.交易管理.费率查询 import get_0_fee_shares
from src.service.交易管理.赎回基金 import sell_0_fee_shares
from src.API.交易管理.trade import get_bank_shares
from src.API.定投计划管理.SmartPlan import getFundPlanList
from src.common.logger import get_logger

logger = get_logger(__name__)

def main():
    user = DEFAULT_USER
    target_fund_code = "001595"
    target_fund_name_keywords = ["天弘", "银行"] # Just for logging verification
    
    print(f"当前用户: {user.customer_name}")
    print(f"目标基金: {target_fund_code} (天弘中证银行ETF联接C)")
    
    # 1. 从定投计划中查找相关子账户
    print("-" * 50)
    print("正在查询定投计划以获取子账户信息...")
    
    target_sub_accounts = set()
    
    try:
        plans = getFundPlanList(target_fund_code, user)
        if plans:
            print(f"找到 {len(plans)} 个定投计划")
            for plan in plans:
                if plan.subAccountNo:
                    target_sub_accounts.add(plan.subAccountNo)
                    print(f"  关联子账户: {plan.subAccountName} ({plan.subAccountNo}) - 状态: {plan.status}")
        else:
            print(f"未找到基金 {target_fund_code} 的定投计划")
            
    except Exception as e:
        print(f"查询定投计划失败: {e}")
        logger.error(f"查询定投计划失败: {e}", exc_info=True)

    # 2. 也可以尝试从普通子账户列表中查找（作为补充）
    # print("正在检查普通子账户列表...")
    # response = getSubAccountList(user)
    # if response.Success and response.Data:
    #     for sub in response.Data:
    #         # 这里我们不知道哪个子账户有这个基金，只能遍历检查资产
    #         # 为了效率，我们只检查已经在计划中发现的，或者如果计划为空，可能需要全量检查
    #         # 但用户明确要求“在plan中找出”，所以我们主要依赖 plan
    #         pass

    if not target_sub_accounts:
        print("未找到任何关联子账户，无法执行卖出。")
        # Fallback: manually add the one we found in debug if needed, but let's trust the code first.
        # target_sub_accounts.add("27740154") 
        return

    print(f"\n共锁定 {len(target_sub_accounts)} 个目标子账户: {target_sub_accounts}")

    # 3. 遍历目标子账户执行卖出
    print("-" * 50)
    
    for sub_account_no in target_sub_accounts:
        print(f"\n正在处理子账户: {sub_account_no}")
        
        # 验证资产是否存在 (可选，但推荐)
        try:
            assets, _ = get_asset_list_of_sub(user, sub_account_no, with_meta=True)
            has_fund = False
            current_shares = 0.0
            
            if assets:
                for asset in assets:
                    if asset.fund_code == target_fund_code:
                        has_fund = True
                        current_shares = asset.available_vol
                        print(f"  确认持有基金: {asset.fund_name} ({asset.fund_code}), 可用份额: {current_shares}")
                        break
            
            if not has_fund:
                print(f"  子账户 {sub_account_no} 中未找到基金 {target_fund_code} 的资产，跳过")
                continue
                
        except Exception as e:
            print(f"  获取资产详情失败: {e}，尝试直接进行卖出检查")

        # 获取 0费率份额
        try:
            # 注意：get_0_fee_shares 可能返回该用户在该基金下的总0费率份额？还是特定子账户的？
            # 根据代码逻辑，getFee 似乎不区分子账户，或者是全局的。
            # 如果是全局的，我们需要小心不要卖多了。
            # 但是 sell_0_fee_shares 会检查 shares 列表，只卖出 shares 中有的。
            
            zero_fee_shares = get_0_fee_shares(user, target_fund_code)
            if zero_fee_shares is None:
                zero_fee_shares = 0.0
            
            print(f"  查询到 0费率份额: {zero_fee_shares}")

            if zero_fee_shares > 0:
                print(f"    准备卖出...")
                
                # 获取 Share 对象
                shares = get_bank_shares(user, sub_account_no, target_fund_code)
                if not shares:
                    print(f"    [警告] 未获取到 Share 对象列表 (get_bank_shares返回空)")
                    # 尝试重新获取或忽略
                else:
                    # 打印 share 详情
                    total_share_vol = sum(s.availableVol for s in shares)
                    print(f"    获取到 {len(shares)} 个份额记录，总可用: {total_share_vol}")
                    
                    # 执行卖出
                    # sell_0_fee_shares 内部会再次调用 get_0_fee_shares 并比较
                    result = sell_0_fee_shares(user, sub_account_no, target_fund_code, shares)
                    
                    if result:
                        # sell_0_fee_shares 返回 TradeResult 对象
                        if getattr(result, "status", 0) == 1:
                            print(f"    [成功] 卖出操作提交成功！")
                        else:
                            print(f"    [结果] 操作完成，状态: {getattr(result, 'status', 'Unknown')}")
                    else:
                        print(f"    [跳过] 未执行卖出 (可能是非交易时间、份额不足或出错)")
            else:
                print("    无 0费率份额，跳过")
                
        except Exception as e:
            print(f"    [异常] 处理子账户 {sub_account_no} 时出错: {e}")
            logger.error(f"处理卖出异常: {e}", exc_info=True)
            
        time.sleep(1)

if __name__ == "__main__":
    main()
