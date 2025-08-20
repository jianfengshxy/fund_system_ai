from abc import ABC, abstractmethod

from src.domain.fund.fund_info import FundInfo  # 假设已有FundInfo实体

class FundRepository(ABC):
    @abstractmethod
    def get_by_id(self, fund_id: str) -> FundInfo:
        pass

    @abstractmethod
    def save(self, fund: FundInfo):
        pass