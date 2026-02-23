import requests
import json
import logging
import urllib3
import hashlib
from requests.adapters import HTTPAdapter
from typing import List, Optional
import sys
import os

# Add root dir to sys.path if needed
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.API.登录接口.login import ensure_user_fresh
from src.domain.trade.TradeResult import TradeResult
from src.domain.trade.share import Share
from src.domain.user.User import User
from src.common.constant import MOBILE_KEY, DEFAULT_USER
from src.common.logger import get_logger
from src.common.errors import RetriableError, ValidationError

logger = get_logger("Trade")

class HostResolveAdapter(HTTPAdapter):
    def __init__(self, host: str, ip: str, **kwargs):
        self._host = host
        self._ip = ip
        super().__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        pool_kwargs["assert_hostname"] = self._host
        pool_kwargs["server_hostname"] = self._host
        self.poolmanager = urllib3.PoolManager(num_pools=connections, maxsize=maxsize, block=block, **pool_kwargs)

    def get_connection(self, url, proxies=None):
        return self.poolmanager.connection_from_host(self._ip, port=443, scheme="https")

    def add_headers(self, request, **kwargs):
        request.headers["Host"] = self._host

def get_one_fund_tran_infos(user, fund_code, start_date=None, end_date=None, page_index=1, page_size=100, date_type="3"):
    """
    获取单个基金的全部交易历史（支持指定时间范围）
    Args:
        user: User对象
        fund_code: 基金代码
        start_date: 开始日期 (YYYY-MM-DD), 默认为2010-01-01
        end_date: 结束日期 (YYYY-MM-DD), 默认为当前日期
        page_index: 页码
        page_size: 每页数量
        date_type: 时间范围类型，默认为""(全部)。
    """
    u = ensure_user_fresh(user)
    host_header = f"tquerycoreapi{u.index}.1234567.com.cn"
    if not u.index:
        host_header = "tquerycoreapi1.1234567.com.cn"
    url = f"https://{host_header}/api/mobile/Query/GetOneFundTranInfos"
    
    session = requests.Session()
    # 使用 HostResolveAdapter 强制解析域名到指定 IP
    session.mount(f"https://{host_header}/", HostResolveAdapter(host_header, "114.141.184.84"))

    # 定义内部请求函数以支持重试
    def _fetch_page(p_index, p_size, d_type, start_date=None, end_date=None, retry=True):
        curr_u = ensure_user_fresh(user)
        
        headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-Hans-CN;q=1",
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "GTOKEN": "4474AFD3E15F441E937647556C01C174",
            "Host": host_header,
            "MP-VERSION": "5.5.0-1104",
            "Referer": "https://mpservice.com/329e138b3cb74f17a2e4ba5c23f374c0/release/pages/fundRecord/index",
            "User-Agent": "EMProjJijin/6.5.8 (iPhone; iOS 15.6.1; Scale/3.00)",
            "clientInfo": "ttjj-iPhone12,3-iOS-iOS15.6.1",
            "traceparent": "00-63d20001cab74ce99de3c388f65d6277-0000000000000000-01",
            "tracestate": "pid=0x108ee7460,taskid=0x1507ec120"
        }

        payload_dict = {
            "PageIndex": p_index,
            "PageSize": p_size,
            "FundCode": fund_code,
            "SubAccountNo": "",
            "CustomerNo": curr_u.customer_no,
            "BusType": "",
            "Statu": "",
            "Account": "",
            "TransactionAccountId": "",
            "AccountTypes": ["0", "1", "2"],
            "DateType": d_type if d_type is not None else "",
            "StartDate": "",
            "EndDate": ""
        }
        
        if start_date:
            payload_dict["StartDate"] = start_date
            
        if end_date:
            payload_dict["EndDate"] = end_date

        final_data = {
            "utoken": curr_u.u_token,
            "uid": curr_u.customer_no,
            "mobileKey": MOBILE_KEY,
            "customerNo": curr_u.customer_no,
            "deviceid": MOBILE_KEY,
            "ctoken": curr_u.c_token,
            "serverversion": "6.6.11",
            "rtype": "app",
            "data": json.dumps(payload_dict)
        }

        try:
            # 注意：verify=False 配合 HostResolveAdapter 使用，因为我们手动指定了IP但Host头是域名
            response = session.post(url, headers=headers, json=final_data, verify=False, timeout=10)
            response.raise_for_status()
            resp_json = response.json()
            
            # 检查是否需要刷新 Token (Code=1006 或相关消息)
            if not resp_json.get("Succeed", False) and retry:
                msg = resp_json.get("Message", "")
                code = resp_json.get("Code", 0)
                if code == 1006 or "token" in msg.lower() or "设备" in msg:
                    logger.warning(f"检测到Token/设备ID不一致(Code={code}, Msg={msg})，尝试强制刷新Token并重试...")
                    # 强制刷新 Token
                    ensure_user_fresh(user, force_refresh=True)
                    # 递归调用一次（不再 retry）
                    return _fetch_page(p_index, p_size, d_type, start_date, end_date, retry=False)
            
            if "TotalCount" in resp_json:
                logger.info(f"TotalCount: {resp_json['TotalCount']}, PageSize: {p_size}, PageIndex: {p_index}")
                
            return resp_json

        except Exception as e:
            logger.error(f"API请求异常: {e}", extra=extra)
            return {}

    extra = {"account": getattr(user, "mobile_phone", None), "action": "get_one_fund_tran_infos", "fund_code": fund_code}
    all_results = []
    current_page = page_index
    total_count = None
    max_pages = 500

    # 如果没有指定开始时间，且查询全部，则默认从2000年开始，确保覆盖所有历史
    if not start_date and not date_type:
        start_date = "2000-01-01"

    while current_page <= max_pages:
        response_data = _fetch_page(current_page, page_size, date_type, start_date, end_date)

        if not response_data.get("Succeed", False):
            logger.error(f"获取单基金历史交易失败: {response_data}", extra=extra)
            # 如果是第一页失败，直接返回空；如果是后续页失败，返回已获取的
            if current_page == 1:
                return []
            break

        if total_count is None:
            total_count = response_data.get("TotalCount")
            logger.info(f"预期总条数: {total_count}", extra=extra)

        items = response_data.get("responseObjects") or response_data.get("List") or response_data.get("Data")
        if not items:
            break

        if isinstance(items, list):
            for item in items:
                all_results.append(TradeResult.from_api(item))

        # 终止条件判断
        # 1. 如果已知 TotalCount，且已获取数量达到 TotalCount，则停止
        if total_count is not None:
            if len(all_results) >= total_count:
                logger.info(f"已获取全部 {len(all_results)} 条记录 (TotalCount={total_count})", extra=extra)
                break
        
        # 2. 如果当前页返回数量小于 page_size，通常意味着是最后一页
        # 但如果 TotalCount 还没达到，可能是 API 分页有问题，或者实际上还有更多
        # 这里为了稳健，如果 TotalCount 存在，优先信赖 TotalCount；否则信赖 len(items) < page_size
        if total_count is None and len(items) < page_size:
            break
            
        current_page += 1

    logger.info(f"获取单基金历史交易成功，共 {len(all_results)} 条", extra=extra)
    return all_results

