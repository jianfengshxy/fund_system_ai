import sys
import os
import requests
import json
import logging
import hashlib
import random
import time
from src.API.银行卡信息.CashBag import getCashBagAvailableShareV2
# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.domain.trade.TradeResult import TradeResult
from src.domain.user.User import User
from typing import List, Optional, Dict, Any
from src.common.constant import MOBILE_KEY

def commit_order(user: User, sub_account_no: str, fund_code: str, amount: float) -> Optional[TradeResult]:
    """
    提交基金购买订单
    Args:
        user: User对象，包含用户认证信息
        sub_account_no: 子账户编号
        fund_code: 基金代码
        amount: 购买金额
    Returns:
        Optional[TradeResult]: 交易结果，如果失败则返回None
    """
    logger = logging.getLogger("BuyMrg")
    
    # 获取交易ID
    trace_id = get_trace_id(user)
    if not trace_id:
        logger.error("获取交易ID失败")
        return None
    
    # 获取活期宝银行卡列表
    bank_cards = getCashBagAvailableShareV2(user)
    if not bank_cards:
        logger.error("获取银行卡信息失败：没有可用的银行卡")
        raise Exception("获取银行卡信息失败：没有可用的银行卡")
    
    # 使用第一个银行卡（余额最高的）
    bank_card_info = bank_cards[0]
    
    # 处理购买金额
    if float(amount) < 10:
        amount = str(10 + round(random.uniform(0.01, 1), 2))
    else:
        amount = str(float(amount) - round(random.uniform(0.01, 1), 2))
    
    # 从AccountNo中提取实际的银行账号（第一个#之前的部分）
    bank_account_no = bank_card_info.AccountNo.split('#')[0]
      
    # 检查银行卡余额
    if bank_card_info.CurrentRealBalance < 100:
        logger.error(f'银行卡余额不足: {bank_card_info.CurrentRealBalance}')
        return None
    
    # 构建请求URL
    url = f"https://tradeapilvs{user.index}.1234567.com.cn/Trade/FundTrade/CommitOrder"
    if not user.index:
        url = "https://tradeapilvs1.1234567.com.cn/Trade/FundTrade/CommitOrder"
    
    # 构建请求头
    headers = {
        "Connection": "keep-alive",
        "Host": f"tradeapilvs{user.index}.1234567.com.cn",
        "Accept": "*/*",
        "GTOKEN": "4474AFD3E15F441E937647556C01C174",
        "User-Agent": "EMProjJijin/6.5.5 (iPhone; iOS 15.5; Scale/3.00)",
        "Accept-Language": "zh-Hans-CN;q=1",
        "Referer": "https://mpservice.com/47e7241f3f0a46af8629dfe78fe62c55/release/pages/BuyTrade",
        "clientInfo": "ttjj-iPhone12,3-iOS-iOS15.5",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    # 构建请求数据
    password_hash = hashlib.md5(user.password.encode()).hexdigest()
    
    data = (
        f"BankAccountNo={bank_account_no}&"
        f"CouponsId=&"
        f"CouponsType=&"
        f"FollowingSubAccountNo=&"
        f"FundAppsJson=%5B%7B%22fundCode%22%3A%22{fund_code}%22%2C%22amount%22%3A%22{amount}%22%7D%5D&"
        f"IsPayPlus=false&"
        f"IsRemittance=&"
        f"MobileKey={MOBILE_KEY}&"
        f"Password={password_hash}&"
        f"RatioRefundType=&"
        f"SubAccountNo={sub_account_no}&"
        f"TotalAmounts={amount}&"
        f"TraceID={trace_id}&"
        f"TradeType=AsyJCJY022&"
        f"appType=ttjj&"
        f"cToken={user.c_token}&"
        f"phoneType=Iphone&"
        f"serverVersion=10.6.9&"
        f"uToken={user.u_token}&"
        f"userId={user.customer_no}&"
        f"version=10.6.9"
    )
    
    try:
        # 发送请求
        response = requests.post(url, headers=headers, data=data, verify=False)
        response.raise_for_status()
        result = response.json()
        logger.info(f"提交订单响应: {result}")
        
        # 处理响应结果
        if 'Success' in result and result['Success']:
            busin_serial_no = result['Data'].get('AppSerialNo')
            business_type = result['Data'].get('BusinType')
            
            trade_result = TradeResult(
                busin_serial_no, 
                business_type, 
                None,  # apply_workday
                amount,  # amount
                None,  # status
                None,  # show_com_prop
                fund_code  # fund_code
            )
            
            logger.info(f"提交订单成功: {trade_result}")
            time.sleep(1)
            return trade_result
        elif 'FirstError' in result:
            logger.error(f"提交订单失败: {result['FirstError']}")
            return None
        else:
            logger.error("提交订单失败: 未知错误")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"请求失败: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"提交订单失败: {str(e)}")
        return None


def get_trace_id(user: User) -> Optional[str]:
    """
    获取交易ID
    Args:
        user: User对象，包含用户认证信息
    Returns:
        Optional[str]: 交易ID，如果失败则返回None
    """
    logger = logging.getLogger("BuyMrg")
    
    url = f"https://tradeapilvs{user.index}.1234567.com.cn/Business/home/NoticeStayTrace"
    if not user.index:
        url = "https://tradeapilvs1.1234567.com.cn/Business/home/NoticeStayTrace"
    
    headers = {
        "Connection": "keep-alive",
        "Referer": "https://mpservice.com/47e7241f3f0a46af8629dfe78fe62c55/release/pages/BuyTrade",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Host": f"tradeapilvs{user.index}.1234567.com.cn",
        "User-Agent": "EMProjJijin/6.6.11 (iPhone; iOS 15.5; Scale/3.00)"
    }
    
    data = (
        f"MobileKey={MOBILE_KEY}&"
        f"appType=ttjj&"
        f"cToken={user.c_token}&"
        f"phoneType=Iphone&"
        f"serverVersion=6.6.11&"
        f"uToken={user.u_token}&"
        f"userId={user.customer_no}&"
        f"version=6.6.11"
    )
    
    try:
        response = requests.post(url, headers=headers, data=data, verify=False)
        response.raise_for_status()
        result = response.json()
        
        if 'Success' in result and result['Success'] and 'Data' in result and 'TraceID' in result['Data']:
            trace_id = result['Data']['TraceID']
            logger.info(f"获取交易ID成功: {trace_id}")
            return trace_id
        else:
            logger.error("获取交易ID失败")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"请求失败: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"获取交易ID失败: {str(e)}")
        return None