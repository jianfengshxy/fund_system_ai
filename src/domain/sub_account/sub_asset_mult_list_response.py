from typing import List, Optional
from dataclasses import dataclass

@dataclass
class GroupType:
    group_type_name: str
    color: str

@dataclass
class SubAccountGroup:
    open_flag: str
    is_dissolving: bool
    race_id: Optional[str]
    on_way_trade_count: int
    on_way_trade_desc: Optional[str]
    sub_account_no: str
    group_name: str
    group_type: Optional[str]
    total_profit: str
    total_profit_rate: Optional[str]
    total_amount: str
    total_amount_decimal: float
    day_profit: str
    comment: Optional[str]
    score: str
    fund_updating: bool
    to_or_yes_day_profit: bool
    list_profit: Optional[str]
    group_types: List[GroupType]
    interval_profit_rate: str
    interval_profit_rate_name: str
    sub_account_explain: Optional[str]
    followed_sub_account_no: Optional[str]

@dataclass
class SubAssetMultListResponse:
    sub_bank_state: str
    group_card_tip: str
    sub_account_remark: str
    update: bool
    sub_account_asset: Optional[str]
    has_condition_trade: bool
    condition_trade_amount: str
    condition_trade_profit: str
    condition_trade_to_or_yes_day_profit: bool
    base_account_amount: str
    yesterday_profit: str
    list_group: List[SubAccountGroup]
    to_or_yes_day_profit: bool
    sub_total_amount: str