def get_trades_list(user, sub_account_no="", fund_code="", bus_type="", status="", page_index=1, page_size=50, date_type: Optional[str] = "3"):
    """
    获取交易列表
    Args:
        user: User对象，包含用户认证信息
        sub_account_no: 子账户编号，默认为空
        fund_code: 基金代码，默认为空
        bus_type: 业务类型，默认为空
        status: 状态，默认为空
        page_index: 页码，默认为1
        page_size: 每页数量，默认为50
        date_type: 时间范围类型，默认为"3"。
                   "5": 近1周
                   "1": 近1月
                   "2": 近3月
                   "3": 近1年 (推荐，能获取较长历史记录)
                   "": 全量查询（通过循环 DateType='3' 和 '0' 并配合结束日期递推实现）
    Returns:
        List[TradeResult]: 交易结果列表
    """
    # 内部辅助函数：请求单次API
    def _fetch_page(p_index, p_size, d_type, end_date=None):
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
            "PageIndex": p_index,
            "PageSize": p_size,
            "FundCode": fund_code,
            "BusType": bus_type,
            "Statu": status,
            "Account": "",
            "SubAccountNo": sub_account_no,
            "CustomerNo": u.customer_no
        }
        
        if d_type:
            payload_dict["DateType"] = d_type
            
        if end_date:
            payload_dict["EndDate"] = end_date

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
        
        try:
            response = requests.post(url, headers=headers, json=data, verify=False)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"API请求失败: {e}")
            return {}

    # 主逻辑
    all_results = []
    
    # 如果指定了 date_type (非空)，则按常规分页逻辑处理
    if date_type:
        current_page = page_index
        max_pages = 100
        while current_page < page_index + max_pages:
            resp = _fetch_page(current_page, page_size, date_type)
            if not resp.get("Succeed", False):
                break
            
            batch = []
            for item in resp.get("responseObjects", []):
                batch.append(TradeResult.from_api(item))
            
            if batch:
                all_results.extend(batch)
            
            if len(batch) < page_size:
                break
            current_page += 1
            
        return all_results
    
    # 如果 date_type 为空，执行全量回溯逻辑
    # 策略：先查近1年(DateType='3')，拿到最早的一条日期，然后作为 EndDate 继续查更早的(DateType='0')
    # 注意：DateType='0' 通常表示自定义时间段或不限，需要配合 EndDate 使用
    
    # 1. 先获取近1年的
    logger.info(f"正在获取近1年交易记录...")
    current_page = 1
    min_date = None
    
    while True:
        resp = _fetch_page(current_page, 50, "3") # DateType='3'
        if not resp.get("Succeed", False):
            break
            
        batch = []
        for item in resp.get("responseObjects", []):
            t = TradeResult.from_api(item)
            batch.append(t)
            # 记录最小日期
            d_str = getattr(t, 'strike_start_date', None) or getattr(t, 'apply_work_day', None)
            if d_str:
                if not min_date or d_str < min_date:
                    min_date = d_str
                    
        if batch:
            all_results.extend(batch)
            
        if len(batch) < 50:
            break
        current_page += 1
        
    logger.info(f"近1年记录获取完毕，共 {len(all_results)} 条。最早日期: {min_date}")
    
    # 2. 递归获取更早的记录
    # 假设 API 支持 EndDate 参数来查询该日期之前的记录
    # 如果 API 不支持 EndDate，那这个方法也无法获取更多。
    # 根据测试结果，DateType='0' 似乎返回了和 '3' 一样的数据（198条），说明 '0' 可能是默认值。
    # 我们尝试用 DateType='0' 且 EndDate = min_date 来获取更早的
    
    # 防止死循环，最多回溯 5 年
    for _ in range(5):
        if not min_date:
            break
            
        logger.info(f"正在尝试获取 {min_date} 之前的记录...")
        
        # 构造 EndDate (减去1天)
        try:
            from datetime import datetime, timedelta
            last_dt = datetime.strptime(min_date[:10], "%Y-%m-%d")
            next_end_date = (last_dt - timedelta(days=1)).strftime("%Y-%m-%d")
        except:
            break
            
        # 尝试查询更早的
        # 这里假设 API 支持 EndDate。如果不支持，这段代码可能只会重复返回相同数据，需要去重。
        current_page = 1
        found_new = False
        batch_results = []
        
        while True:
            # 关键：这里用 DateType='0' 或其他值，并传入 EndDate
            # 注意：如果 API 不识别 EndDate，这可能会返回重复数据，必须去重
            resp = _fetch_page(current_page, 50, "0", end_date=next_end_date)
            
            if not resp.get("Succeed", False):
                break
                
            batch = []
            for item in resp.get("responseObjects", []):
                t = TradeResult.from_api(item)
                # 判重
                if not any(x.id == t.id for x in all_results):
                    batch.append(t)
                    # 更新全局最小日期
                    d_str = getattr(t, 'strike_start_date', None) or getattr(t, 'apply_work_day', None)
                    if d_str and d_str < min_date:
                        min_date = d_str
                        
            if batch:
                batch_results.extend(batch)
                found_new = True
                
            if len(batch) < 50:
                break
            current_page += 1
        
        if found_new:
            logger.info(f"获取到更早的 {len(batch_results)} 条记录。当前最早日期: {min_date}")
            all_results.extend(batch_results)
        else:
            logger.info("未获取到更早记录，结束回溯。")
            break
            
    # 按日期排序
    all_results.sort(key=lambda x: getattr(x, 'strike_start_date', "") or "0000-00-00", reverse=True)
    return all_results
 
