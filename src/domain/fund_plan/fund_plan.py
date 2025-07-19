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
    
    def __str__(self) -> str:
        """返回定投计划的详细信息字符串表示"""
        profit_info = ""
        if self.rationProfit is not None and self.totalProfit is not None:
            profit_info = f"\n  定投收益: {self.rationProfit:.2f}元, 总收益: {self.totalProfit:.2f}元"
        elif self.rationProfit is not None:
            profit_info = f"\n  定投收益: {self.rationProfit:.2f}元"
        elif self.totalProfit is not None:
            profit_info = f"\n  总收益: {self.totalProfit:.2f}元"
        
        profit_rate_info = ""
        if self.rationProfitRate is not None and self.totalProfitRate is not None:
            profit_rate_info = f"\n  定投收益率: {self.rationProfitRate:.2%}, 总收益率: {self.totalProfitRate:.2%}"
        elif self.rationProfitRate is not None:
            profit_rate_info = f"\n  定投收益率: {self.rationProfitRate:.2%}"
        elif self.totalProfitRate is not None:
            profit_rate_info = f"\n  总收益率: {self.totalProfitRate:.2%}"
        
        target_info = ""
        if self.targetRate:
            target_info = f"\n  目标收益率: {self.targetRate}"
        if self.retreatPercentage:
            target_info += f", 回撤比例: {self.retreatPercentage}"
        
        return f"""定投计划详情:
  计划ID: {self.planId}
  基金代码: {self.fundCode}
  基金名称: {self.fundName}
  基金类型: {self.fundType}
  计划状态: {self.status}
  计划类型: {self.planType}
  定投金额: {self.amount:.2f}元
  定投周期: {self.periodType}({self.periodValue})
  子账户: {self.subAccountName}({self.subAccountNo})
  计划资产: {self.planAssets:.2f}元{profit_info}{profit_rate_info}{target_info}
  下次扣款: {self.nextDeductDate}
  银行卡: {self.shortBankCardNo}({self.showBankCode})"""
    def __repr__(self):
        return self.__str__()