class AssetDetails:
    def __init__(self):
        self.fund_name = None
        self.fund_code = None
        self.fund_type = None
        self.hold_profit = None
        self.hold_profit_rate = None
        self.constant_profit = None
        self.constant_profit_rate = None
        self.profit_value = None
        self.daily_profit = None
        self.asset_value = None
        self.available_vol = None
        self.on_way_transaction_count = None
        self.asset_rank = None
        self.fund_nav = None
        self.nav_date = None
        self.nav_change = None      # 今日净值涨跌幅(%)
        self.tracked_index_code = None
        self.tracked_index_name = None
        self.primary_theme_code = None
        self.primary_theme_name = None
        self.latest_heat_score = None
        self.latest_heat_trade_date = None
        
    def to_dict(self):
        return {
            'fund_name': self.fund_name,
            'fund_code': self.fund_code,
            'fund_type': self.fund_type,
            'hold_profit': self.hold_profit,
            'hold_profit_rate': self.hold_profit_rate,
            'constant_profit': self.constant_profit,
            'constant_profit_rate': self.constant_profit_rate,
            'profit_value': self.profit_value,
            'daily_profit': self.daily_profit,
            'asset_value': self.asset_value,
            'available_vol': self.available_vol,
            'on_way_transaction_count': self.on_way_transaction_count,
            'asset_rank': self.asset_rank,
            'fund_nav': self.fund_nav,
            'nav_date': self.nav_date,
            'estimated_change': getattr(self, 'estimated_change', 0.0), # 确保 estimated_change 存在
            'nav_change': getattr(self, 'nav_change', None),             # 今日净值涨跌幅(%)
            'tracked_index_code': getattr(self, 'tracked_index_code', None),
            'tracked_index_name': getattr(self, 'tracked_index_name', None),
            'primary_theme_code': getattr(self, 'primary_theme_code', None),
            'primary_theme_name': getattr(self, 'primary_theme_name', None),
            'latest_heat_score': getattr(self, 'latest_heat_score', None),
            'latest_heat_trade_date': getattr(self, 'latest_heat_trade_date', None),
        }

    def __str__(self):
        return f"""AssetDetails(
            fund_name={self.fund_name},
            fund_code={self.fund_code},
            fund_type={self.fund_type},
            hold_profit={self.hold_profit},
            hold_profit_rate={self.hold_profit_rate},
            constant_profit={self.constant_profit},
            constant_profit_rate={self.constant_profit_rate},
            profit_value={self.profit_value},
            daily_profit={self.daily_profit},
            asset_value={self.asset_value},
            available_vol={self.available_vol},
            on_way_transaction_count={self.on_way_transaction_count},
            asset_rank={self.asset_rank},
            fund_nav={self.fund_nav},
            nav_date={self.nav_date}
        )"""
