from typing import Optional

if __name__ == "__main__":
    # 导入必要的模块
    import sys
    import os
    
    # 获取项目根目录路径
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    
    # 如果项目根目录不在Python路径中，则添加
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

import logging

from src.API.基金信息.FundInfo import getFundInfo
from src.common.logger import get_logger
from src.common.errors import RetriableError, ValidationError
import requests
from src.common.requests_session import session
from src.domain.fund.fund_info import FundInfo
from src.common.constant import DEFAULT_USER, SERVER_VERSION, PHONE_TYPE, MOBILE_KEY, DEVICE_ID

def update_fund_estimated_value(user, fund_info: FundInfo) -> FundInfo:
    """
    获取并更新基金的估值信息 (GSZ, GSZZL, GZTIME)
    
    Args:
        user: User对象，包含用户认证信息
        fund_info: FundInfo对象，将被更新估值信息
        
    Returns:
        FundInfo: 更新后的FundInfo对象
    """
    url = "https://fundcomapi.tiantianfunds.com/mm/newCore/FundValuationLast"
    
    # 这里的header和参数参考了用户提供的curl命令
    headers = {
        "Host": "fundcomapi.tiantianfunds.com",
        "Accept": "*/*",
        "GTOKEN": "03FC9273690F4DC4B71CB2247A0E4338",
        "clientInfo": "ttjj-iPhone18,1-iOS-iOS26.0.1",
        "MP-VERSION": "1.24.0",
        "Accept-Language": "zh-Hans-CN;q=1",
        "validmark": "Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZdSIrQ1Lx4ygfw5br2rQnUfMES8ernsO5lB/RKZKLdR3yoBJgvUEdjLzf1UcRv2jubOhDMdgTBXIMkwtWN4p0ISg==",
        "User-Agent": "EMProjJijin/6.8.3 (iPhone; iOS 26.0.1; Scale/3.00)",
        "Referer": "https://mpservice.com/fundb5035dd2ee584a/release/pages/public-offer-fund/index",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "FCODES": fund_info.fund_code,
        "FIELDS": "GSZZL,GZTIME,GSZ",
        "ctoken": user.c_token,
        "deviceid": DEVICE_ID, # 使用常量
        "passportctoken": getattr(user, 'passport_ctoken', ''),
        "passportid": getattr(user, 'passport_id', ''),
        "passportutoken": getattr(user, 'passport_utoken', ''),
        "plat": PHONE_TYPE, # 使用常量 'Iphone'
        "product": "EFund",
        "uid": user.customer_no, # 假设uid使用customer_no
        "userid": user.customer_no, # 假设userid使用customer_no
        "utoken": user.u_token,
        "version": "6.8.3" # 这里硬编码为6.8.3，或者使用SERVER_VERSION
    }
    
    logger = get_logger("FundValuation")
    extra = {"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "action": "update_fund_estimated_value", "fund_code": fund_info.fund_code}
    
    try:
        response = session.post(url, headers=headers, data=data, verify=False, timeout=10)
        response.raise_for_status()
        
        json_data = response.json()
        logger.debug(f"响应数据: {json_data}")
        
        if not json_data.get('success', False):
            # 有些接口成功也是 code 0，但这里success字段明确
            error_msg = json_data.get('firstError') or '未知错误'
            # 注意：如果success为False，可能errorCode不为0
            if json_data.get('errorCode', -1) != 0:
                 logger.error(f"获取基金估值信息失败: {error_msg}", extra=extra)
                 # 这里可以选择抛出异常，或者只是记录错误并返回原对象
                 # 参照FundRank，抛出异常比较合适，或者静默失败
                 # 考虑到估值信息可能不是必须的，可以记录错误但不阻断流程，
                 # 但为了明确反馈，这里还是记录并让上层决定
                 pass
        
        data_list = json_data.get('data', [])
        if data_list and isinstance(data_list, list):
            data = data_list[0]
            # 更新估值信息
            try:
                fund_info.estimated_value = float(data.get('GSZ') or 0)  # GSZ - 估算净值
            except (ValueError, TypeError):
                fund_info.estimated_value = 0.0
                
            try:
                fund_info.estimated_change = float(data.get('GSZZL') or 0)  # GSZZL - 估算涨跌幅
            except (ValueError, TypeError):
                fund_info.estimated_change = 0.0
                
            fund_info.estimated_time = data.get('GZTIME', '')  # GZTIME - 估算时间
            
            logger.info(f"基金{fund_info.fund_code}估值更新: 类型={fund_info.fund_type}, 净值={fund_info.estimated_value}, 涨跌幅={fund_info.estimated_change}%, 时间={fund_info.estimated_time}", extra=extra)
        else:
            logger.warning(f"未找到基金{fund_info.fund_code}的估值数据", extra=extra)
            
        return fund_info
            
    except requests.exceptions.RequestException as e:
        logger.error(f"请求失败: {str(e)}", extra=extra)
        # 这里可以选择抛出RetriableError，或者吞掉异常
        raise RetriableError(str(e))
    except Exception as e:
        logger.error(f"处理过程发生异常: {str(e)}", extra=extra)
        raise ValidationError(str(e))

if __name__ == "__main__":
    # 设置日志级别为DEBUG
    logging.getLogger().setLevel(logging.DEBUG)
    
    fund_code = "004433"
    
    print(f"正在获取基金 {fund_code} 的基础信息...")
    fund_info = getFundInfo(DEFAULT_USER, fund_code)
    
    if fund_info:
        print(f"获取成功: {fund_info.fund_name} ({fund_info.fund_code}), 类型: {fund_info.fund_type}")
        print(f"更新前: 估值={fund_info.estimated_value}, 涨跌幅={fund_info.estimated_change}, 时间={fund_info.estimated_time}")
        
        try:
            print("正在更新估值信息...")
            updated_fund = update_fund_estimated_value(DEFAULT_USER, fund_info)
            print(f"更新后: 估值={updated_fund.estimated_value}, 涨跌幅={updated_fund.estimated_change}, 时间={updated_fund.estimated_time}")
            print("测试通过！")
        except Exception as e:
            print(f"测试失败: {e}")
    else:
        print(f"无法获取基金 {fund_code} 的基础信息，测试终止。")
