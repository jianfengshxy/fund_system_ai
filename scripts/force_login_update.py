import sys
import os

# Ensure src is in the python path
sys.path.insert(0, os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from src.API.登录接口.login import login, login_passport, inference_passport_for_bind
from src.service.用户管理.用户信息 import update_user_cache
from src.service.用户管理.user_token_store import UserTokenStore
from src.service.银行卡账户.bankAccoutService import getMaxhqbBank

def force_login_and_update(account, password):
    print(f"开始为用户 {account} 重新登录...")
    u1 = login(account, password)
    if u1:
        print("基础登录成功，获取passport信息...")
        u2 = inference_passport_for_bind(u1) or login_passport(u1)
        if u2:
            print("Passport信息获取成功，获取银行卡信息...")
            u3 = getMaxhqbBank(u2) or u2
            
            print("更新缓存(内存+文件)...")
            update_user_cache(u3)
            
            print("更新数据库...")
            try:
                UserTokenStore().upsert(u3)
                print("数据库和缓存更新成功！")
            except Exception as e:
                print("更新数据库失败:", e)
        else:
            print("Passport登录/推断失败！")
    else:
        print("基础登录失败，请检查账号密码！")

if __name__ == "__main__":
    force_login_and_update("13820198186", "tang8186")