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
             one_year_return, since_launch_return, product_rank, update_time, tracking_index,
             rank_100day, rank_30day, volatility, nav_5day_avg,
             season_item_rank, season_item_sc, month_item_rank, month_item_sc)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            fund_name = VALUES(fund_name),
            fund_type = VALUES(fund_type),
            fund_sub_type = VALUES(fund_sub_type),
            one_year_return = VALUES(one_year_return),
            since_launch_return = VALUES(since_launch_return),
            product_rank = VALUES(product_rank),
            update_time = VALUES(update_time),
            tracking_index = IFNULL(VALUES(tracking_index), tracking_index),
            rank_100day = IFNULL(VALUES(rank_100day), rank_100day),
            rank_30day = IFNULL(VALUES(rank_30day), rank_30day),
            volatility = IFNULL(VALUES(volatility), volatility),
            nav_5day_avg = IFNULL(VALUES(nav_5day_avg), nav_5day_avg),
            season_item_rank = IFNULL(VALUES(season_item_rank), season_item_rank),
            season_item_sc = IFNULL(VALUES(season_item_sc), season_item_sc),
            month_item_rank = IFNULL(VALUES(month_item_rank), month_item_rank),
            month_item_sc = IFNULL(VALUES(month_item_sc), month_item_sc)
        """
        params_list = [
            (update_date, ind.fund_code, ind.fund_name, ind.fund_type, ind.fund_sub_type,
             ind.one_year_return, ind.since_launch_return, ind.product_rank, ind.update_time, ind.tracking_index,
             getattr(ind, 'rank_100day', None), getattr(ind, 'rank_30day', None), getattr(ind, 'volatility', None), getattr(ind, 'nav_5day_avg', None),
             getattr(ind, 'season_item_rank', None), getattr(ind, 'season_item_sc', None), getattr(ind, 'month_item_rank', None), getattr(ind, 'month_item_sc', None))
            for ind in indicators
        ]
        self.db.insert_many(sql, params_list)

    def get_frequent_indicators(self, days: int = 5, threshold: int = 3) -> List[FundInvestmentIndicator]:
        recent_dates_sql = """
            SELECT DISTINCT update_date 
            FROM fund_investment_indicators 
            ORDER BY update_date DESC 
            LIMIT %s
        """
        recent_dates = self.db.execute_query(recent_dates_sql, (days,))
        print(f"DEBUG: Retrieved {len(recent_dates)} recent dates")  # 新增日志
        if recent_dates:
            print(f"DEBUG: Recent dates: {[row['update_date'] for row in recent_dates]}")  # 新增日志
        if not recent_dates:
            print("No recent dates available, returning empty list")  # 处理无数据情况
            return []
        
        date_list = [row['update_date'] for row in recent_dates]
        min_date = min(date_list)
        max_date = max(date_list)
        print(f"Min date: {min_date}, Max date: {max_date}")  # 现有日志
    
        # 查询在最近days个交易日内出现至少threshold次的基金
        # 不再要求必须出现在“全局最新日期”，改为取每只基金在窗口内自己的最新一条记录
        # 注意：此变更可能返回窗口期内而非绝对最新的数据，适用于追踪期内稳定出现的基金筛选
        sql = """
            SELECT t.*
            FROM fund_investment_indicators t
            JOIN (
                SELECT fund_code, MAX(update_date) AS max_ud
                FROM fund_investment_indicators
                WHERE update_date BETWEEN %s AND %s
                GROUP BY fund_code
                HAVING COUNT(DISTINCT update_date) >= %s
            ) m ON t.fund_code = m.fund_code AND t.update_date = m.max_ud
        """
        results = self.db.execute_query(sql, (min_date, max_date, threshold))
        print(f"Query results count: {len(results)}")  # 现有日志
        if results:
            print("DEBUG: Found funds details:")
            for row in results:
                print(f"  - Code: {row['fund_code']}, Name: {row.get('fund_name', 'N/A')}, Tracking Index: {row.get('tracking_index', 'N/A')}")
        
        return [FundInvestmentIndicator.from_dict(row) for row in results]
