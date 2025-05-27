from dataclasses import dataclass

@dataclass
class Share:
    availableVol: float
    bankCode: str
    showBankCode: str
    bankCardNo: str
    bankName: str
    shareId: str
    bankAccountNo: str
    totalVol: float