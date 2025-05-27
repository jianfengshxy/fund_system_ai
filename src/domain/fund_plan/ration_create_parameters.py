from dataclasses import dataclass
from typing import List, Optional

@dataclass
class DiscountRate:
    lowerLimit: float
    upperLimit: float
    rate: float
    strRate: str
    discount: float
    strDiscount: str
    discountTips: Optional[str]

@dataclass
class RationCreateParameters:
    planStrategyList: List[str]
    buyStrategyList: List[str]
    redeemStrategyList: List[str]
    couponSelectList: List[str]
    allowRedeemToHqb: bool
    rationAutoPay: bool
    tjdAutoPay: bool
    naturalDate: str
    closeMarketTip: List[str]
    fundCode: str
    fundName: str
    fundType: str
    fundTypeTwo: str
    fundTypeName: str
    chargeTypeName: str
    fundRisk: str
    fundRiskName: str
    enableDt: bool
    financialType: str
    majorFundCode: str
    isHKFund: bool
    isHqbFund: bool
    isFinancialFund: bool
    isSpecialRateFund: bool
    supportSubAccount: bool
    minBusinLimit: str
    maxBusinLimit: str
    discountRateList: List[DiscountRate]
    orderNo: str
    forceRationCode: Optional[str]
    isSale: bool
    isSupportWitRation: bool