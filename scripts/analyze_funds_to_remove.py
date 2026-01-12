import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.API.资产管理.getAssetListOfSub import get_asset_list_of_sub
from src.domain.user.User import User
from src.common.logger import get_logger

logger = get_logger(__name__)

def analyze_funds_to_remove(user_account, password, sub_account_name="快速止盈"):
    print(f"正在分析用户 {user_account} 的组合 '{sub_account_name}' 以筛选剔除目标...")
    
    user = User(user_account, password)
    
    try:
        sub_account_no = getSubAccountNoByName(user, sub_account_name)
        if not sub_account_no:
            print(f"未找到组合 '{sub_account_name}'")
            return

        assets = get_asset_list_of_sub(user, sub_account_no)
        if not assets:
            print("现有持仓为空。")
            return

        print(f"\n当前持仓 ({len(assets)}支):")
        print(f"{'基金名称':<25} | {'代码':<8} | {'持有收益率':<10} | {'持有金额':<10} | {'板块'}")
        print("-" * 85)

        # Categorize for analysis
        games = []
        comm_satellite = []
        low_performance = []
        high_profit = []

        for asset in assets:
            name = asset.fund_name
            code = asset.fund_code
            rate = asset.hold_profit_rate
            amt = asset.asset_value
            
            # Simple sector tagging based on name
            sector = "其他"
            if "游戏" in name:
                sector = "游戏"
                games.append(asset)
            elif "通信" in name or "卫星" in name:
                sector = "通信/卫星"
                comm_satellite.append(asset)
            elif "光伏" in name:
                sector = "光伏"
            elif "医药" in name or "药" in name:
                sector = "医药"
            elif "军工" in name:
                sector = "军工"
            elif "创业板" in name:
                sector = "创业板"
            elif "汽车" in name:
                sector = "智能汽车"
            
            print(f"{name[:25]:<25} | {code:<8} | {rate:>9.2f}% | {amt:>9.2f} | {sector}")

            if rate > 5.0: # Arbitrary threshold for "Fast Take Profit"
                high_profit.append(asset)
            if rate < -15.0:
                low_performance.append(asset)

        print("\n" + "="*50)
        print("【剔除/减仓建议】")
        print("="*50)

        # 1. Redundancy Check
        if len(games) > 1:
            print("\n1. ⚠️ 板块重复 (建议保留强者，剔除弱者或合并):")
            print("   检测到多只游戏动漫类基金。同质化严重，建议只保留一只。")
            for f in games:
                print(f"   - {f.fund_name} ({f.fund_code}): 收益率 {f.hold_profit_rate}%")

        if len(comm_satellite) > 1:
            print("\n2. ⚠️ 细分赛道重叠 (通信/卫星):")
            print("   卫星通信是通信的细分，存在重叠。")
            for f in comm_satellite:
                print(f"   - {f.fund_name} ({f.fund_code}): 收益率 {f.hold_profit_rate}%")

        # 2. Strategy: Fast Take Profit
        if high_profit:
            print("\n3. 💰 止盈机会 (符合“快速止盈”策略):")
            print("   以下基金收益较好，建议落袋为安，腾出资金布局新热点：")
            for f in high_profit:
                print(f"   - {f.fund_name} ({f.fund_code}): 收益率 {f.hold_profit_rate}%, 金额 {f.asset_value}")

        # 3. Strategy: Stop Loss / Weak Sector
        if low_performance:
            print("\n4. 📉 深度亏损/弱势板块 (需审视是否止损):")
            print("   以下基金亏损较多，若非长期看好，建议调仓换股：")
            for f in low_performance:
                print(f"   - {f.fund_name} ({f.fund_code}): 收益率 {f.hold_profit_rate}%")
                if "光伏" in f.fund_name:
                    print("     -> 点评: 光伏行业产能过剩尚未出清，短期反弹压力大。")
                if "医药" in f.fund_name:
                    print("     -> 点评: 医药板块长期磨底，反弹乏力，时间成本高。")

    except Exception as e:
        print(f"分析失败: {e}")

if __name__ == "__main__":
    analyze_funds_to_remove("13918199137", "sWX15706")
