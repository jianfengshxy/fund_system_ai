import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.API.资产管理.getAssetListOfSub import get_asset_list_of_sub
from src.domain.user.User import User
from src.common.logger import get_logger

logger = get_logger(__name__)

# 候选基金列表 (基于2025年市场热点筛选：AI、半导体、黄金、新能源)
# 均为C类份额，高波动，高夏普潜力
CANDIDATES = [
    {
        "code": "012734",
        "name": "易方达中证人工智能主题ETF联接C",
        "sector": "人工智能/算力",
        "reason": "AI产业链核心，2025年算力需求持续爆发，高波动高成长，适合波段操作。"
    },
    {
        "code": "007301",
        "name": "国联安中证全指半导体ETF联接C",
        "sector": "半导体",
        "reason": "半导体国产替代加速，设备与材料环节高景气，行业Beta属性强，波动大。"
    },
    {
        "code": "008702",
        "name": "华夏中证沪深港黄金产业股票ETF联接C",
        "sector": "黄金/有色",
        "reason": "2025年贵金属牛市，黄金/有色板块具备高收益高波动特征，优于纯黄金ETF。"
    },
    {
        "code": "013180", 
        "name": "广发国证新能源电池主题ETF联接C",
        "sector": "新能源电池",
        "reason": "新能源车/储能需求回暖，电池板块弹性大，适合低位布局反弹。"
    },
    {
        "code": "025857",
        "name": "华夏中证电网设备主题ETF发起式联接C",
        "sector": "电网设备/特高压",
        "reason": "AI电力需求瓶颈，电网设备升级，新发基金热点，波动潜力大。"
    }
]

def select_funds(user_account, password, sub_account_name="快速止盈"):
    print(f"正在为用户 {user_account} 的组合 '{sub_account_name}' 遴选高波动C类基金...")
    
    # 1. 初始化用户
    user = User(user_account, password)
    
    # 2. 获取现有持仓以去重
    existing_codes = set()
    try:
        sub_account_no = getSubAccountNoByName(user, sub_account_name)
        if sub_account_no:
            print(f"成功获取组合ID: {sub_account_no}")
            assets = get_asset_list_of_sub(user, sub_account_no)
            if assets:
                print(f"现有持仓 ({len(assets)}支):")
                for asset in assets:
                    existing_codes.add(asset.fund_code)
                    print(f"  - {asset.fund_name} ({asset.fund_code})")
            else:
                print("现有持仓为空。")
        else:
            print(f"未找到组合 '{sub_account_name}'，将列出所有候选基金。")
    except Exception as e:
        print(f"获取现有持仓失败 (可能是网络或凭证问题): {e}")
        print("无法自动去重，请人工核对上述候选列表。")

    # 3. 筛选并输出推荐
    print("\n" + "="*50)
    print("【推荐买入基金列表】")
    print("筛选标准: C类指数基金 | 夏普率高 | 资金热点 | 波动率大")
    print("="*50)
    
    count = 0
    for cand in CANDIDATES:
        if cand['code'] in existing_codes:
            continue
            
        print(f"\n[{cand['sector']}] {cand['name']} ({cand['code']})")
        print(f"  推荐理由: {cand['reason']}")
        count += 1
        
    if count == 0:
        print("\n没有新的推荐基金 (所有候选基金均已在持仓中)。")
    else:
        print(f"\n共推荐 {count} 支基金。")

if __name__ == "__main__":
    # 默认使用施小雨账号 (需替换为真实密码或在运行环境中有有效Token)
    select_funds("13811574620", "123456")
