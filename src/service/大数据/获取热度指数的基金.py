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
from src.service.大数据.获取指数资金热度 import get_index_heat_rank
from src.API.市场指数.获取追踪指数的基金 import get_tracking_funds
from src.API.市场指数.指数资金流向 import get_index_money_flow

logger = get_logger("HeatIndexFundService")

def calculate_slope(values: List[float]) -> float:
    """
    计算线性回归斜率
    """
    n = len(values)
    if n < 2:
        return 0.0
    
    x = list(range(n))
    y = values
    
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(i * j for i, j in zip(x, y))
    sum_xx = sum(i * i for i in x)
    
    # m = (N * Σ(xy) - Σx * Σy) / (N * Σ(x^2) - (Σx)^2)
    numerator = n * sum_xy - sum_x * sum_y
    denominator = n * sum_xx - sum_x ** 2
    
    if denominator == 0:
        return 0.0
        
    return numerator / denominator

def check_money_flow_trend(user: User, index_code: str) -> bool:
    """
    检查指数资金流向趋势
    要求：5日和10日资金流向都是净流入加大（趋势向上）
    """
    try:
        # 获取资金流向数据
        flows = get_index_money_flow(user, index_code=index_code)
        
        if not flows or len(flows) < 10:
            # 数据不足10天，无法判断10日趋势，保守起见返回False
            # 或者如果数据不足但有5天，可以降级？这里严格按要求执行
            return False
            
        # 提取资金流向得分
        scores = []
        for item in flows:
            try:
                scores.append(float(item.get("XLFLOW_SCORE", 0)))
            except (ValueError, TypeError):
                scores.append(0.0)
                
        # 检查10日趋势
        last_10_scores = scores[-10:]
        slope_10 = calculate_slope(last_10_scores)
        
        # 检查5日趋势
        last_5_scores = scores[-5:]
        slope_5 = calculate_slope(last_5_scores)
        
        # 都是净流入加大（斜率大于0）
        # 考虑到浮点数精度，用 > 0.001
        is_increasing = slope_5 > 0 and slope_10 > 0
        
        if is_increasing:
            logger.info(f"指数 {index_code} 资金流向趋势符合要求 (Slope5={slope_5:.2f}, Slope10={slope_10:.2f})")
        
        return is_increasing
        
    except Exception as e:
        logger.error(f"检查指数 {index_code} 资金流向异常: {e}")
        return False

def get_heat_index_funds(user: User, top_n: int = 50) -> List[Dict[str, Any]]:
    """
    获取热度指数对应的优选基金
    1. 获取热度指数排行
    2. 遍历指数，获取追踪该指数的基金
    3. 筛选条件：
       - 指数基金的C类份额 (ISCLASSC == 1)
       - 费率只有{0, 1.5}两档位 (通过 SHRATE7 == 0 判断，即持有7天免赎回费)
    4. 如果有多个符合条件的基金，选择第一个
    
    Args:
        user: User对象
        top_n: 获取前N个热度指数
        
    Returns:
        List[Dict[str, Any]]: 基金列表，包含指数信息和选中的基金信息
    """
    logger.info(f"开始获取前 {top_n} 个热度指数对应的优选基金...")
    
    # 1. 获取热度指数
    heat_ranks = get_index_heat_rank(user, page_size=top_n)
    
    # 截取前 top_n 个 (虽然 get_index_heat_rank 的 page_size 控制了获取数量，但去重后数量可能会变，且为了保险再次截取)
    # 注意：get_index_heat_rank 返回的是去重后的列表，page_size 是传给 API 的，所以返回数量可能小于 2*page_size
    # 这里我们只处理前 top_n 个热度最高的
    target_indices = heat_ranks[:top_n]
    
    results = []
    
    logger.info(f"已获取热度指数排行，开始筛选基金...")
    
    for i, index in enumerate(target_indices):
        index_code = index.get("code")
        index_name = index.get("name")
        index_score = index.get("score")
        
        if not index_code:
            continue
            
        # 额外筛选：热度分数需大于 50.0
        try:
            if float(index_score) <= 50.0:
                continue
        except (ValueError, TypeError):
            continue
            
        try:
            # 2. 检查资金流向趋势 (5日、10日净流入加大)
            if not check_money_flow_trend(user, index_code):
                # logger.info(f"指数 {index_name} ({index_code}) 资金流向趋势不符合要求，跳过")
                continue
                
            # 3. 获取追踪基金
            # logger.info(f"[{i+1}/{len(target_indices)}] 正在查询指数 {index_name} ({index_code}) 的追踪基金...")
            funds = get_tracking_funds(user, index_code=index_code, page_size=50)
            
            # 4. 筛选基金
            selected_fund = None
            
            for fund in funds:
                # 检查是否为 C 类份额
                is_class_c = False
                val_c = fund.get("ISCLASSC")
                if val_c == 1 or val_c == 1.0 or val_c == "1":
                    is_class_c = True
                
                if not is_class_c:
                    continue
                
                # 检查费率 (SHRATE7 == 0 表示7天赎回费为0，通常对应 {0, 1.5} 两档费率)
                # 1.5% (<7天), 0% (>=7天)
                shrate7 = fund.get("SHRATE7")
                is_low_fee = False
                try:
                    if float(shrate7) == 0:
                        is_low_fee = True
                except (ValueError, TypeError):
                    pass
                
                if is_low_fee:
                    selected_fund = fund
                    break # 找到第一个就退出
            
            if selected_fund:
                logger.info(f"指数 {index_name} 选中基金: {selected_fund.get('SHORTNAME')} ({selected_fund.get('FCODE')})")
                results.append({
                    "index_name": index_name,
                    "index_code": index_code,
                    "index_score": index_score,
                    "fund_name": selected_fund.get("SHORTNAME"),
                    "fund_code": selected_fund.get("FCODE"),
                    "fund_nav": selected_fund.get("ENDNAV"), # 规模
                    "fund_1y_return": selected_fund.get("SYL_1N"), # 近1年收益
                    "shrate7": selected_fund.get("SHRATE7")
                })
            else:
                logger.warning(f"指数 {index_name} ({index_code}) 未找到符合条件(C类且7天免赎回费)的基金")
                
        except Exception as e:
            logger.error(f"处理指数 {index_name} ({index_code}) 基金筛选时异常: {e}")
            
    logger.info(f"处理完成，共选中 {len(results)} 只基金")
    return results

if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    from src.API.登录接口.login import ensure_user_fresh
    
    print("Refreshing user token...")
    user = ensure_user_fresh(DEFAULT_USER)
    
    print("\n--- Testing Heat Index Funds Selection ---")
    # 获取前 5 个热度指数的基金进行测试
    selected_funds = get_heat_index_funds(user, top_n=50)
    
    print(f"\n{'Index Name':<20} {'Score':<8} {'Fund Name':<30} {'Code':<10} {'1Y Return':<10}")
    print("-" * 90)
    
    for item in selected_funds:
        # 处理中文对齐
        idx_name = item['index_name']
        fund_name = item['fund_name']
        
        # 简单截断过长的名称以便显示
        if len(fund_name) > 20:
            fund_name = fund_name[:18] + ".."
            
        print(f"{idx_name:<20} {item['index_score']:<8} {fund_name:<30} {item['fund_code']:<10} {item['fund_1y_return']}%")
