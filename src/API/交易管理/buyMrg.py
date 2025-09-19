import sys
import os

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import requests
import json
import logging
import hashlib
import random
import time
from src.API.银行卡信息.CashBag import getCashBagAvailableShareV2
from src.domain.trade.TradeResult import TradeResult
from src.domain.user.User import User
from typing import List, Optional, Dict, Any
from src.common.constant import MOBILE_KEY
from src.API.工具.utils import get_fund_system_time_trade
from src.common.errors import TradePasswordError  # 新增：密码错误异常

def _is_password_error_message(msg: str) -> bool:
    """根据返回文案判断是否为密码相关错误（保守匹配，避免误伤）。"""
    if not msg:
        return False
    text = str(msg)
    keywords = ["密码错误", "交易密码", "支付密码", "口令错误", "输错", "ErrPass"]
    return any(k in text for k in keywords)

def commit_order(user: User, sub_account_no: str, fund_code: str, amount: float) -> Optional[TradeResult]:
    """
    提交基金购买订单（API层，仅负责原始HTTP请求）
    Args:
        user: User对象，包含用户认证信息
        sub_account_no: 子账户编号
        fund_code: 基金代码
        amount: 购买金额
    Returns:
        Optional[TradeResult]: 交易结果，如果失败则返回None
    """
    logger = logging.getLogger("BuyMrg")

    # 获取交易ID（API前置依赖）
    trace_id = get_trace_id(user)
    if not trace_id:
        logger.error("获取交易ID失败")
        return None

    # 获取银行卡账号（请求必填字段）
    try:
        bank_card_info = user.max_hqb_bank
    except AttributeError:
        logger.error(f"提交订单失败: 银行卡信息未设置。上下文: user_id={user.customer_no}, sub_account_no={sub_account_no}, fund_code={fund_code}, amount={amount}")
        return None
    bank_account_no = bank_card_info.AccountNo
    logger.info(f"提交订单(API)，用户：{user.account}，基金代码：{fund_code}，购买金额：{amount}，银行账号：{bank_account_no}")

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

    # 构建请求数据（此处仅做 str 转换，不再做业务层的金额保护/扰动）
    password_hash = hashlib.md5(user.password.encode()).hexdigest()
    amount_str = str(float(amount))

    data = (
        f"BankAccountNo={bank_account_no}&"
        f"CouponsId=&"
        f"CouponsType=&"
        f"FollowingSubAccountNo=&"
        f"FundAppsJson=%5B%7B%22fundCode%22%3A%22{fund_code}%22%2C%22amount%22%3A%22{amount_str}%22%7D%5D&"
        f"IsPayPlus=false&"
        f"IsRemittance=&"
        f"MobileKey={MOBILE_KEY}&"
        f"Password={password_hash}&"
        f"RatioRefundType=&"
        f"SubAccountNo={sub_account_no}&"
        f"TotalAmounts={amount_str}&"
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
        response = requests.post(url, headers=headers, data=data, verify=False)
        response.raise_for_status()
        result = response.json()

        if 'Success' in result and result['Success']:
            busin_serial_no = result['Data'].get('AppSerialNo')
            business_type = result['Data'].get('BusinType')
            trade_result = TradeResult(
                busin_serial_no,
                business_type,
                None,   # apply_workday
                amount_str,  # amount
                None,   # status
                None,   # show_com_prop
                fund_code
            )
            logger.info(f"提交订单成功: {trade_result}")
            time.sleep(1)
            return trade_result
        elif 'FirstError' in result:
            first_error = result.get('FirstError') or result.get('Message') or ""
            if _is_password_error_message(first_error):
                logger.error(f"提交订单失败(疑似密码错误): {first_error}，立即终止流程")
                raise TradePasswordError(first_error)
            logger.error(f"提交订单失败: {first_error}")
            return None
        else:
            logger.error("提交订单失败: 未知错误")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"请求失败: {str(e)}。上下文: user_id={user.customer_no}, sub_account_no={sub_account_no}, fund_code={fund_code}, amount={amount}")
        return None
    except TradePasswordError as e:
        # 重要：不要吞掉密码错误，让上层立刻中止流程
        logger.error(f"提交订单失败(密码错误)：{e}，向上抛出")
        raise
    except Exception as e:
        logger.error(f"提交订单失败: {str(e)}。上下文: user_id={user.customer_no}, sub_account_no={sub_account_no}, fund_code={fund_code}, amount={amount}")
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
            # logger.info(f"获取交易ID成功: {trace_id}")
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