from typing import Optional, List
from dataclasses import dataclass
from datetime import date

@dataclass
class FundPlan:
    def __init__(self, planId: str = '', fundCode: str = '', fundName: str = '', 
                 fundType: str = '', planState: str = '', planBusinessState: str = '',
                 pauseType: Optional[str] = None, planExtendStatus: str = '',
                 planType: str = '', periodType: int = 0, periodValue: int = 0,
                 amount: float = 0.0, bankAccountNo: str = '', payType: int = 0,
                 subAccountNo: str = '', subAccountName: str = '', currentDay: str = '',
                 buyStrategy: str = '', redeemStrategy: str = '', planAssets: float = 0.0,
                 rationProfit: Optional[float] = None, totalProfit: Optional[float] = None,
                 rationProfitRate: Optional[float] = None, totalProfitRate: Optional[float] = None,
                 unitPrice: Optional[float] = None, targetRate: Optional[str] = None,
                 retreatPercentage: Optional[str] = None, renewal: bool = False,
                 redemptionWay: int = 0, planStrategyId: str = '', redeemLimit: str = '',
                 financialType: Optional[str] = None, executedAmount: float = 0.0,
                 executedTime: int = 0, nextDeductDescription: str = '',
                 nextDeductDate: str = '', reTriggerDate: str = '',  # 添加 reTriggerDate 参数
                 recentDeductDate: str = '', bankCode: str = '',
                 showBankCode: str = '', shortBankCardNo: str = '',
                 subDisband: Optional[bool] = None, isGdlc: bool = False,
                 retriggerTips: str = '', isDeductDay: bool = False):
        self.planId = planId
        self.fundCode = fundCode
        self.fundName = fundName
        self.fundType = fundType
        self.planState = planState
        self.planBusinessState = planBusinessState
        self.pauseType = pauseType
        self.planExtendStatus = planExtendStatus
        self.planType = planType
        self.periodType = periodType
        self.periodValue = periodValue
        self.amount = amount
        self.bankAccountNo = bankAccountNo
        self.payType = payType
        self.subAccountNo = subAccountNo
        self.subAccountName = subAccountName
        self.reTriggerDate = reTriggerDate  # 添加 reTriggerDate 属性
        self.currentDay = currentDay
        self.buyStrategy = buyStrategy
        self.redeemStrategy = redeemStrategy
        self.planAssets = planAssets
        self.rationProfit = rationProfit
        self.totalProfit = totalProfit
        self.rationProfitRate = rationProfitRate
        self.totalProfitRate = totalProfitRate
        self.unitPrice = unitPrice
        self.targetRate = targetRate
        self.retreatPercentage = retreatPercentage
        self.renewal = renewal
        self.redemptionWay = redemptionWay
        self.planStrategyId = planStrategyId
        self.redeemLimit = redeemLimit
        self.financialType = financialType
        self.executedAmount = executedAmount
        self.executedTime = executedTime
        self.nextDeductDescription = nextDeductDescription
        self.nextDeductDate = nextDeductDate
        self.recentDeductDate = recentDeductDate
        self.bankCode = bankCode
        self.showBankCode = showBankCode
        self.shortBankCardNo = shortBankCardNo
        self.shares = []  

    @property
    def status(self) -> str:
        return f"{self.planState}-{self.planExtendStatus}" if self.planExtendStatus else str(self.planState)