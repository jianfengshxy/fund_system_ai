import os
import sys
import logging
from typing import List, Dict, Any, Optional

# Ensure src is in path
if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.domain.user.User import User
from src.API.市场指数.获取市场指数 import get_market_index
from src.API.市场指数.指数资金流向 import get_index_money_flow

logger = get_logger("IndexHeatService")

def get_index_heat_rank(user: User, page_size: int = 50) -> List[Dict[str, Any]]:
    """
    获取指数资金热度排行
    1. 获取行业(001002)和主题(001003)指数
    2. 根据指数代码(INDEXCODE)去重，合并名称
    3. 查询每个唯一指数的资金流向数据
    4. 提取最新的 XLFLOW_SCORE (越大热度越高)
    5. 根据名称去重，保留分数最高的
    6. 按分数降序排序
    
    Args:
        user: User对象
        page_size: 每个类型获取的指数数量
        
    Returns:
        List[Dict[str, Any]]: 排序后的热度列表
    """
    logger.info("开始获取指数资金热度排行...")
    
    # 1. 获取指数列表
    indices = []
    
    # 获取主题指数
    logger.info("正在获取主题指数...")
    themes = get_market_index(user, type_code="001003", page_size=page_size)
    if themes:
        indices.extend(themes)
        
    # 获取行业指数
    logger.info("正在获取行业指数...")
    industries = get_market_index(user, type_code="001002", page_size=page_size)
    if industries:
        indices.extend(industries)
    
    # 2. 根据指数代码去重并合并名称
    unique_indices = {}
    for index in indices:
        # 优先使用 INDEXCODE，如果没有则使用 SEC_CODE
        index_code = index.get("INDEXCODE") or index.get("SEC_CODE")
        index_name = index.get("SEC_NAME")
        
        if not index_code:
            continue
            
        if index_code not in unique_indices:
            unique_indices[index_code] = {
                "names": set(),
                "original_data": index
            }
        
        if index_name:
            unique_indices[index_code]["names"].add(index_name)
            
    logger.info(f"共获取到 {len(indices)} 个指数，代码去重后剩余 {len(unique_indices)} 个，开始查询资金热度...")
    
    result_list = []
    
    # 3. 查询资金流向
    for i, (index_code, data) in enumerate(unique_indices.items()):
        # 合并名称
        merged_name = ",".join(sorted(list(data["names"])))
        
        try:
            flows = get_index_money_flow(user, index_code=index_code, range_type="n")
            
            if flows and len(flows) > 0:
                # 取最新的一条数据
                latest_flow = flows[-1]
                score_str = latest_flow.get("XLFLOW_SCORE")
                
                if score_str:
                    try:
                        score = float(score_str)
                        result_list.append({
                            "code": index_code,
                            "name": merged_name,
                            "score": score,
                            "date": latest_flow.get("PDATE"),
                            "change": latest_flow.get("CHGRT")
                        })
                    except ValueError:
                        logger.warning(f"指数 {merged_name} 分数转换失败: {score_str}")
        except Exception as e:
            logger.error(f"处理指数 {merged_name} ({index_code}) 异常: {e}")
            
    # 4. 根据名称去重 (保留分数最高的)
    unique_name_results = {}
    for item in result_list:
        name = item["name"]
        score = item["score"]
        
        if name not in unique_name_results:
            unique_name_results[name] = item
        else:
            # 如果当前分数更高，则替换
            if score > unique_name_results[name]["score"]:
                unique_name_results[name] = item
                
    final_results = list(unique_name_results.values())
    
    # 5. 排序 (分数降序)
    final_results.sort(key=lambda x: x["score"], reverse=True)
    
    logger.info(f"热度排行处理完成，名称去重后共 {len(final_results)} 个有效结果")
    return final_results

if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    from src.API.登录接口.login import ensure_user_fresh
    
    print("Refreshing user token...")
    user = ensure_user_fresh(DEFAULT_USER)
    
    print("\n--- Testing Index Heat Rank ---")
    # 测试时使用较小的 page_size 以减少等待时间
    test_page_size = 20
    print(f"Fetching top {test_page_size} themes and industries...")
    
    ranks = get_index_heat_rank(user, page_size=test_page_size)
    
    print(f"\n{'Rank':<5} {'Name':<30} {'Code':<10} {'Score':<10} {'Change':<10} {'Date':<15}")
    print("-" * 90)
    
    for i, item in enumerate(ranks):
        print(f"{i+1:<5} {item['name']:<30} {item['code']:<10} {item['score']:<10} {item['change']}%   {item['date']}")
