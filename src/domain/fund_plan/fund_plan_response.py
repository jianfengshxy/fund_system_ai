from dataclasses import dataclass
from .page_info import PageInfo

@dataclass
class FundPlanResponse:
    fundCode: str
    fundName: str
    pageInfo: PageInfo