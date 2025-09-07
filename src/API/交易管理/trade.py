
import requests
import json
import logging
import hashlib
from src.domain.trade.TradeResult import TradeResult
from src.domain.trade.share import Share
from src.domain.user.User import User  # 添加User类的导入
from typing import List, Optional  # 添加类型提示支持
from src.common.constant import DEFAULT_USER, MOBILE_KEY

def get_trades_list(user, sub_account_no="", fund_code="", bus_type="", status=""):
    """
    获取交易列表
    Args:
        user: User对象，包含用户认证信息
        sub_account_no: 子账户编号，默认为空
        fund_code: 基金代码，默认为空
        bus_type: 业务类型，默认为空
        status: 状态，默认为空
    Returns:
        List[TradeResult]: 交易结果列表
    """
    # print(f"index:{user.index}")
    url = f"https://tquerycoreapi{user.index}.1234567.com.cn/api/mobile/Query/GetQueryInfosQuickUse"
    if not user.index:
        url = "https://tquerycoreapi1.1234567.com.cn/api/mobile/Query/GetQueryInfosQuickUse"
    
    headers = {
        "Connection": "keep-alive",
        "Host": f"tquerycoreapi{user.index}.1234567.com.cn",
        "Accept": "*/*",
        "GTOKEN": "4474AFD3E15F441E937647556C01C174",
        "clientInfo": "ttjj-iPhone12,3-iOS-iOS15.6.1",
        "MP-VERSION": "5.5.0-1104",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-Hans-CN;q=1",
        "Content-Type": "application/json",
        "User-Agent": "EMProjJijin/6.5.8 (iPhone; iOS 15.6.1; Scale/3.00)",
        "Referer": "https://mpservice.com/329e138b3cb74f17a2e4ba5c23f374c0/release/pages/home/index"
    }
    
    data = {
        "utoken": user.u_token,
        "uid": user.customer_no,
        "mobileKey": MOBILE_KEY,
        "customerNo": user.customer_no,
        "deviceid": "6A464B04-3930-4D99-AFAD-E40BE6727075",
        "ctoken": user.c_token,
        "serverversion": "6.6.11",
        "rtype": "app",
        "data": json.dumps({
            "PageIndex": 1,
            "PageSize": 100,
            "FundCode": fund_code,
            "DateType": "3",
            "BusType": bus_type,
            "Statu": status,
            "Account": "",
            "SubAccountNo": sub_account_no,
            "CustomerNo": user.customer_no
        })
    }
    
    logger = logging.getLogger("Trade")
    try:
        response = requests.post(url, headers=headers, json=data, verify=False)
        response.raise_for_status()
        response_data = response.json()
        # logger.info(f"响应数据: {response_data}")
        
        if response_data.get("Succeed", False):
            results = []
            for trade_info in response_data.get("responseObjects", []):
                trade_result = TradeResult.from_api(trade_info)
                results.append(trade_result)
            return results
        else:
            logger.error(f"获取可撤单交易列表失败: {response_data}")
            return []
    except requests.exceptions.RequestException as e:
        logger.error(f"请求失败: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"获取可撤单交易列表失败: {str(e)}")
        return []

def get_bank_shares(user: User, sub_account_no: str, fund_code: str) -> List[Share]:
    """
    获取银行份额信息
    Args:
        user: User对象，包含用户认证信息
        sub_account_no: 子账户编号
        fund_code: 基金代码
    Returns:
        List[Share]: 银行份额列表
    """
    url = f"https://tradeapilvs{user.index}.1234567.com.cn/User/home/GetShareDetail"
    if not user.index:
        url = "https://tradeapilvs1.1234567.com.cn/User/home/GetShareDetail"
    
    headers = {
        "Connection": "keep-alive",
        "Host": f"tradeapilvs{user.index}.95021.com",
        "Accept": "*/*",
        "GTOKEN": "4474AFD3E15F441E937647556C01C174",
        "clientInfo": "ttjj-iPhone12,3-iOS-iOS15.6",
        "MP-VERSION": "3.11.0",
        "Accept-Language": "zh-Hans-CN;q=1",
        "User-Agent": "EMProjJijin/6.5.7 (iPhone; iOS 15.6; Scale/3.00)",
        "Referer": "https://mpservice.com/0b74fd40a63b40fb99467fedd9156d8f/release/pages/holdDetailPage",
        "Content-Type": "application/x-www-form-urlencoded",
        "Cookie": "st_inirUrl=fund%3A%2F%2Fpage; st_pvi=13093762203779; st_sp=2022-03-03%2012%3A16%3A47"
    }

    data = {
        "AppType": "ttjj",
        "CToken": user.c_token,
        "CustomerNo": user.customer_no,
        "IsBaseAsset": "false",
        "MobileKey": MOBILE_KEY,
        "Passportid": user.passport_id,
        "PhoneType": "IOS15.6.0",
        "ServerVersion": "6.6.11",
        "UToken": user.u_token,
        "UserId": user.customer_no,
        "Version": "6.6.11",
        "fundCode": fund_code,
        "subAccountNo": sub_account_no
    }

    logger = logging.getLogger("Trade")
    try:
        response = requests.post(url, headers=headers, data=data, verify=False)
        response.raise_for_status()
        response_data = response.json()
        # logger.info(f"响应数据: {response_data}")
        
        bank_shares = []
        if response_data.get("Data") and response_data["Data"].get("Shares"):
            shares_list = response_data["Data"]["Shares"]
            for share_data in shares_list:
                # logger.info(f"share_data: {share_data}")
                # 使用正确的参数名称创建Share对象
                bank_share = Share(
                    bankName=share_data.get("BankName", ""),
                    bankCode=share_data.get("BankCode", ""),
                    showBankCode=share_data.get("ShowBankCode", ""),
                    bankCardNo=share_data.get("BankCardNo", ""),
                    shareId=share_data.get("ShareId", ""),
                    bankAccountNo=share_data.get("BankAccountNo", ""),
                    availableVol=float(share_data.get("AvailableShare", "0")),
                    totalVol=float(share_data.get("TotalAvaVol", "0"))
                )
                bank_shares.append(bank_share)
            return bank_shares
        else:
            # logger.error(f"获取银行份额信息失败: {response_data}")
            return []
    except requests.exceptions.RequestException as e:
        logger.error(f"请求失败: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"获取银行份额信息失败: {str(e)}")
        return []


if __name__ == "__main__":
    # 导入必要的模块
    import sys
    import os
    import logging
    
    # 获取项目根目录路径
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    
    # 如果项目根目录不在Python路径中，则添加
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    
   
 
    
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("Trade")
    
    # 打印用户信息
    logger.info("开始获取交易列表")
    logger.info(f"用户信息: customer_no={DEFAULT_USER.customer_no}")
    
    # 调用接口获取交易列表
    trades = get_trades_list(DEFAULT_USER)
    
    # 打印结果
    logger.info(f"获取到 {len(trades)} 条交易记录")
    for i, trade in enumerate(trades):
        logger.info(f"交易记录 {i+1}: ID={trade.id}, 业务代码={trade.business_code}, 申请份额={trade.apply_count}")