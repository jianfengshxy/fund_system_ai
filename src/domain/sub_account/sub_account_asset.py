from domain.asset.asset_details import *

class SubAccountAsset:
    def __init__(self):
        # self.asset_value = None
        # self.daily_profit = None
        # self.hold_profit = None
        # self.constant_profit = None
        # self.profit_value = None
        # self.to_or_yes_day_profit = None
        # self.updating = None
        # self.stay_way_count = None
        # self.total_count = None
        self.asset_details = []
        
    def add_asset_detail(self, asset_detail):
        self.asset_details.append(asset_detail)