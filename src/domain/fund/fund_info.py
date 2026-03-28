from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class FundInfo:
    """基金信息类"""
    # 基本信息
    fund_code: str                      # 基金代码 FCODE
    fund_name: str                      # 基金名称 SHORTNAME
    fund_type: str                      # 基金类型 RSFUNDTYPE
    
    # 净值信息
    nav: float                          # 当前净值 NAV
    acc_nav: float                      # 累计净值 ACCNAV
    nav_date: str                       # 净值日期 PDATE
    nav_change: float                   # 净值变化率 NAVCHGRT
    
    # 估值信息
    estimated_value: Optional[float]     # 估算净值 GSZ
    estimated_change: Optional[float]    # 估算涨跌幅 GSZZL
    estimated_time: Optional[str]        # 估算时间 GZTIME
    
    # 收益率信息
    week_return: Optional[float]         # 近一周收益率 SYL_Z
    month_return: Optional[float]        # 近一月收益率 SYL_Y
    three_month_return: Optional[float]  # 近三月收益率 SYL_3Y
    six_month_return: Optional[float]    # 近六月收益率 SYL_6Y
    year_return: Optional[float]         # 近一年收益率 SYL_1N
    this_year_return: Optional[float]    # Come来收益率 SYL_JN
    
    # 交易信息
    max_purchase: float                  # 最大申购金额 MAXSG
    can_purchase: bool                   # 是否可以购买 ISBUY
    can_redeem: bool                     # 是否可以赎回 (derived from ISBUY)
    
    # 其他信息
    index_code: Optional[str]            # 跟踪指数代码 INDEXCODE
    tracking_error: Optional[float]      # 跟踪误差 TRKERROR1   
    rank_100day: Optional[int]             # 近100日排名 RANK_100DAY
    rank_30day: Optional[int]              # 近30日排名 RANK_30DAY
    volatility: Optional[float]           # 波动率 VOLATILITY
    # 新增：近5日平均净值（由历史净值计算得到，用于与当日估值净值比较）
    nav_5day_avg: Optional[float] = None
    fund_sub_type: str = ''



    @classmethod
    def from_dict(cls, data):
        """
        从字典创建FundInfo对象
        Args:
            data: API返回的基金信息字典
        Returns:
            FundInfo对象
        """
        def safe_float(value, default=0.0):
            """安全地将值转换为浮点数"""
            if value is None or value == '' or (isinstance(value, str) and value.strip() == '--'):
                return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default

        return cls(
            fund_code=data.get('FCODE', ''),
            fund_name=data.get('SHORTNAME', ''),
            fund_type=data.get('RSFUNDTYPE', ''),
            nav=safe_float(data.get('NAV')),
            acc_nav=safe_float(data.get('ACCNAV')),
            nav_date=data.get('PDATE', ''),
            nav_change=safe_float(data.get('NAVCHGRT')),
            estimated_value=safe_float(data.get('GSZ'), None),
            estimated_change=safe_float(data.get('GSZZL'), None),
            estimated_time=data.get('GZTIME'),
            week_return=safe_float(data.get('SYL_Z'), None),
            month_return=safe_float(data.get('SYL_Y'), None),
            three_month_return=safe_float(data.get('SYL_3Y'), None),
            six_month_return=safe_float(data.get('SYL_6Y'), None),
            year_return=safe_float(data.get('SYL_1N'), None),
            this_year_return=safe_float(data.get('SYL_JN'), None),
            max_purchase=safe_float(data.get('MAXSG')),
            can_purchase=data.get('ISBUY') == '1',
            can_redeem=data.get('ISBUY') in ['1', '4'], # 1:可申购赎回, 4:暂停申购但可赎回
            index_code=data.get('INDEXCODE'),
            tracking_error=safe_float(data.get('TRKERROR1'), None),
            rank_100day = 0,
            rank_30day = 0 ,
            volatility = 0.0,
            nav_5day_avg = None,
            fund_sub_type=data.get('RSBTYPE', '')
        )

    def __str__(self) -> str:
        """返回基金信息的字符串表示"""
        # 格式化收益率显示
        def format_return(value):
            return f"{value}%" if value is not None else "暂无"
        
        # 格式化估值信息
        estimated_info = "暂无"
        if self.estimated_value:
            estimated_info = f"{self.estimated_value} ({self.estimated_change}% {self.estimated_time})"
        
        return (
            f"基金名称: {self.fund_name} ({self.fund_code})\n"
            f"基金类型: {self.fund_type}\n"
            f"基金子类型: {self.fund_sub_type or '暂无'}\n"
            f"净值信息:\n"
            f"  当前净值: {self.nav} ({self.nav_date})\n"
            f"  累计净值: {self.acc_nav}\n"
            f"  日涨跌幅: {self.nav_change}%\n"
            f"估值信息: {estimated_info}\n"
            f"收益率信息:\n"
            f"  近一周: {format_return(self.week_return)}\n"
            f"  近一月: {format_return(self.month_return)}\n"
            f"  近三月: {format_return(self.three_month_return)}\n"
            f"  近六月: {format_return(self.six_month_return)}\n"
            f"  近一年: {format_return(self.year_return)}\n"
            f"  今年来: {format_return(self.this_year_return)}\n"
            f"交易信息:\n"
            f"  最大申购金额: {self.max_purchase:,.2f}元\n"
            f"  是否可购买: {'是' if self.can_purchase else '否'}\n"
            f"  是否可赎回: {'是' if self.can_redeem else '否'}\n"
            f"指数信息:\n"
            f"  跟踪指数: {self.index_code or '暂无'}\n"
            f"  跟踪误差: {f'{self.tracking_error:.4f}%' if self.tracking_error is not None else '暂无'}\n"
            f"排名信息:\n"
            f"  近30日排名: {self.rank_30day if self.rank_30day is not None else '暂无'}\n"
            f"  近100日排名: {self.rank_100day if self.rank_100day is not None else '暂无'}\n"
            f"风险指标:\n"
            f"  波动率: {f'{self.volatility:.2f}%' if self.volatility is not None else '暂无'}"
        )

        
