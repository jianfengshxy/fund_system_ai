import sys
import os
import json

root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.service.用户管理.用户信息 import get_user_all_info, refresh_user_tokens
from src.common.constant import DEFAULT_GTOKEN, DEVICE_ID, IOS_CLIENT_INFO, IOS_OS_VERSION, IOS_USER_AGENT, MOBILE_KEY, PLATFORM, SERVER_VERSION
import requests

def test_api():
    print("1. 获取用户信息...")
    refresh_user_tokens("13918199137", "sWX15706", ensure_bank=False)
    user = get_user_all_info("13918199137", "sWX15706", ensure_bank=False)
    if not user:
        print("ERROR: 获取用户信息失败")
        return
    
    print(f"2. 用户获取成功: {getattr(user, 'customer_name', '未知')}")
    
    post_url = "https://fundmobapi.eastmoney.com/FundMNewApi/FundMnIndexHot"
    
    body_params = {
        'IndexCode': '930901',
        'MobileKey': MOBILE_KEY,
        'OSVersion': IOS_OS_VERSION,
        'appType': 'ttjj',
        'appVersion': SERVER_VERSION,
        'cToken': user.c_token,
        'deviceid': DEVICE_ID,
        'passportid': user.passport_id,
        'plat': PLATFORM,
        'product': 'EFund',
        'serverVersion': SERVER_VERSION,
        'uToken': user.u_token,
        'userId': user.customer_no,
        'version': SERVER_VERSION
    }
    
    headers = {
        'Connection': 'keep-alive',
        'Host': 'fundmobapi.eastmoney.com',
        'Accept': '*/*',
        'GTOKEN': DEFAULT_GTOKEN,
        'clientInfo': IOS_CLIENT_INFO,
        'Accept-Language': 'zh-Hans-CN;q=1',
        'User-Agent': IOS_USER_AGENT,
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    print(f"3. 发送请求: {post_url}")
    try:
        # 尝试 POST
        res = requests.post(post_url, data=body_params, headers=headers, verify=False)
        print("4. POST 请求返回结果如下:")
        print(res.text[:1500])
        
        # 尝试 GET
        res_get = requests.get(post_url, params=body_params, headers=headers, verify=False)
        print("5. GET 请求返回结果如下:")
        print(res_get.text[:1500])
        
    except Exception as e:
        print(f"ERROR: 请求失败: {e}")

if __name__ == "__main__":
    test_api()
