from typing import Optional
import logging

if __name__ == "__main__":
    import os
    import sys

    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.common.errors import RetriableError, ValidationError
import requests
import json
from src.common.constant import SERVER_VERSION, PHONE_TYPE, DEVICE_ID
from src.common.requests_session import session

def get_fund_rank_diagram(user, fund_code) -> Optional[dict]:
    """
    获取基金历史排名图表数据
    Args:
        user: User对象，包含用户认证信息
        fund_code: 基金代码
    Returns:
        dict: 基金历史排名图表数据，如果获取失败返回None
    """
    url = "https://fundcomapi.tiantianfunds.com/mm/FundMNewApi/FundRankDiagram"
    
    headers = {
        'Host': 'fundcomapi.tiantianfunds.com',
        'tracestate': 'pid=0x104d5e3f0,taskid=0x174db1bc0',
        'Accept': '*/*',
        'GTOKEN': '03FC9273690F4DC4B71CB2247A0E4338',
        'clientInfo': 'ttjj-iPhone18,1-iOS-iOS26.0.1',
        'MP-VERSION': '3.6.8',
        'Accept-Language': 'zh-Hans-CN;q=1',
        'validmark': 'Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZdSIrQ1Lx4ygfw5br2rQnUfMES8ernsO5lB/RKZKLdR3yjfnrfzfHdSgXTLHDA0NGIiANDpxJn4QqsyZYAe8zKMA==',
        'User-Agent': 'EMProjJijin/6.8.3 (iPhone; iOS 26.0.1; Scale/3.00)',
        'Referer': 'https://mpservice.com/516939c37bdb4ba2b1138c50cf69a2e1/release/pages/increase-list/index',
        'traceparent': '00-8f41444868164c8a91be49506978b527-0000000000000000-01',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    # 使用 user 对象中的 token 信息
    # 注意：原 curl 命令使用了特定的 deviceid 和 plat (Iphone)，这里尝试使用 user 对象和常量
    # 如果失败，可能需要回退到硬编码的 deviceid/plat，但通常 API 应该通用
    
    data = {
        'FCODE': fund_code,
        'RANGE': '3y',
        'ctoken': user.c_token,
        'deviceid': DEVICE_ID,
        'passportctoken': user.passport_ctoken,
        'passportid': user.passport_id,
        'passportutoken': user.passport_utoken,
        'plat': PHONE_TYPE,
        'product': 'EFund',
        'uid': user.customer_no,
        'userid': user.customer_no,
        'utoken': user.u_token,
        'version': SERVER_VERSION
    }
    
    logger = get_logger("FundRankDiagram")
    extra = {"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "action": "get_fund_rank_diagram", "fund_code": fund_code}
    try:
        response = session.post(url, headers=headers, data=data, verify=False, timeout=15)
        response.raise_for_status()
        
        try:
            return response.json()
        except json.JSONDecodeError as e:
            logger.error(f"解析基金排名图表数据失败: {str(e)}，响应内容: {response.text[:200]}", extra=extra)
            raise ValidationError(str(e))
            
    except requests.exceptions.RequestException as e:
        logger.error(f"请求基金排名图表数据失败: {str(e)}", extra=extra)
        raise RetriableError(str(e))
    except Exception as e:
        logger.error(f"处理基金排名图表数据时发生异常: {str(e)}", extra=extra)
        raise ValidationError(str(e))

if __name__ == '__main__':
    from src.domain.user.User import User
    from src.common.constant import (
        PASSPORT_CTOKEN, PASSPORT_UTOKEN, USER_ID, 
        U_TOKEN, C_TOKEN, PASSPORT_ID
    )
    
    # 构造测试用户
    user = User("default_account", "default_password")
    user.c_token = C_TOKEN
    user.u_token = U_TOKEN
    user.customer_no = USER_ID
    user.passport_id = PASSPORT_ID
    user.passport_ctoken = PASSPORT_CTOKEN
    user.passport_utoken = PASSPORT_UTOKEN
    
    fund_code = '011707'
    print(f"Testing get_fund_rank_diagram for {fund_code}...")
    
    # 配置基本的日志输出到控制台，以便看到 logger 的输出
    logging.basicConfig(level=logging.INFO)
    
    try:
        result = get_fund_rank_diagram(user, fund_code)
        
        if result:
            print("Success! Result received.")
            # 打印部分结果
            print(json.dumps(result, indent=2, ensure_ascii=False)[:500] + "...")
        else:
            print("Failed to get data (returned None).")
    except Exception as e:
        print(f"An error occurred: {e}")
