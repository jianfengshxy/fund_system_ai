from dataclasses import dataclass
from typing import List, Optional
from .fund_plan import FundPlan
from ..trade.share import Share

@dataclass
class FundPlanDetail:
    rationPlan: FundPlan
    profitTrends: List
    couponDetail: Optional[str]
    shares: List[Share]    
    def __str__(self) -> str:
        """打印基金计划详情的所有信息"""
        shares_info = '\n'.join([f'    {share}' for share in self.shares]) if self.shares else '    无份额信息'
        trends_info = '\n'.join([f'    {trend}' for trend in self.profitTrends]) if self.profitTrends else '    无收益趋势数据'
        
        return f"""基金计划详情:
配置计划:
    {self.rationPlan}
收益趋势:
{trends_info}
优惠券详情: {self.couponDetail if self.couponDetail else '无'}
份额信息:
{shares_info}"""
