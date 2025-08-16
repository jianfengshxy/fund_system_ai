from src.db.database_connection import DatabaseConnection
from src.domain.fund.fund_repository import FundRepository
from src.domain.fund.fund_info import FundInfo

class FundRepositoryImpl(FundRepository):
    def __init__(self):
        self.db = DatabaseConnection()

    def get_by_id(self, fund_id: str) -> FundInfo:
        sql = "SELECT * FROM funds WHERE id = %s"  # 假设表名
        result = self.db.execute_query(sql, (fund_id,))
        if result:
            return FundInfo(**result[0])  # 映射到实体
        return None

    def save(self, fund: FundInfo):
        sql = "INSERT INTO funds (id, name) VALUES (%s, %s)"  # 示例
        self.db.insert(sql, (fund.id, fund.name))