# 模块顶层
import os
import sys

# 将项目根目录加入到 sys.path，确保可以 import src.**
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import logging
import re
from typing import List, Dict, Any, Optional

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.domain.fund_plan import ApiResponse
from src.domain.fund.fund_investment_indicator import FundInvestmentIndicator
from src.service.基金信息.基金信息 import get_all_fund_info
from src.API.大数据.加仓风向标 import getFundInvestmentIndicators as getBasicFundInvestmentIndicators
from src.db.fund_repository_impl import FundRepositoryImpl
from src.db.fund_investment_indicator_repository_impl import FundInvestmentIndicatorRepositoryImpl
from datetime import datetime
from src.API.资产管理.getAssetListOfSub import get_asset_list_of_sub
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.API.交易管理.feeMrg import getFee
from src.service.公共服务.redeem_fee_filter_service import is_high_frequency_index_fee_ok
from src.common.constant import DEFAULT_USER


from src.common.logger import get_logger
logger = get_logger("FundInvestmentIndicatorService")

def process_fund_investment_indicators(user, page_size=50) -> List[FundInvestmentIndicator]:
    """
    处理基金投资指标数据，按规则过滤并返回结果
    """
    
    try:
        # 调用API层获取基础数据
        api_response = getBasicFundInvestmentIndicators(user, page_size)
        
        if not api_response.Success:
            logger.error(f"API调用失败: {api_response.FirstError}")
            return []
        
        data = api_response.Data
        if data is None:
            logger.warning("API返回数据为空")
            return []
        
        # 获取类型为9的基金列表
        fund_list = data.get('9', [])
        if not fund_list:
            logger.warning("未找到加仓风向标基金数据")
            return []
        # print(f"{fund_list}")
        indicators = []
        for fund_data in fund_list:
            indicator = FundInvestmentIndicator.from_dict(fund_data)
            indicators.append(indicator)
        
        logger.info(f"=== 开始过滤处理，初始基金数量: {len(indicators)} ===")
        # 添加打印初始基金名称
        for ind in indicators:
            logger.info(f"初始基金: {ind.fund_name} ({ind.fund_code})")
        
        # === 步骤1: 仅保留基金名称中包含"C"的基金 ===
        indicators = [ind for ind in indicators if "C" in ind.fund_name]
        logger.info(f"=== 步骤1: 保留基金名包含'C'的基金，过滤后数量: {len(indicators)} ===")
        
        # === 步骤2: 多条件过滤规则 ===
        filtered_indicators = []
        
        for ind in indicators:
            # 规则1: 过滤掉包含"债"的基金
            if "债" in ind.fund_name:
                continue
            
            # 规则2: 过滤掉子类型 002003
            if ind.fund_sub_type == "002003":
                continue
            
            # 规则3: 仅保留基金类型在 [000,001,002]
            if ind.fund_type not in ["000", "001", "002"]:
                continue

            # 规则4: 当 fund_type == "000" 时，只保留 fund_sub_type == "000001"
            if ind.fund_type == "000" and ind.fund_sub_type != "000001":
                continue

            # 符合条件的保留
            filtered_indicators.append(ind)
        
        logger.info(f"=== 步骤2: 多条件过滤完成，过滤后数量: {len(filtered_indicators)} ===")
        
        # === 步骤3: 获取基金详细信息并进行index_code去重 ===
        logger.info("=== 步骤3: 获取基金详细信息并进行index_code去重 ===")
        
        # 为每个基金添加index_code信息
        # 新增：在此处先根据 six_month_return 是否有值进行“历史数据齐全/成立>=6个月”过滤
        age_ok_indicators = []
        for indicator in filtered_indicators:
            fund_info = get_all_fund_info(user, indicator.fund_code)
            if not fund_info:
                logger.info(f"剔除基金 {indicator.fund_name}({indicator.fund_code}): 无法获取基金详情，视为历史数据不全")
                continue

            six_month_return = getattr(fund_info, 'six_month_return', None)
            if six_month_return is None:
                logger.info(f"剔除基金 {indicator.fund_name}({indicator.fund_code}): six_month_return 无值，历史数据不全或成立不足6个月")
                continue

            # 历史数据齐全，保留并补充 index_code/tracking_index
            indicator.index_code = getattr(fund_info, 'index_code', None)
            indicator.tracking_index = indicator.index_code
            logger.info(f"基金 {indicator.fund_name}({indicator.fund_code}) 通过历史数据检查，index_code: {indicator.index_code}, tracking_index: {indicator.tracking_index}")
            age_ok_indicators.append(indicator)
        
        logger.info(f"=== 历史数据齐全过滤后基金数量: {len(age_ok_indicators)} ===")
        
        # 根据index_code进行去重（新增：优先保留组合中的已持有基金）
        try:
            sub_name = os.getenv("INDEX_FUNDS_SUB_ACCOUNT_NAME", "")
            sub_no = getSubAccountNoByName(user, sub_name)
            if not sub_no:
                logger.warning(f"未找到组合 {sub_name} 的账号，持仓优先去重失效")
                holdings = []
            else:
                holdings = get_asset_list_of_sub(user, sub_no)
            held_codes = {a.fund_code for a in holdings} if holdings else set()
            logger.info(f"已获取组合[{sub_name}]持仓基金数量: {len(held_codes)}（sub_account_no={sub_no}）")
        except Exception as e:
            logger.warning(f"获取组合持仓失败，退化为不考虑持仓优先: {e}")
            held_codes = set()

        # 先将无 index_code 的直接保留
        final_indicators: List[FundInvestmentIndicator] = []
        for ind in age_ok_indicators:
            if not getattr(ind, "index_code", None):
                final_indicators.append(ind)
                logger.info(f"保留无index_code基金: {ind.fund_name}({ind.fund_code})")
        
        # 对有 index_code 的按 index_code 分组
        grouped: Dict[str, List[FundInvestmentIndicator]] = {}
        for ind in age_ok_indicators:
            idx = getattr(ind, "index_code", None)
            if idx:
                grouped.setdefault(idx, []).append(ind)

        # 每个 index_code 只保留一个：优先保留已持有，其次 product_rank 最优
        for idx, group in grouped.items():
            group = [g for g in group if not any((g.fund_code == x.fund_code) for x in final_indicators)]
            if not group:
                continue

            held_group = [g for g in group if g.fund_code in held_codes]
            if held_group:
                chosen = min(held_group, key=lambda x: x.product_rank)
                reason = "按持仓优先保留"
            else:
                chosen = min(group, key=lambda x: x.product_rank)
                reason = "未持有该指数，按排名保留"

            final_indicators.append(chosen)
            logger.info(f"{reason}: {chosen.fund_name}({chosen.fund_code}) - index_code: {idx}")
            for g in group:
                if g.fund_code != chosen.fund_code:
                    logger.info(f"过滤重复index_code基金（优先保留已持有）: 被剔除 {g.fund_name}({g.fund_code}) - index_code: {idx}，保留: {chosen.fund_name}({chosen.fund_code})")
        
        logger.info(f"=== 步骤3: index_code去重后基金数量: {len(final_indicators)} ===")
        
        # 根据product_rank从小到大排序
        final_indicators.sort(key=lambda x: x.product_rank)
        
        return final_indicators
        
    except Exception as e:
        logger.error(f'处理加仓风向标基金信息失败: {str(e)}')
        import traceback
        logger.error(f"异常堆栈: {traceback.format_exc()}")
        return []