def get_trade_order_result(user: User, app_serial_no: str, business_type: str):
    """
    查询指定的交易的结果
    Args:
        user: User对象
        app_serial_no: APP流水号(或busin_serial_no)
        business_type: 业务类型 (默认 "22")
    Returns:
        dict: 交易结果详情
    """
    u = ensure_user_fresh(user)
    host_header = f"tradeapilvs{u.index}.1234567.com.cn"
    if not u.index:
        host_header = "tradeapilvs5.1234567.com.cn"
        
    url = f"https://{host_header}/Trade/FundTrade/OrderResult"
    
    from urllib.parse import quote
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Content-Type": "application/json; charset=utf-8",
        "Host": host_header,
        # Referer 中包含中文 "品种A"，需要进行 URL 编码
        "Referer": f"https://mpservice.com/fund4046e6539c4c47/release/pages/buy-fund/result?key=trad-result-params-tradeno&enterTag={quote('品种A')}",
        "User-Agent": "okhttp/3.12.13",
        "clientInfo": "ttjj-ZTE 7534N-Android-11",
        "gtoken": "ceaf-4a997831b1b3b90849f585f98ca6f30e",
        "mp_instance_id": "92",
        "traceparent": "00-0000000046aa4cae0000019671a9326e-0000000000000000-01",
        "tracestate": "pid=0xc14bf30,taskid=0x10c0d09"
    }

    # 构造 payload
    payload = {
        "ServerVersion": "6.7.1",
        "parentAppSerialNo": "",
        "CustomerNo": u.customer_no,
        "PhoneType": "Android",
        "businType": business_type,
        "MobileKey": MOBILE_KEY,
        "Version": "6.7.1",
        "UserId": u.customer_no,
        "appSerialNo": app_serial_no, 
        "UToken": u.u_token,
        "AppType": "ttjj",
        "tradeModeType": "",
        "CToken": u.c_token
    }
    
    try:
        # 记录请求信息以便调试
        logger.info(f"get_trade_order_result 请求 URL: {url}")
        logger.info(f"get_trade_order_result 请求 Headers: {json.dumps(headers, ensure_ascii=False)}")
        logger.info(f"get_trade_order_result 请求 Payload: {json.dumps(payload, ensure_ascii=False)}")
        
        response = requests.post(url, headers=headers, json=payload, verify=False, timeout=10)
        response.raise_for_status()
        resp_json = response.json()
        
        # 检查是否需要刷新 Token
        if not resp_json.get("Success", False): # 注意这里是 Success 而不是 Succeed
            msg = resp_json.get("Message") or ""
            code = resp_json.get("Code", 0)
            # 兼容可能的错误码
            if code == 1006 or "token" in msg.lower() or "设备" in msg:
                logger.warning(f"检测到Token/设备ID不一致(Code={code}, Msg={msg})，尝试强制刷新Token并重试...")
                u2 = ensure_user_fresh(user, force_refresh=True)
                # 更新 Token 后重试
                payload["UToken"] = u2.u_token
                payload["CToken"] = u2.c_token
                
                # 更新 session adapter 中的 host (如果 index 变了)
                host_header2 = f"tradeapilvs{u2.index}.1234567.com.cn"
                if not u2.index:
                    host_header2 = "tradeapilvs5.1234567.com.cn"
                url2 = f"https://{host_header2}/Trade/FundTrade/OrderResult"
                headers["Host"] = host_header2
                response = requests.post(url2, headers=headers, json=payload, verify=False, timeout=10)
                response.raise_for_status()
                resp_json = response.json()
                
        return resp_json

    except Exception as e:
        logger.error(f"获取交易结果失败: {e}")
        return {}

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
    host_header = f"tradeapilvs{u.index}.1234567.com.cn"
    if not u.index:
        host_header = "tradeapilvs1.1234567.com.cn"
    url = f"https://{host_header}/User/home/GetShareDetail"
    
    headers = {
        "Connection": "keep-alive",
        "Host": host_header,
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
            
            host_header2 = f"tradeapilvs{u2.index}.1234567.com.cn"
            if not u2.index:
                host_header2 = "tradeapilvs1.1234567.com.cn"
            url2 = f"https://{host_header2}/User/home/GetShareDetail"
            
            # 更新Host头
            headers["Host"] = host_header2
            
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
            
            host_header2 = f"tradeapilvs{u2.index}.1234567.com.cn"
            if not u2.index:
                host_header2 = "tradeapilvs1.1234567.com.cn"
            url2 = f"https://{host_header2}/User/home/GetShareDetail"
            headers["Host"] = host_header2

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
    from src.domain.user.User import User
    
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 测试遍历交易列表查询结果
    logger.info("开始获取交易列表并逐个查询结果...")
    
    # 获取最近 20 条交易记录
    trades = get_trades_list(DEFAULT_USER, page_size=20, date_type="1")
    logger.info(f"获取到 {len(trades)} 条交易记录")
    
    for i, trade in enumerate(trades):
        app_serial_no = getattr(trade, 'busin_serial_no', None) or getattr(trade, 'id', None)
        if not app_serial_no:
            logger.warning(f"第 {i+1} 条交易无流水号，跳过: {trade}")
            continue
            
        # 确定 business_type
        # 优先使用 business_code (数字编码), 其次尝试 business_type (可能是中文描述)
        # 如果 business_type 是数字，也可以用
        b_code = getattr(trade, 'business_code', None)
        b_type = getattr(trade, 'business_type', None)
        
        # target_business_type = "22" # 默认值
        
        if b_code:
            target_business_type = str(b_code)
        elif b_type and str(b_type).isdigit():
             target_business_type = str(b_type)
        elif b_type:
             target_business_type = str(b_type)
        
        product_name = getattr(trade, 'product_name', '未知')
        logger.info(f"正在查询第 {i+1}/{len(trades)} 条交易结果: serial_no={app_serial_no}, type={target_business_type}, name={product_name}")
        
        try:
            result = get_trade_order_result(DEFAULT_USER, app_serial_no, business_type=target_business_type)
            # 简略打印结果
            success = result.get("Success", False)
            msg = result.get("ErrorMessage") or result.get("Message")
            logger.info(f"查询结果: Success={success}, Msg={msg}")
        except Exception as e:
            logger.error(f"查询异常: {e}")
            
    logger.info("测试完成")
    
