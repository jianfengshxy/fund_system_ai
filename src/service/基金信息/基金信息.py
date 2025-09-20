import logging
from typing import Dict, List, Optional
import sys
import os

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import logging
from typing import Dict, List, Optional
from src.common.constant import DEFAULT_USER
from src.API.基金信息.FundInfo import getFundInfo, updateFundEstimatedValue
from src.API.基金信息.FundRank import get_nav_rank, get_fund_volatility as get_fund_volatility_api
from src.domain.fund.fund_info import FundInfo
from src.domain.user.User import User

# 用于缓存基金信息的字典，避免重复请求
fund_info_cache: Dict[str, FundInfo] = {}

logger = logging.getLogger(__name__)

def get_all_fund_info(user: User, fund_code: str) -> Optional[FundInfo]:
    """
    获取基金的完整信息，包括基础信息、估值信息、排名信息和波动率
    """
    # 第0步：从缓存中查找基金信息
    if fund_code in fund_info_cache:
        fund_info = fund_info_cache[fund_code]
        # 即便从缓存取，也要刷新估值信息
        try:
            updated_fund_info = updateFundEstimatedValue(fund_info)
            if updated_fund_info:
                fund_info = updated_fund_info
                fund_info_cache[fund_code] = fund_info  # 更新缓存
                # logger.debug(f"{fund_info.fund_name}刷新基金估值信息: 估算净值={fund_info.estimated_value}, 估算涨跌={fund_info.estimated_change}%")
            else:
                logger.warning(f"{fund_info.fund_name}刷新基金估值信息失败: {fund_code}")
        except Exception as e:
            logger.error(f"{fund_info.fund_name}刷新基金估值信息时发生异常: {str(e)}")
        return fund_info
    
    logger.debug(f"开始获取基金 {fund_code} 的完整信息")
    
    # 第1步：获取基金基础信息
    fund_info = getFundInfo(user, fund_code)
    if not fund_info:
        logger.error(f"获取基金基础信息失败: {fund_code}")
        return None
    
    logger.debug(f"{fund_info.fund_name}成功获取基金基础信息: {fund_info.fund_name}({fund_code})")
    
    # 第2步：获取基金估值信息
    try:
        updated_fund_info = updateFundEstimatedValue(fund_info)
        if updated_fund_info:
            fund_info = updated_fund_info
            logger.debug(f"{fund_info.fund_name}成功获取基金估值信息: 估算净值={fund_info.estimated_value}, 估算涨跌={fund_info.estimated_change}%")
        else:
            logger.warning(f"{fund_info.fund_name}获取基金估值信息失败: {fund_code}")
    except Exception as e:
        logger.error(f"{fund_info.fund_name}获取基金估值信息时发生异常: {str(e)}")
    
    # 第3步：获取基金30日排名信息
    try:
        rank_30 = get_nav_rank(user, fund_info, 30)
        if rank_30 is not None:
            fund_info.rank_30day = rank_30
            logger.debug(f"{fund_info.fund_name}成功获取基金30日排名信息: {rank_30}")
        else:
            logger.warning(f"{fund_info.fund_name}获取基金30日排名信息失败: {fund_code}")
    except Exception as e:
        logger.error(f"{fund_info.fund_name}获取基金30日排名信息时发生异常: {str(e)}")
    
    # 第4步：获取基金100日排名信息
    try:
        rank_100 = get_nav_rank(user, fund_info, 100)
        if rank_100 is not None:
            fund_info.rank_100day = rank_100
            logger.debug(f"{fund_info.fund_name}成功获取基金100日排名信息: {rank_100}")
        else:
            logger.warning(f"{fund_info.fund_name}获取基金100日排名信息失败: {fund_code}")
    except Exception as e:
        logger.error(f"{fund_info.fund_name}获取基金100日排名信息时发生异常: {str(e)}")
    
    # 第5步：获取基金30日波动率信息
    try:
        volatility_result = get_fund_volatility_api(user, fund_info, 30)
        if volatility_result is not None:
            _, _, volatility = volatility_result
            fund_info.volatility = volatility
            logger.debug(f"{fund_info.fund_name}成功获取基金30日波动率信息: {volatility}")
        else:
            logger.warning(f"{fund_info.fund_name}获取基金30日波动率信息失败: {fund_code}")
    except Exception as e:
        logger.error(f"{fund_info.fund_name}获取基金30日波动率信息时发生异常: {str(e)}")
    
    # 新增：第5.1步 获取近5日平均净值（用于与当日估值净值比较）
    try:
        nav5_result = get_fund_volatility_api(user, fund_info, 5)
        if nav5_result is not None:
            mean_5d, _, _ = nav5_result
            fund_info.nav_5day_avg = mean_5d
            logger.debug(f"{fund_info.fund_name}成功获取近5日平均净值: {mean_5d}")
        else:
            logger.warning(f"{fund_info.fund_name}获取近5日平均净值失败: {fund_code}")
    except Exception as e:
        logger.error(f"{fund_info.fund_name}获取近5日平均净值时发生异常: {str(e)}")
    
    # 打印基金跟踪的指数信息
    if hasattr(fund_info, 'index_code') and fund_info.index_code:
        logger.debug(f"{fund_info.fund_name}跟踪指数代码: {fund_info.index_code}")
    else:
        logger.debug(f"{fund_info.fund_name}未跟踪任何指数或指数代码为空")
    
    # 第6步：将基金信息加入缓存
    fund_info_cache[fund_code] = fund_info
    logger.debug(f"基金 {fund_code} {fund_info.fund_name}的完整信息已加入缓存")
    
    # 第7步：返回基金信息对象
    return fund_info

if __name__ == '__main__':
    fund_info = get_all_fund_info(DEFAULT_USER, '110026')
    # print(fund_info)
    pass