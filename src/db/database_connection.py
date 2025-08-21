import os
import mysql.connector
from mysql.connector import pooling
from mysql.connector import Error

class DatabaseConnection:
    def __init__(self, pool_size=10):
        if 'FC_FUNCTION_NAME' in os.environ:
            self.dbconfig = {
                'host': os.environ.get('INTERNAL_HOST', 'rm-uf614tc8841ee6nwi.rwlb.rds.aliyuncs.com'),
                'port': int(os.environ.get('DB_PORT', 3306)),
                'user': os.environ.get('DB_USER', 'jianfengshxy'),
                'password': os.environ.get('DB_PASSWORD', 'jianfeng1984Aa+'),
                'database': os.environ.get('DB_NAME', 'kuafudb'),
                'charset': 'utf8mb4'
            }
        else:
            import yaml
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 's.yaml')
            with open(config_path, 'r') as file:
                config = yaml.safe_load(file)
            db_config = config['vars']['common']['database']
            self.dbconfig = {
                'host': db_config.get('EXTERNAL_HOST', 'rm-uf614tc8841ee6nwiwo.rwlb.rds.aliyuncs.com'),
                'port': db_config.get('port', 3306),
                'user': db_config.get('DB_USER', 'jianfengshxy'),
                'password': db_config.get('DB_PASSWORD', 'jianfeng1984Aa+'),
                'database': db_config.get('DB_NAME', 'kuafudb'),
                'charset': 'utf8mb4'
            }
        self.connection_pool = None
        self.pool_size = pool_size

    def create_pool(self):
        if self.connection_pool is None:
            try:
                self.connection_pool = pooling.MySQLConnectionPool(
                    pool_name="mypool",
                    pool_size=self.pool_size,
                    pool_reset_session=True,
                    **self.dbconfig
                )
                print("数据库连接池创建成功")
            except Error as e:
                raise ConnectionError(f"创建连接池失败: {e}")
        return self.connection_pool

    def get_connection(self):
        pool = self.create_pool()
        return pool.get_connection()

    def disconnect(self, conn):
        if conn and conn.is_connected():
            conn.close()

    def test_connection(self):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()  # 读取结果以避免Unread result found错误
            cursor.close()
            self.disconnect(conn)
            print("数据库连接池测试成功")
            return True
        except Error as e:
            print(f"测试连接失败: {e}")
            return False

    def execute_query(self, sql, params=None):
        conn = self.get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(sql, params or ())
            result = cursor.fetchall()
            conn.commit()
            return result
        finally:
            cursor.close()
            self.disconnect(conn)

    def insert(self, sql, params=None):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params or ())
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
            self.disconnect(conn)

    def insert_many(self, sql, params_list=None):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.executemany(sql, params_list or [])
            conn.commit()
            return cursor.rowcount
        finally:
            cursor.close()
            self.disconnect(conn)

    def update(self, sql, params=None):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params or ())
            conn.commit()
            return cursor.rowcount
        finally:
            cursor.close()
            self.disconnect(conn)

    def delete(self, sql, params=None):
        return self.update(sql, params)