def save_fund_investment_indicators(user):
    indicators = process_fund_investment_indicators(user)  
    if not indicators:
        return
    # 从第一个指标的 update_time 提取 update_date
    update_time = indicators[0].update_time
    update_date = datetime.strptime(update_time, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')

    # 补齐新增字段并打印每只基金的关键字段
    from src.API.基金信息.FundRank import get_fund_growth_rate  # 就地导入，避免顶层改动
    for ind in indicators:
        # 获取完整基金信息（包含排名、波动率、近5日均值等）
        fund_info = get_all_fund_info(user, ind.fund_code)
        ind.rank_100day = getattr(fund_info, 'rank_100day', None)
        ind.rank_30day = getattr(fund_info, 'rank_30day', None)
        ind.volatility = getattr(fund_info, 'volatility', None)
        ind.nav_5day_avg = getattr(fund_info, 'nav_5day_avg', None)

        # 补齐 3Y 和 1Y(实际参数为 'Y') 的排名信息（分子/分母）
        season_rate, season_item_rank, season_item_sc = get_fund_growth_rate(fund_info, '3Y')
        month_rate, month_item_rank, month_item_sc = get_fund_growth_rate(fund_info, 'Y')  # 修复：'1Y' -> 'Y'
        # 若接口偶发缺数据返回 0/0，则不入库（置为 None，避免写入错误0值）
        if month_item_rank == 0 and month_item_sc == 0:
            month_item_rank, month_item_sc = None, None

        ind.season_item_rank = season_item_rank
        ind.season_item_sc = season_item_sc
        ind.month_item_rank = month_item_rank
        ind.month_item_sc = month_item_sc

        # 细粒度日志，便于确认补齐值
        logger.info(
            f"入库前补齐({ind.fund_code} {ind.fund_name}): "
            f"rank30={ind.rank_30day}, rank100={ind.rank_100day}, vol={ind.volatility}, nav5={ind.nav_5day_avg}, "
            f"season={ind.season_item_rank}/{ind.season_item_sc}, month={ind.month_item_rank}/{ind.month_item_sc}"
        )

    # 补齐完成统计
    fields = [
        'rank_30day', 'rank_100day', 'volatility', 'nav_5day_avg',
        'season_item_rank', 'season_item_sc', 'month_item_rank', 'month_item_sc'
    ]
    total = len(indicators)
    counts = {f: sum(1 for x in indicators if getattr(x, f, None) is not None) for f in fields}
    logger.info(
        "补齐完成统计: " +
        ", ".join([f"{f}={counts[f]}/{total}" for f in fields])
    )

    # 入库前质量统计与严格断言（可选）
    import os
    print(f"[质量统计] 待入库基金数: {total}")
    for f in (['tracking_index'] + fields):
        c = sum(1 for x in indicators if getattr(x, f, None) is not None)
        ratio = (c / total) if total > 0 else 0.0
        print(f"[质量统计] {f}: 非空 {c}/{total} ({ratio:.1%})")

    strict = os.environ.get('STRICT_QUALITY_CHECK', '0') == '1'
    critical_fields = ['rank_100day', 'rank_30day', 'volatility', 'season_item_rank', 'month_item_rank']
    if strict and all(sum(1 for x in indicators if getattr(x, f, None) is not None) == 0 for f in critical_fields):
        raise ValueError(f"质量断言失败：关键字段全部为空，终止入库。统计={counts}")

    # 仓库保存（本地实例化，避免作用域问题）
    from src.db.fund_investment_indicator_repository_impl import FundInvestmentIndicatorRepositoryImpl
    repo = FundInvestmentIndicatorRepositoryImpl()
    repo.save_investment_indicators(indicators, update_date)


# 添加缓存字典
_fund_indicators_cache = {}

def get_fund_investment_indicators(days=180, threshold=20, user=None) -> List[FundInvestmentIndicator]:
    user = user or DEFAULT_USER
    cache_key = f"{days}_{threshold}_{getattr(user, 'account', '')}"
    if cache_key in _fund_indicators_cache:
        get_logger(__name__).info(f"从缓存中获取基金投资指标: days={days}, threshold={threshold}")
        return _fund_indicators_cache[cache_key]
    
    repo = FundInvestmentIndicatorRepositoryImpl()
    indicators = repo.get_frequent_indicators(days, threshold)

    filtered_indicators: List[FundInvestmentIndicator] = []
    fee_cache: Dict[str, Dict] = {}
    allowed_types = {"000", "001", "002"}
    for ind in (indicators or []):
        fund_code = getattr(ind, "fund_code", "")
        fund_name = getattr(ind, "fund_name", fund_code)
        fund_type = getattr(ind, "fund_type", None)
        if fund_type not in allowed_types:
            get_logger(__name__).info(f"跳过{fund_name}({fund_code}): fund_type={fund_type} 不在[000,001,002]")
            continue

        rank_100 = getattr(ind, "rank_100day", None)
        if rank_100 is None:
            try:
                fund_info = get_all_fund_info(user, fund_code)
                rank_100 = getattr(fund_info, "rank_100day", None) if fund_info else None
                if rank_100 is not None:
                    ind.rank_100day = rank_100
            except Exception:
                rank_100 = None

        try:
            rank_100_num = float(rank_100) if rank_100 is not None else None
        except Exception:
            rank_100_num = None
        if rank_100_num is None or rank_100_num < 20 or rank_100_num > 80:
            get_logger(__name__).info(f"跳过{fund_name}({fund_code}): rank_100day={rank_100_num} 不在[20,80]")
            continue

        if fund_type == "000":
            try:
                key = str(fund_code)
                if key not in fee_cache:
                    fee_cache[key] = getFee(user, key)
                ok, reason = is_high_frequency_index_fee_ok(fee_cache.get(key))
                if not ok:
                    get_logger(__name__).info(f"跳过{fund_name}({fund_code}): 指数基金费率不满足高频要求({reason})")
                    continue
            except Exception as e:
                get_logger(__name__).warning(f"跳过{fund_name}({fund_code}): 指数基金费率查询失败({e})")
                continue

        filtered_indicators.append(ind)

    indicators = filtered_indicators

    if indicators:
        seen_indexes = set()
        unique_indicators = []
        for ind in indicators:
            if ind.tracking_index and ind.tracking_index not in seen_indexes:
                seen_indexes.add(ind.tracking_index)
                unique_indicators.append(ind)
            elif not ind.tracking_index:
                unique_indicators.append(ind)
        indicators = unique_indicators
        n = len(indicators)
        get_logger(__name__).info(f"按规则过滤并去重后基金数量: {n}")
        get_logger(__name__).info(f"按规则过滤并去重后基金列表(共{n}只):")
        for i, ind in enumerate(indicators, start=1):
            fund_code = getattr(ind, "fund_code", "")
            fund_name = getattr(ind, "fund_name", fund_code)
            get_logger(__name__).info(f"{i:02d}. {fund_name}({fund_code})")
    
    _fund_indicators_cache[cache_key] = indicators
    get_logger(__name__).info(f"已缓存基金投资指标: days={days}, threshold={threshold}")
    return indicators


if __name__ == "__main__":
    from common.constant import DEFAULT_USER
    
    try:
        indicators = process_fund_investment_indicators(DEFAULT_USER)
        
        if indicators:
            print(f"加仓风向标基金信息处理成功:")
            print(f"总共获取到 {len(indicators)} 条基金信息（已过滤）")
            print("-----------------------------------")
            
            for i, indicator in enumerate(indicators, 1):
                index_code = getattr(indicator, 'index_code', None)
                index_code_display = index_code if index_code else ""
                
                print(f"{i}. {indicator.fund_name} ({indicator.fund_code})")
                print(f"   排名: {indicator.product_rank}")
                print(f"   基金类型: {indicator.fund_type}")
                print(f"   基金子类型: {indicator.fund_sub_type}")
                print(f"   指数代码: {index_code_display}")
                print(f"   更新时间: {indicator.update_time}")
                print("-----------------------------------")
        else:
            print("处理加仓风向标基金信息失败或无数据返回")
    except Exception as e:
        print(f"执行过程中发生异常: {str(e)}")
