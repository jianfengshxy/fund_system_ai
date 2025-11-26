import os
import sys
from typing import Optional

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.db.database_connection import DatabaseConnection
from src.domain.user.User import User

class UserTokenStore:
    def __init__(self):
        self.db = DatabaseConnection()

    def ensure_table(self):
        sql = (
            "CREATE TABLE IF NOT EXISTS user_tokens ("
            "id BIGINT PRIMARY KEY AUTO_INCREMENT,"
            "account VARCHAR(32) NOT NULL UNIQUE,"
            "password_hash VARCHAR(64),"
            "customer_no VARCHAR(64),"
            "customer_name VARCHAR(128),"
            "c_token TEXT,"
            "u_token TEXT,"
            "passport_id VARCHAR(64),"
            "passport_ctoken TEXT,"
            "passport_utoken TEXT,"
            "index_zone INT,"
            "mobile_phone VARCHAR(32),"
            "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
            ") CHARACTER SET utf8mb4"
        )
        self.db.update(sql)

    def get(self, account: str) -> Optional[User]:
        self.ensure_table()
        rows = self.db.execute_query(
            "SELECT account,password_hash,customer_no,customer_name,c_token,u_token,passport_id,passport_ctoken,passport_utoken,index_zone,mobile_phone FROM user_tokens WHERE account=%s",
            (account,)
        )
        if not rows:
            return None
        row = rows[0]
        user = User(account=row.get("account"), password=None)
        user.customer_no = row.get("customer_no")
        user.customer_name = row.get("customer_name")
        user.c_token = row.get("c_token")
        user.u_token = row.get("u_token")
        user.passport_id = row.get("passport_id")
        user.passport_ctoken = row.get("passport_ctoken")
        user.passport_utoken = row.get("passport_utoken")
        user.index = row.get("index_zone")
        user.mobile_phone = row.get("mobile_phone")
        return user

    def upsert(self, user: User):
        self.ensure_table()
        sql = (
            "INSERT INTO user_tokens (account,password_hash,customer_no,customer_name,c_token,u_token,passport_id,passport_ctoken,passport_utoken,index_zone,mobile_phone) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE customer_no=VALUES(customer_no), customer_name=VALUES(customer_name), c_token=VALUES(c_token), u_token=VALUES(u_token), "
            "passport_id=VALUES(passport_id), passport_ctoken=VALUES(passport_ctoken), passport_utoken=VALUES(passport_utoken), index_zone=VALUES(index_zone), mobile_phone=VALUES(mobile_phone)"
        )
        password_hash = None
        self.db.update(sql, (
            getattr(user, "account", None),
            password_hash,
            getattr(user, "customer_no", None),
            getattr(user, "customer_name", None),
            getattr(user, "c_token", None),
            getattr(user, "u_token", None),
            getattr(user, "passport_id", None),
            getattr(user, "passport_ctoken", None),
            getattr(user, "passport_utoken", None),
            getattr(user, "index", None),
            getattr(user, "mobile_phone", None),
        ))

