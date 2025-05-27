from typing import Optional, List
from dataclasses import dataclass
from .fund_plan import FundPlan
from ..trade.share import Share

@dataclass
class FundPlanDetail:
    rationPlan: FundPlan
    profitTrends: List
    couponDetail: Optional[str]
    shares: List[Share]