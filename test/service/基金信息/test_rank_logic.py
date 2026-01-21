
import requests
from typing import Optional

# Mock implementation of the logic found in FundRank.py
def mock_get_nav_rank(navs, current_nav):
    # Logic from FundRank.py
    # sorted_navs = [float(data.get('DWJZ', 0)) for data in datas if data.get('DWJZ') is not None]
    sorted_navs = list(navs)
    sorted_navs.append(current_nav)
    sorted_navs.sort()
    
    # rank = sorted_navs.index(current_nav) + 1
    rank = sorted_navs.index(current_nav) + 1
    
    return rank, sorted_navs

def test_rank_logic():
    # 模拟一组历史净值: 1.0, 1.1, 1.2, 1.3, 1.4 (一直在涨)
    history_navs = [1.0, 1.1, 1.2, 1.3, 1.4]
    
    # 情况A: 当前净值 0.9 (比历史都低 -> 暴跌)
    current_nav_low = 0.9
    rank_low, sorted_low = mock_get_nav_rank(history_navs, current_nav_low)
    print(f"当前净值 {current_nav_low} (创新低):")
    print(f"  排序后: {sorted_low}")
    print(f"  排名: {rank_low} (应该是 1)")
    
    # 情况B: 当前净值 1.5 (比历史都高 -> 创新高)
    current_nav_high = 1.5
    rank_high, sorted_high = mock_get_nav_rank(history_navs, current_nav_high)
    print(f"\n当前净值 {current_nav_high} (创新高):")
    print(f"  排序后: {sorted_high}")
    print(f"  排名: {rank_high} (应该是 N)")

if __name__ == "__main__":
    test_rank_logic()
