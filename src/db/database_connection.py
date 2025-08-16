import os
import yaml  # 新增导入，用于解析 s.yaml
import pymysql
from pymysql.err import OperationalError

class DatabaseConnection:
    def __init__(self):
        if 'FC_FUNCTION_NAME' in os.environ:  # 检测是否在阿里云 Function Compute 环境
            # 在阿里云环境，从环境变量读取
            self.host = os.environ.get('internal_host', 'default_host')
            self.port = int(os.environ.get('DB_PORT', 3306))
            self.user = os.environ.get('DB_USER', 'default_user')
            self.password = os.environ.get('DB_PASSWORD', 'default_password')
            self.database = os.environ.get('DB_NAME', 'default_db')
        else:
            # 在本地环境，从 s.yaml 读取
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 's.yaml')
            with open(config_path, 'r') as file:
                config = yaml.safe_load(file)
            db_config = config['vars']['common']['database']
            self.host = db_config.get('external_host', 'default_host')  # 假设本地使用 external_host
            self.port = db_config.get('port', 3306)
            self.user = db_config.get('DB_USER', 'default_user')
            self.password = db_config.get('DB_PASSWORD', 'default_password')
            self.database = db_config.get('DB_NAME', 'default_db')
        self.connection = None

    def connect(self):
        if self.connection is None or not self.connection.open:
            try:
                self.connection = pymysql.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    database=self.database,
                    charset='utf8mb4',
                    cursorclass=pymysql.cursors.DictCursor
                )
                print("数据库连接成功")
            except OperationalError as e:
                raise ConnectionError(f"连接数据库失败: {e}")
        return self.connection

    def disconnect(self):
        if self.connection and self.connection.open:
            self.connection.close()
            self.connection = None
            print("数据库连接已断开")

    def test_connection(self):
        try:
            conn = self.connect()
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
            self.disconnect()
            return True
        except Exception as e:
            print(f"测试连接失败: {e}")
            return False

    def execute_query(self, sql, params=None):
        conn = self.connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params or ())
                return cursor.fetchall()
        finally:
            conn.commit()  # 假设查询后需提交，视情况调整

    def insert(self, sql, params=None):
        conn = self.connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params or ())
                conn.commit()
                return cursor.lastrowid
        finally:
            pass  # 可添加错误处理

    def insert_many(self, sql, params_list=None):
        conn = self.connect()
        try:
            with conn.cursor() as cursor:
                cursor.executemany(sql, params_list or [])
                conn.commit()
                return cursor.rowcount
        finally:
            pass  # 可添加错误处理

    def update(self, sql, params=None):
        conn = self.connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params or ())
                conn.commit()
                return cursor.rowcount
        finally:
            pass

    def delete(self, sql, params=None):
        return self.update(sql, params)  # 复用update逻辑