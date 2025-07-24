import pymysql
import os

# 数据库凭证（请替换为实际值）
DB_USER = 'jianfengshxy'  # 替换为实际用户名
DB_PASSWORD = 'jianfeng1984Aa+'  # 替换为实际密码
DB_NAME = 'kuafudb'  # 从您的选择中获取，或替换为实际数据库名

# 内网和外网地址
INTERNAL_HOST = 'rm-uf614tc8841ee6nwi.rwlb.rds.aliyuncs.com'
EXTERNAL_HOST = 'rm-uf614tc8841ee6nwiwo.rwlb.rds.aliyuncs.com'
DB_PORT = 3306

def is_fc_environment():
    """检查是否在阿里云函数计算环境中"""
    return 'FC_FUNCTION_NAME' in os.environ or 'ALIYUN_FC_RUNTIME' in os.environ

def test_connection(host, port, user, password, db_name, description):
    try:
        connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=db_name,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        print(f"{description} 连接成功: {host}:{port}")
        # 可选：执行简单查询
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            print(f"{description} 测试查询结果: {result}")
        connection.close()
        return True
    except pymysql.MySQLError as e:
        print(f"{description} 连接失败: {e}")
        return False

if __name__ == "__main__":
    if is_fc_environment():
        print("检测到阿里云FC环境，使用内网主机")
        test_connection(INTERNAL_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, "内网")
    else:
        print("检测到本地环境，使用外网主机")
        test_connection(EXTERNAL_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, "外网")
    # 如果需要手动测试其他主机，取消注释以下行
    # test_connection('rm-uf614tc8841ee6nwi.rwlb.rds.aliyuncs.com', DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, "手动内网")
    # test_connection('rm-uf614tc8841ee6nwiwo.rwlb.rds.aliyuncs.com', DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, "手动外网")