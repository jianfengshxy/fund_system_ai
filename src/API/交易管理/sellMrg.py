import sys
import os
import requests
import json
import logging
import hashlib
import time

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.domain.trade.TradeResult import TradeResult
from src.domain.user.User import User
from typing import List, Optional, Dict, Any
from src.common.constant import MOBILE_KEY,SERVER_VERSION,PHONE_TYPE

def super_transfer(user: User, sub_account_no: str, fund_code: str, fund_amount: float, share_id: str) -> Optional[TradeResult]:
    """
    基金转换
    Args:
        user: User对象，包含用户认证信息
        sub_account_no: 子账户编号
        fund_code: 基金代码
        fund_amount: 转换份额
        share_id: 份额ID
    Returns:
        Optional[TradeResult]: 交易结果，如果失败则返回None
    """
    if abs(fund_amount) < 0.000001:  # 使用绝对值和小阈值来判断接近零的值
        logger = logging.getLogger("SellMrg")
        logger.info("卖出的份额参数为0")
        return None
    
    url = f"https://tradeapilvs{user.index}.1234567.com.cn/Business/home/SFTransfer"
    if not user.index:
        url = "https://tradeapilvs1.1234567.com.cn/Business/home/SFTransfer"
    
    headers = {
        "Connection": "keep-alive",
        "Host": f"tradeapilvs{user.index}.1234567.com.cn",
        "Accept": "*/*",
        "GTOKEN": "4474AFD3E15F441E937647556C01C174",
        "clientInfo": "ttjj-iPhone12,3-iOS-iOS15.5",
        "Accept-Language": "zh-Hans-CN;q=1",
        "User-Agent": "EMProjJijin/6.5.5 (iPhone; iOS 15.5; Scale/3.00)",
        "Referer": "https://mpservice.com/6ddf65da15dd416ca1c964efb606471f/release/pages/fundSalePage",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    # 对密码进行MD5加密
    password_hash = hashlib.md5(user.password.encode()).hexdigest()
    req_no = str(int(time.time() * 1000))  # 当前时间的毫秒级Unix时间戳
    
    data = {
        "FundAmount": fund_amount,
        "FundIn": "004369",
        "FundOut": fund_code,
        "IsAllTransfer": "1",
        "LargeRedemptionFlag": "1",
        "MobileKey": MOBILE_KEY,
        "Password": password_hash,
        "ReqNo": req_no,
        "ShareID": share_id,
        "SubAccountNo": sub_account_no,
        "appType": "ttjj",
        "cToken": user.c_token,
        "phoneType": "Iphone",
        "pwd": password_hash,
        "serverVersion": SERVER_VERSION,
        "uToken": user.u_token,
        "userId": user.customer_no,
        "version": SERVER_VERSION
    }
    
    logger = logging.getLogger("SellMrg")
    try:
        response = requests.post(url, headers=headers, data=data, verify=False)
        response.raise_for_status()
        response_data = response.json()
        logger.info(f"响应数据: {response_data}")
        
        busin_serial_no = None
        business_type = None
        apply_workday = None
        amount = None
        status = None
        show_com_prop = None
        
        if response_data is not None and "Data" in response_data:
            data = response_data["Data"]
            if data is not None:
                if "JumpParams" in data:
                    jump_params = data["JumpParams"]
                    busin_serial_no = jump_params.get("BusinSerialNo")
                    business_type = jump_params.get("BusinessType")
                apply_workday = data.get("ApplyWorkDay", "")
                amount = data.get("ApplyAmount", "")
                status = data.get("Status", "")
                show_com_prop = data.get("ShowComProp", "")
        
        result = TradeResult(busin_serial_no, business_type, apply_workday, amount, status, show_com_prop, fund_code)
        logger.info(f"super_transfer的结果: {result}")
        return result
    except requests.exceptions.RequestException as e:
        logger.error(f"请求失败: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"基金转换失败: {str(e)}")
        return None


def hqbMakeRedemption(user: User, sub_account_no: str, fund_code: str, fund_amount: float, share_id: str) -> Optional[TradeResult]:
    """
    货币基金赎回
    Args:
        user: User对象，包含用户认证信息
        sub_account_no: 子账户编号
        fund_code: 基金代码
        fund_amount: 赎回份额
        share_id: 份额ID
    Returns:
        Optional[TradeResult]: 交易结果，如果失败则返回None
    """
    if fund_amount == 0.00:
        logger = logging.getLogger("SellMrg")
        logger.info("赎回的份额不能为0")
        return None
    
    url = f"https://tradeapilvs{user.index}.1234567.com.cn/Business/hqb/MakeRedemption"
    if not user.index:
        url = "https://tradeapilvs1.1234567.com.cn/Business/hqb/MakeRedemption"
    
    headers = {
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Referer": "https://mpservice.com/fund5e3619595b0346/release/pages/sell-fund/index",
        "Host": f"tradeapilvs{user.index}.1234567.com.cn",
        "tracestate": "pid=0x10630d5a0,taskid=0x282890a00",
        "Accept": "*/*",
        "GTOKEN": "4474AFD3E15F441E937647556C01C174",
        "clientInfo": "ttjj-iPhone 11 Pro-iOS-iOS16.2",
        "MP-VERSION": "1.0.5",
        "Accept-Language": "zh-Hans-CN;q=1",
        "User-Agent": "EMProjJijin/6.6.12 (iPhone; iOS 16.2; Scale/3.00)",
        "traceparent": "00-c77bf29263684cbcb20397522ee7fa48-0000000000000000-01",
        "Content-Length": "1233",
        "Cookie": "acw_tc=0bca392617092637189786468e3ebc1cbaae75aedd2ca760b7029b704565f0"
    }
    
    # 构造请求参数
    password_hash = hashlib.md5(user.password.encode()).hexdigest()
    req_no = str(int(time.time() * 1000))  # 当前时间的毫秒级Unix时间戳
    
    payload = {
        "ServerVersion": "6.6.12",
        "isAllTransfer": True,
        "reqNo": req_no,
        "shareID": share_id,
        "PayType": "1",
        "CustomerNo": user.customer_no,
        "Vol": str(fund_amount),
        "PhoneType": "Iphone",
        "Version": "6.6.12",
        "MobileKey": MOBILE_KEY,
        "UserId": user.customer_no,
        "fundOut": str(fund_code),
        "fromSubAccountNo": sub_account_no,
        "fundIn": "007866",
        "UToken": user.u_token,
        "largeRedemptionFlag": "1",
        "AppType": "ttjj",
        "CToken": user.c_token,
        "Password": password_hash
    }
    
    logger = logging.getLogger("SellMrg")
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), verify=False)
        response.raise_for_status()
        response_data = response.json()
        logger.info(f"赎回的响应: {response_data}")
        
        if response_data is not None and "Data" in response_data:
            data = response_data["Data"]
            if data is not None:
                # 解析响应内容
                pred_info = data.get("PredInfo", "")
                apply_workday = data.get("ApplyWorkDay", "")
                amount = data.get("ApplyAmount", "")
                status = data.get("Status", "")
                busin_serial_no = None
                business_type = None
                show_com_prop = None
                
                if "JumpParams" in data:
                    jump_params = data["JumpParams"]
                    busin_serial_no = jump_params.get("BusinSerialNo")
                    business_type = jump_params.get("BusinessType")
                
                result = TradeResult(busin_serial_no, business_type, apply_workday, amount, status, show_com_prop, fund_code)
                logger.info(f"货币基金赎回结果: {result}")
                return result
            else:
                # 处理响应中未返回Data的情况
                logger.error("赎回响应中未返回Data")
                return TradeResult(None, None, None, None, None, None, fund_code)
        else:
            # 处理响应数据不完整的情况
            logger.error("赎回响应数据不完整")
            return TradeResult(None, None, None, None, None, None, fund_code)
    except requests.exceptions.RequestException as e:
        logger.error(f"请求失败: {str(e)}")
        return TradeResult(None, None, None, None, None, None, fund_code)
    except Exception as e:
        logger.error(f"货币基金赎回失败: {str(e)}")
        return TradeResult(None, None, None, None, None, None, fund_code)


