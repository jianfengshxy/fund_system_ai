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

    def get_frequent_indicators(self, days: int = 20, threshold: int = 3) -> List[FundInvestmentIndicator]:
        recent_dates_sql = """
            SELECT DISTINCT update_date 
            FROM fund_investment_indicators 
            ORDER BY update_date DESC 
            LIMIT %s
        """
        recent_dates = self.db.execute_query(recent_dates_sql, (days,))
        if not recent_dates or len(recent_dates) < days:
            print(f"No sufficient recent dates, returning empty list")  # 添加调试打印
            return []
    
        date_list = [row['update_date'] for row in recent_dates]
        min_date = min(date_list)
        max_date = max(date_list)
        print(f"Min date: {min_date}, Max date: {max_date}")  # 添加调试打印
    
        # 查询在最近days个日期内出现至少threshold次且在最新日期出现的基金
        sql = """
            SELECT * 
            FROM fund_investment_indicators 
            WHERE fund_code IN (
                SELECT fund_code 
                FROM fund_investment_indicators 
                WHERE update_date BETWEEN %s AND %s 
                GROUP BY fund_code 
                HAVING COUNT(DISTINCT update_date) >= %s
            ) AND update_date = %s
        """
        results = self.db.execute_query(sql, (min_date, max_date, threshold, max_date))
        print(f"Query results count: {len(results)}")  # 添加调试打印
    
        return [FundInvestmentIndicator.from_dict(row) for row in results]