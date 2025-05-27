class SubAccount:
    def __init__(self, customer_no, sub_account_no, sub_account_name, total_profit=None, total_profit_rate=None, total_amount=None):
        self.customer_no = customer_no
        self.sub_account_no = sub_account_no
        self.sub_account_name = sub_account_name
        self.total_profit = total_profit
        self.total_profit_rate = total_profit_rate
        self.total_amount = total_amount
        self.asset_value = 0.0
        self.daily_profit = 0.0
        self.hold_profit = 0.0
        self.constant_profit = 0.0
        self.profit_value = 0.0
        self.to_or_yes_day_profit = 0.0
        self.updating = False
        self.stay_way_count = 0
        self.total_count = 0
        self.budget = 1.0
        self.hold_rate = None
        self.asset_details = []
        self.asset_counts = 0
        # 新增字段
        self.open_flag = None
        self.is_dissolving = False
        self.group_type = None
        self.score = None
        self.group_types = []
        self.interval_profit_rate = None
        self.interval_profit_rate_name = None
        self.sub_account_explain = None
        self.followed_sub_account_no = None
        self.on_way_trade_count = 0
        self.on_way_trade_desc = None

    def add_asset_detail(self, asset_detail):
        self.asset_details.append(asset_detail)

    def __str__(self):
        base_info = f"""SubAccount(
            customer_no={self.customer_no},
            sub_account_no={self.sub_account_no},
            sub_account_name={self.sub_account_name},
            total_profit={self.total_profit},
            total_profit_rate={self.total_profit_rate},
            total_amount={self.total_amount},
            asset_value={self.asset_value},
            daily_profit={self.daily_profit},
            hold_profit={self.hold_profit},
            constant_profit={self.constant_profit},
            profit_value={self.profit_value},
            to_or_yes_day_profit={self.to_or_yes_day_profit},
            updating={self.updating},
            stay_way_count={self.stay_way_count},
            total_count={self.total_count},
            budget={self.budget},
            hold_rate={self.hold_rate},
            asset_counts={self.asset_counts},
            open_flag={self.open_flag},
            is_dissolving={self.is_dissolving},
            group_type={self.group_type},
            score={self.score},
            group_types={self.group_types},
            interval_profit_rate={self.interval_profit_rate},
            interval_profit_rate_name={self.interval_profit_rate_name},
            sub_account_explain={self.sub_account_explain},
            followed_sub_account_no={self.followed_sub_account_no},
            on_way_trade_count={self.on_way_trade_count},
            on_way_trade_desc={self.on_way_trade_desc}
        )"""
        asset_details_str = "Asset Details:\n        {' '.join([str(asset_detail) for asset_detail in self.asset_details])}"
        return base_info + "\n        " + asset_details_str
    
    @classmethod
    def from_basic_info(cls, customer_no, sub_account_no, sub_account_name):
        return cls(customer_no, sub_account_no, sub_account_name)
      

# 示例用法
# sub_account = SubAccount("cd0b7906b53b43ffa508a99744b4055b", "2002334319", "子账户1", 1000, 0.05, 5000)
# print(sub_account.sub_account_name)  # 输出: 子账户1
