from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class FundInvestmentIndicator:
    """加仓风向标基金信息类"""
    fund_code: str = ''                  # 基金代码 FCODE
    fund_name: str = ''                  # 基金名称 SHORTNAME
    fund_type: str = ''                  # 基金类型 RSFUNDTYPE
    fund_sub_type: str = ''              # 基金子类型 RSBTYPE
    one_year_return: float = 0.0         # 一年收益率 SYL_1N
    since_launch_return: float = 0.0     # 成立以来收益率 SYL_LN
    product_rank: float = 0.0            # 产品排名 PRODUCT_RANK
    update_date: str = ''                # 更新日期 update_date
    update_time: str = ''                # 更新时间 update_time
    tracking_index: Optional[str] = None # 追踪指数（可选）
    # 新增：基金更多信息（来自 get_all_fund_info）与排名分母信息（来自 get_fund_growth_rate）
    rank_100day: Optional[int] = None
    rank_30day: Optional[int] = None
    volatility: Optional[float] = None
    nav_5day_avg: Optional[float] = None
    season_item_rank: Optional[int] = None
    season_item_sc: Optional[int] = None
    month_item_rank: Optional[int] = None
    month_item_sc: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FundInvestmentIndicator':
        """从字典创建对象"""
        # 安全地转换数值，处理None值
        def safe_float(value, default=0.0):
            if value is None or value == '':
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
        # 新增：安全的整数转换
        def safe_int(value, default=None):
            if value is None or value == '':
                return default
            try:
                return int(value)
            except (ValueError, TypeError):
                return default
        
        # 支持小写和API大写键
        fund_code = data.get('fund_code') or data.get('FCODE', '')
        fund_name = data.get('fund_name') or data.get('SHORTNAME', '')
        fund_type = data.get('fund_type') or data.get('RSFUNDTYPE', '')
        fund_sub_type = data.get('fund_sub_type') or data.get('RSBTYPE', '')
        one_year_return = safe_float(data.get('one_year_return') or data.get('SYL_1N'))
        since_launch_return = safe_float(data.get('since_launch_return') or data.get('SYL_LN'))
        product_rank = safe_float(data.get('product_rank') or data.get('PRODUCT_RANK'))
        update_date = (data.get('update_date') or data.get('EUTIME', '').split(' ')[0])
        update_time = data.get('update_time') or data.get('EUTIME', '')
        tracking_index = data.get('tracking_index') or data.get('tracking_index', None)

        # 新增字段的容错取值（查询时 SELECT * 会返回这些列；旧数据或旧表结构可能缺失）
        rank_100day = safe_int(data.get('rank_100day'))
        rank_30day = safe_int(data.get('rank_30day'))
        volatility = safe_float(data.get('volatility'), default=None)
        nav_5day_avg = safe_float(data.get('nav_5day_avg'), default=None)
        season_item_rank = safe_int(data.get('season_item_rank'))
        season_item_sc = safe_int(data.get('season_item_sc'))
        month_item_rank = safe_int(data.get('month_item_rank'))
        month_item_sc = safe_int(data.get('month_item_sc'))

        return cls(
            fund_code=fund_code,
            fund_name=fund_name,
            fund_type=fund_type,
            fund_sub_type=fund_sub_type,
            one_year_return=one_year_return,
            since_launch_return=since_launch_return,
            product_rank=product_rank,
            update_date=update_date,
            update_time=update_time,
            tracking_index=tracking_index,
            # 新增字段
            rank_100day=rank_100day,
            rank_30day=rank_30day,
            volatility=volatility,
            nav_5day_avg=nav_5day_avg,
            season_item_rank=season_item_rank,
            season_item_sc=season_item_sc,
            month_item_rank=month_item_rank,
            month_item_sc=month_item_sc
        )
    
    def __str__(self) -> str:
        """返回基金信息的字符串表示"""
        return f"FundInvestmentIndicator(fund_code={self.fund_code}, fund_name={self.fund_name}, product_rank={self.product_rank})"