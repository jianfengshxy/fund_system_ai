import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3

# 禁用SSL证书验证警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def create_session():
    session = requests.Session()
    # 配置重试策略
    retry_strategy = Retry(
        total=3,  # 最大重试次数
        backoff_factor=0.5,  # 重试间隔因子
        status_forcelist=[429, 500, 502, 503, 504],  # 需要重试的状态码
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]  # 允许重试的请求方法
    )
    # 配置连接池大小
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=100,  # 连接池大小
        pool_maxsize=100       # 最大连接数
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

# 全局共享Session
session = create_session()
