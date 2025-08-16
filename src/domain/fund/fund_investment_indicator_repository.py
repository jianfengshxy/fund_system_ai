from abc import ABC, abstractmethod
from typing import List
from src.domain.fund.fund_investment_indicator import FundInvestmentIndicator

class FundInvestmentIndicatorRepository(ABC):
    @abstractmethod
    def save_investment_indicators(self, indicators: List[FundInvestmentIndicator], update_date: str):
        pass