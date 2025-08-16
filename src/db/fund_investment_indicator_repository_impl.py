from typing import List
from src.db.database_connection import DatabaseConnection
from src.domain.fund.fund_investment_indicator_repository import FundInvestmentIndicatorRepository
from src.domain.fund.fund_investment_indicator import FundInvestmentIndicator

class FundInvestmentIndicatorRepositoryImpl(FundInvestmentIndicatorRepository):
    def __init__(self):
        self.db = DatabaseConnection()

    def save_investment_indicators(self, indicators: List[FundInvestmentIndicator], update_date: str):
        sql = """
            INSERT INTO fund_investment_indicators 
            (update_date, fund_code, fund_name, fund_type, fund_sub_type, 
             one_year_return, since_launch_return, product_rank, update_time, tracking_index)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            fund_name = VALUES(fund_name),
            fund_type = VALUES(fund_type),
            fund_sub_type = VALUES(fund_sub_type),
            one_year_return = VALUES(one_year_return),
            since_launch_return = VALUES(since_launch_return),
            product_rank = VALUES(product_rank),
            update_time = VALUES(update_time),
            tracking_index = VALUES(tracking_index)
        """
        params_list = [
            (update_date, ind.fund_code, ind.fund_name, ind.fund_type, ind.fund_sub_type,
             ind.one_year_return, ind.since_launch_return, ind.product_rank, ind.update_time, ind.tracking_index)
            for ind in indicators
        ]
        self.db.insert_many(sql, params_list)