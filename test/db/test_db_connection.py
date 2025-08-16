import sys
import os

# 添加项目根目录到sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.db.database_connection import DatabaseConnection

# 设置环境变量（测试用，实际从s.yaml加载）
os.environ['DB_HOST'] = 'rm-uf614tc8841ee6nwiwo.rwlb.rds.aliyuncs.com'
os.environ['DB_PORT'] = '3306'
os.environ['DB_USER'] = 'jianfengshxy'
os.environ['DB_PASSWORD'] = 'jianfeng1984Aa+'
os.environ['DB_NAME'] = 'kuafudb'

db = DatabaseConnection()
if db.test_connection():
    print("连接测试成功")
    # 测试查询
    results = db.execute_query("SELECT DATABASE()")
    print(f"当前数据库: {results}")
    # 注意：由于新实现中disconnect现在需要传入连接对象，您可能需要调整为：
    # conn = db.get_connection()
    # ... 使用后 db.disconnect(conn)
    # 但对于测试，当前方法已兼容
else:
    print("连接测试失败")