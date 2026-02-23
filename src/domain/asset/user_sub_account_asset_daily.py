from dataclasses import dataclass
from datetime import date

@dataclass
class UserSubAccountAssetDaily:
    customer_no: str
    sub_account_no: str  # Empty string for Base Account
    sub_account_name: str
    date: date
    
    asset_value: float = 0.0
    hold_profit: float = 0.0
    daily_profit: float = 0.0
    total_profit: float = 0.0
    
    # Optional: Source type (1=Base, 2=UserSub, 3=PlanSub)
    source_type: int = 0
    
    def to_dict(self):
        return {
            "customer_no": self.customer_no,
            "sub_account_no": self.sub_account_no,
            "sub_account_name": self.sub_account_name,
            "date": self.date,
            "asset_value": self.asset_value,
            "hold_profit": self.hold_profit,
            "daily_profit": self.daily_profit,
            "total_profit": self.total_profit,
            "source_type": self.source_type
        }
