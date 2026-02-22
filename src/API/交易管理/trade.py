
import requests
import json
import logging

if __name__ == "__main__":
    import os
    import sys

    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.common.errors import RetriableError, ValidationError
import hashlib
from src.domain.trade.TradeResult import TradeResult
from src.domain.trade.share import Share
from src.domain.user.User import User  # 添加User类的导入
from typing import List, Optional  # 添加类型提示支持
from src.common.constant import DEFAULT_USER, MOBILE_KEY
from src.API.登录接口.login import ensure_user_fresh

logger = get_logger("Trade")

def get_trades_list(user, sub_account_no="", fund_code="", bus_type="", status="", page_index=1, page_size=50, date_type=""):
    """
    获取交易列表
    Args:
        user: User对象，包含用户认证信息
        sub_account_no: 子账户编号，默认为空
        fund_code: 基金代码，默认为空
        bus_type: 业务类型，默认为空
        status: 状态，默认为空
        page_index: 页码，默认为1
        page_size: 每页数量，默认为100
        date_type: 时间范围类型，默认为"3"。
                   "5": 近1周
                   "1": 近1月
                   "2": 近3月
                   "3": 近1年 (推荐，能获取较长历史记录)
    Returns:
        List[TradeResult]: 交易结果列表
    """
    # print(f"index:{user.index}")
    u = ensure_user_fresh(user)
    url = f"https://tquerycoreapi{u.index}.1234567.com.cn/api/mobile/Query/GetQueryInfosQuickUse"
    if not u.index:
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
    
    payload_dict = {
        "PageIndex": page_index,
        "PageSize": page_size,
        "FundCode": fund_code,
        "BusType": bus_type,
        "Statu": status,
        "Account": "",
        "SubAccountNo": sub_account_no,
        "CustomerNo": u.customer_no
    }
    
    if date_type is not None:
        payload_dict["DateType"] = date_type
        
    data = {
        "utoken": u.u_token,
        "uid": u.customer_no,
        "mobileKey": MOBILE_KEY,
        "customerNo": u.customer_no,
        "deviceid": "6A464B04-3930-4D99-AFAD-E40BE6727075",
        "ctoken": u.c_token,
        "serverversion": "6.6.11",
        "rtype": "app",
        "data": json.dumps(payload_dict)
    }
    
    extra = {"account": getattr(user, "mobile_phone", None) or getattr(user, "account", None),
             "sub_account_name": "",
             "action": "get_trades_list",
             "fund_code": fund_code,
             "sub_account_no": sub_account_no}
    
    all_results = []
    current_page = page_index
    max_pages = 100  # 防止无限循环
    
    try:
        while current_page < page_index + max_pages:
            payload_dict["PageIndex"] = current_page
            data["data"] = json.dumps(payload_dict)
            
            response = requests.post(url, headers=headers, json=data, verify=False)
            response.raise_for_status()
            response_data = response.json()
            
            current_batch = []
            if response_data.get("Succeed", False):
                for trade_info in response_data.get("responseObjects", []):
                    current_batch.append(TradeResult.from_api(trade_info))
                
                if current_batch:
                    all_results.extend(current_batch)
                
                # 如果当前页获取的数据少于page_size，说明是最后一页了
                if len(current_batch) < page_size:
                    break
                    
                current_page += 1
            else:
                # 错误处理逻辑 (保留原有的错误处理，但只针对第一次请求或关键错误)
                err_text = ""
                try:
                    err_text = json.dumps(response_data, ensure_ascii=False)
                except Exception:
                    err_text = ""
                
                # 检查是否为正常空数据（ErrorCode=0）
                error_code = response_data.get("ErrorCode")
                if error_code == 0 or str(error_code) == "0":
                    if current_page == page_index: # 第一页就没数据
                         logger.info(f"获取交易列表为空 (ErrorCode=0)", extra=extra)
                    break # 没数据了，退出循环

                need_refresh = any(k in err_text for k in ['Token', 'token', '凭证', 'passport', '未登录', '请登录', 'UToken', 'CToken', 'passportid', '权限'])
                if not need_refresh:
                    logger.error(f"获取可撤单交易列表失败: {response_data}", extra=extra)
                    if current_page == page_index: # 第一页就失败才抛异常
                        raise ValidationError("API_FAIL")
                    break

                # Token过期重试逻辑 (简化版，只在第一页失败时重试，或者在循环中刷新token后继续？)
                # 为了保持逻辑简单且健壮，如果中途token过期，刷新后重试当前页
                u2 = ensure_user_fresh(u, force_refresh=True)
                url2 = f"https://tquerycoreapi{u2.index}.1234567.com.cn/api/mobile/Query/GetQueryInfosQuickUse"
                if not u2.index:
                    url2 = "https://tquerycoreapi1.1234567.com.cn/api/mobile/Query/GetQueryInfosQuickUse"
                
                # 更新data中的token信息
                data["utoken"] = u2.u_token
                data["uid"] = u2.customer_no
                data["customerNo"] = u2.customer_no
                data["ctoken"] = u2.c_token
                payload_dict["CustomerNo"] = u2.customer_no
                data["data"] = json.dumps(payload_dict)
                
                # 更新headers host (虽然requests会自动处理，但保持一致性)
                headers["Host"] = f"tquerycoreapi{u2.index}.1234567.com.cn"
                
                # 重试当前页
                response = requests.post(url2, headers=headers, json=data, verify=False)
                response.raise_for_status()
                response_data = response.json()
                
                if response_data.get("Succeed", False):
                    retry_batch = []
                    for trade_info in response_data.get("responseObjects", []):
                        retry_batch.append(TradeResult.from_api(trade_info))
                    
                    if retry_batch:
                        all_results.extend(retry_batch)
                    
                    if len(retry_batch) < page_size:
                        break
                    current_page += 1
                else:
                    error_code = response_data.get("ErrorCode")
                    if error_code == 0 or str(error_code) == "0":
                        break
                    
                    logger.error(f"获取可撤单交易列表失败(重试后): {response_data}", extra=extra)
                    if current_page == page_index:
                        raise ValidationError("API_FAIL")
                    break
        
        return all_results

    except requests.exceptions.RequestException as e:
        logger.error(f"请求失败: {str(e)}", extra=extra)
        raise RetriableError(str(e))
    except Exception as e:
        logger.error(f"获取可撤单交易列表失败: {str(e)}", extra=extra)
        raise ValidationError(str(e))

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
    u = ensure_user_fresh(user)
    url = f"https://tradeapilvs{u.index}.1234567.com.cn/User/home/GetShareDetail"
    if not u.index:
        url = "https://tradeapilvs1.1234567.com.cn/User/home/GetShareDetail"
    
    headers = {
        "Connection": "keep-alive",
        "Host": f"tradeapilvs{u.index}.1234567.com.cn",
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
        "CToken": u.c_token,
        "CustomerNo": u.customer_no,
        "IsBaseAsset": "false",
        "MobileKey": MOBILE_KEY,
        "Passportid": u.passport_id,
        "PhoneType": "IOS15.6.0",
        "ServerVersion": "6.6.11",
        "UToken": u.u_token,
        "UserId": u.customer_no,
        "Version": "6.6.11",
        "fundCode": fund_code,
        "subAccountNo": sub_account_no
    }

    logger = get_logger("Trade")
    extra = {"account": getattr(user, "mobile_phone", None) or getattr(user, "account", None),
             "action": "get_bank_shares",
             "fund_code": fund_code,
             "sub_account_no": sub_account_no}
    try:
        response = requests.post(url, headers=headers, data=data, verify=False)
        
        # 403 Forbidden 重试逻辑
        if response.status_code == 403:
            logger.warning(f"获取银行份额信息返回403 Forbidden, 尝试刷新token重试", extra=extra)
            u2 = ensure_user_fresh(u, force_refresh=True)
            data["CToken"] = u2.c_token
            data["CustomerNo"] = u2.customer_no
            data["Passportid"] = u2.passport_id
            data["UToken"] = u2.u_token
            data["UserId"] = u2.customer_no
            
            url2 = f"https://tradeapilvs{u2.index}.1234567.com.cn/User/home/GetShareDetail"
            if not u2.index:
                url2 = "https://tradeapilvs1.1234567.com.cn/User/home/GetShareDetail"
            
            # 更新Host头
            headers["Host"] = f"tradeapilvs{u2.index}.1234567.com.cn"
            
            response = requests.post(url2, headers=headers, data=data, verify=False)

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
            logger.info(f"银行份额条数: {len(bank_shares)}", extra=extra)
            return bank_shares
        else:
            err_text = ""
            try:
                err_text = json.dumps(response_data, ensure_ascii=False)
            except Exception:
                err_text = ""
            
            # 检查是否为正常空数据（Success=True 或 ErrorCode=0）
            is_success = response_data.get("Success", False)
            error_code = response_data.get("ErrorCode")
            if is_success or error_code == 0 or str(error_code) == "0":
                logger.info(f"获取银行份额信息为空 (无持有份额)", extra=extra)
                return []

            need_refresh = any(k in err_text for k in ['Token', 'token', '凭证', 'passport', '未登录', '请登录', 'UToken', 'CToken', 'passportid', '权限'])
            if not need_refresh:
                logger.warning(f"获取银行份额信息返回异常数据: {response_data}", extra=extra)
                return []
            u2 = ensure_user_fresh(u, force_refresh=True)
            data["CToken"] = u2.c_token
            data["CustomerNo"] = u2.customer_no
            data["Passportid"] = u2.passport_id
            data["UToken"] = u2.u_token
            data["UserId"] = u2.customer_no
            url2 = f"https://tradeapilvs{u2.index}.1234567.com.cn/User/home/GetShareDetail"
            if not u2.index:
                url2 = "https://tradeapilvs1.1234567.com.cn/User/home/GetShareDetail"
            response = requests.post(url2, headers=headers, data=data, verify=False)
            response.raise_for_status()
            response_data = response.json()
            bank_shares = []
            if response_data.get("Data") and response_data["Data"].get("Shares"):
                shares_list = response_data["Data"]["Shares"]
                for share_data in shares_list:
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
                logger.info(f"银行份额条数: {len(bank_shares)}", extra=extra)
                return bank_shares
            logger.warning(f"获取银行份额信息返回空数据: {response_data}", extra=extra)
            return []
    except requests.exceptions.RequestException as e:
        logger.error(f"请求失败: {str(e)}", extra=extra)
        raise RetriableError(str(e))
    except Exception as e:
        logger.error(f"获取银行份额信息失败: {str(e)}", extra=extra)
        raise ValidationError(str(e))


if __name__ == "__main__":
    # 导入必要的模块
    import logging
    
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
