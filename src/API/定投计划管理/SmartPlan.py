import logging

if __name__ == "__main__":
    import os
    import sys

    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
from src.common.logger import get_logger
from src.API.登录接口.login import ensure_user_fresh
import urllib.parse
import hashlib
import requests
import requests
from urllib.parse import quote_plus
from typing import Dict, Any, Optional, Union,List
import uuid, secrets, time

# 然后进行其他导入
from src.service.基金信息.基金信息 import get_all_fund_info
from src.domain.fund.fund_info import FundInfo
from src.domain.user.User import User 
from src.domain.fund_plan import ApiResponse, FundPlanResponse, PageInfo, FundPlan
from src.domain.fund_plan.fund_plan_detail import FundPlanDetail
from src.domain.fund_plan import RationCreateParameters, DiscountRate
from src.domain.trade.share import Share
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.common.constant import (
    SERVER_VERSION, PAGE_SIZE, PASSPORT_CTOKEN, PLAN_TYPE,
    PASSPORT_UTOKEN, PHONE_TYPE, MOBILE_KEY, PAGE_INDEX,
    USER_ID, U_TOKEN, C_TOKEN, PASSPORT_ID, DEFAULT_USER
)
from src.common.errors import RetriableError, ValidationError, NonRetriableError


def parse_amount(amount_str: str) -> float:
    """
    解析金额字符串为浮点数
    Args:
        amount_str: 金额字符串，可能包含逗号、'元'后缀或'--'
    Returns:
        float: 解析后的金额，如果无法解析则返回0.0
    """
    if not amount_str or amount_str == '--' or amount_str == 'null':
        return 0.0
        
    try:
        # 移除'元'后缀、所有逗号和空格
        cleaned_str = str(amount_str).replace('元', '').replace(',', '').strip()
        return float(cleaned_str)
    except (ValueError, TypeError):
        return 0.0

def parse_int(value: Any) -> int:
    """
    解析整数值
    Args:
        value: 任意值
    Returns:
        int: 解析后的整数，如果无法解析则返回0
    """
    # 处理空值情况
    if value is None or value == '--' or value == '' or value == 'null':
        return 0
    try:
        if isinstance(value, str):
            # 移除逗号和空格
            cleaned_str = value.replace(',', '').strip()
            # 如果清理后的字符串为空，返回0
            if not cleaned_str:
                return 0
            return int(float(cleaned_str))
        return int(value)
    except (ValueError, TypeError):
        return 0


def getFundRations(user, page_index=1, page_size=1000, planTypes=None, fundTypes=None) -> ApiResponse[FundPlanResponse]:
    """
    获取基金定投计划列表
    
    参数:
    user: 用户对象
    page_index: 页码，默认为1
    page_size: 每页数量，默认为1000
    planTypes: 计划类型数组，1代表目标止盈定投，2代表普通组合定投
    fundTypes: 基金类型数组，0代表指数基金，1代表股票型，2代表混合型，5代表QDII,默认为空数组
    """
    # 初始化参数默认值
    if planTypes is None:
        planTypes = []
    else:
        # 确保planTypes只包含1和2
        planTypes = [pt for pt in planTypes if pt in [1, 2]]
        
    if fundTypes is None:
        fundTypes = []
    else:
        # 确保fundTypes只包含0、1和2
        fundTypes = [ft for ft in fundTypes if ft in [0, 1, 2]]

    u = ensure_user_fresh(user)
    url = f'https://ibgapi{u.index}.1234567.com.cn/ration-list/getFundRations'
    
    headers = {
        'Connection': 'keep-alive',
        'Host': f'ibgapi{u.index}.1234567.com.cn',
        'Accept': '*/*',
        'GTOKEN': '4474AFD3E15F441E937647556C01C174',
        'clientInfo': 'ttjj-iPhone 11 Pro-iOS-iOS16.2',
        'MP-VERSION': '4.10.4',
        'Content-Type': 'application/json',
        'Accept-Language': 'zh-Hans-CN;q=1',
        'User-Agent': 'EMProjJijin/6.6.12 (iPhone; iOS 16.2; Scale/3.00)',
        'Referer': 'https://mpservice.com/fund7a71775da8f2ce/release/pages/home-sub-page/index',
        'traceparent': '00-4d761c9a842d43438229a02432ff17e6-0000000000000000-01'
    }
    
    body = {
        "ServerVersion": SERVER_VERSION,
        "planTypes": planTypes,  # 使用传入的planTypes参数
        "pageSize": page_size,
        "passportctoken": u.passport_ctoken,
        "fundTypes": fundTypes,  # 使用传入的fundTypes参数
        "passportutoken": u.passport_utoken,
        "PhoneType": PHONE_TYPE,
        "pageIndex": page_index,
        "periodTypes": [],
        "sortType": "1",
        "MobileKey": MOBILE_KEY,
        "UserId": u.customer_no,
        "planStates": 0,
        "UToken": u.u_token,
        "usingNew": False,
        "CToken": u.c_token,
        "passportid": u.passport_id
    }
    
    logger = get_logger("SmartPlan")
    extra = {"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "action": "getFundRations"}
    try:
        response = requests.post(url, json=body, headers=headers, verify=False)
        response.raise_for_status()
        json_data = response.json()
        # logger.debug(f"响应数据: {json_data}")
        try:
            data = json_data.get('Data')
            if data is None:
                if not json_data.get('Success', False):
                    u2 = ensure_user_fresh(u, force_refresh=True)
                    url2 = f'https://ibgapi{u2.index}.1234567.com.cn/ration-list/getFundRations'
                    body2 = dict(body)
                    body2["passportctoken"] = u2.passport_ctoken
                    body2["passportutoken"] = u2.passport_utoken
                    body2["UserId"] = u2.customer_no
                    body2["UToken"] = u2.u_token
                    body2["CToken"] = u2.c_token
                    body2["passportid"] = u2.passport_id
                    headers2 = dict(headers)
                    headers2['Host'] = f'ibgapi{u2.index}.1234567.com.cn'
                    r2 = requests.post(url2, json=body2, headers=headers2, verify=False)
                    r2.raise_for_status()
                    jd2 = r2.json()
                    data = jd2.get('Data')
                    if data is None and not jd2.get('Success', False):
                        return ApiResponse(
                            Success=jd2.get('Success', False),
                            ErrorCode=jd2.get('ErrorCode'),
                            Data=None,
                            FirstError=jd2.get('FirstError'),
                            DebugError=jd2.get('DebugError')
                        )
                    json_data = jd2
                raise ValidationError('Data为空')
            plans = []
            for item in data.get('data', []):
                # 在 getFundRations 函数中修改 FundPlan 初始化
                # 尝试从多个可能的字段获取金额
                # API 可能返回 'amount', 'businBalance', 'targetAmount', 'payAmount' 等
                raw_amount = item.get('amount', 0)
                if not raw_amount or str(raw_amount) == '0' or str(raw_amount) == '0.0':
                    # 尝试从 nextDeductDescription 提取 (格式: 下个扣款日 2026-02-12，扣款 1000.00 元)
                    desc = item.get('nextDeductDescription', '')
                    if desc:
                        import re
                        try:
                            match = re.search(r"扣款\D*([\d\.]+)\D*元", desc)
                            if match:
                                raw_amount = match.group(1)
                        except:
                            pass
                
                plan = FundPlan(
                    planId=item.get('planId', ''),
                    fundCode=item.get('productCode', ''),
                    fundName=item.get('productName', ''),
                    fundType='',
                    planState=str(item.get('planState', '')),
                    planBusinessState='',
                    pauseType=None,
                    planExtendStatus=str(item.get('planExtendStatus', '')),
                    planType=str(item.get('planType', '')),
                    periodType=parse_int(item.get('periodType', 0)),
                    periodValue=parse_int(item.get('periodValue', 0)),
                    amount=parse_amount(raw_amount),
                    bankAccountNo='',
                    payType=parse_int(item.get('payType', 0)),
                    subAccountNo='',
                    subAccountName='',
                    currentDay='',
                    buyStrategy='',
                    redeemStrategy='',
                    planAssets=0.0,
                    rationProfit=None,
                    totalProfit=None,
                    rationProfitRate=None,
                    totalProfitRate=None,
                    unitPrice=None,
                    targetRate=None,
                    retreatPercentage=None,
                    renewal=False,
                    redemptionWay=0,
                    planStrategyId='',
                    redeemLimit='',
                    financialType=None,
                    executedAmount=parse_amount(item.get('executedAmount', 0)),
                    executedTime=parse_int(item.get('executedTime', 0)),
                    nextDeductDescription=item.get('nextDeductDescription', ''),
                    nextDeductDate=item.get('nextDeductDate', ''),
                    reTriggerDate='',
                    recentDeductDate=None,
                    bankCode=item.get('bankCode', ''),
                    showBankCode='',
                    shortBankCardNo=item.get('shortBankCardNo', ''),
                )
                plans.append(plan)

            api_response = ApiResponse(
                Success=json_data.get('Success', False),
                ErrorCode=json_data.get('ErrorCode'),
                Data=plans,
                FirstError=json_data.get('FirstError'),
                DebugError=json_data.get('DebugError')
            )
            logger.info(f"定投计划页数: {len(plans)}", extra=extra)
            return api_response
        except Exception as e:
            logger.error(f'解析响应数据失败: {str(e)}', extra=extra)
            raise ValidationError(str(e))
    except requests.exceptions.RequestException as e:
        logger.error(f'请求失败: {str(e)}', extra=extra)
        raise RetriableError(str(e))

def getFundPlanList(fund_code, user) -> List[FundPlan]:
    """
    获取指定基金定投计划列表
    返回: FundPlan对象列表
    """
    u = ensure_user_fresh(user)
    url = f'https://ibgapi{u.index}.1234567.com.cn/asset/getFundPlanListV2'
    params = [
        ('ServerVersion', SERVER_VERSION),
        ('pageSize', PAGE_SIZE),
        ('passportctoken', u.passport_ctoken),
        ('type', PLAN_TYPE),
        ('passportutoken', u.passport_utoken),
        ('subAccountNo', ''),
        ('PhoneType', PHONE_TYPE),
        ('MobileKey', MOBILE_KEY),
        ('fundCode', fund_code),
        ('pageIndex', PAGE_INDEX),
        ('UserId', u.customer_no),
        ('UToken', u.u_token),
        ('CToken', u.c_token),
        ('passportid', u.passport_id),
    ]
    query_string = urllib.parse.urlencode(params)
    full_url = f"{url}?{query_string}"
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Host': f'ibgapi{u.index}.1234567.com.cn',
        'If-Modified-Since': 'Sat, 26 Apr 2025 08:55:51 GMT',
        'Referer': f'https://mpservice.com/fund46516ffab83642/release/pages/home/index?fundCode={fund_code}&subAccountNo=&reference=holdDetail',
        'User-Agent': 'okhttp/3.12.13',
        'clientInfo': 'ttjj-ZTE 7534N-Android-11',
        'content-type': 'application/json',
        'gtoken': 'ceaf-4a997831b1b3b90849f585f98ca6f30e',
        'mp_instance_id': '40',
        'traceparent': '00-0000000046aa4cae00000196719b333e-0000000000000000-01',
        'tracestate': 'pid=0xb01a105,taskid=0x651cc79'
    }
    logger = get_logger("SmartPlan")
    extra = {"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "action": "getFundPlanList", "fund_code": fund_code}
    try:
        response = requests.get(full_url, headers=headers, verify=False)
        response.raise_for_status()
        json_data = response.json()
        
        # 检查API调用是否成功
        # 如果 Success=False 但 ErrorCode=0，视为正常空数据，不报错也不刷新 Token
        if not json_data.get('Success', False):
            error_code = json_data.get('ErrorCode')
            if error_code == 0 or str(error_code) == '0':
                logger.info('获取定投计划返回 Success=False 但 ErrorCode=0，视为正常空数据', extra=extra)
                # 能够继续向下执行，依靠 Data check 处理
            else:
                err = str(json_data.get('FirstError', '') or '')
                need_refresh = any(k in err for k in ['Token', 'token', '凭证', 'passport', '未登录', '请登录', 'UToken', 'CToken', 'passportid', '权限'])
                if need_refresh:
                    logger.warning(f"API调用失败: {err}，尝试刷新Token重试", extra=extra)
                    u2 = ensure_user_fresh(u, force_refresh=True)
                    url2 = f'https://ibgapi{u2.index}.1234567.com.cn/asset/getFundPlanListV2'
                    params2 = [
                        ('ServerVersion', SERVER_VERSION),
                        ('pageSize', PAGE_SIZE),
                        ('passportctoken', u2.passport_ctoken),
                        ('type', PLAN_TYPE),
                        ('passportutoken', u2.passport_utoken),
                        ('subAccountNo', ''),
                        ('PhoneType', PHONE_TYPE),
                        ('MobileKey', MOBILE_KEY),
                        ('fundCode', fund_code),
                        ('pageIndex', PAGE_INDEX),
                        ('UserId', u2.customer_no),
                        ('UToken', u2.u_token),
                        ('CToken', u2.c_token),
                        ('passportid', u2.passport_id),
                    ]
                    query_string2 = urllib.parse.urlencode(params2)
                    full_url2 = f"{url2}?{query_string2}"
                    headers2 = dict(headers)
                    headers2['Host'] = f'ibgapi{u2.index}.1234567.com.cn'
                    
                    response2 = requests.get(full_url2, headers=headers2, verify=False)
                    response2.raise_for_status()
                    json_data = response2.json()
                    
                    if not json_data.get('Success', False):
                        # 重试后再次检查 ErrorCode=0
                        error_code2 = json_data.get('ErrorCode')
                        if error_code2 == 0 or str(error_code2) == '0':
                            logger.info('重试后获取定投计划返回 ErrorCode=0', extra=extra)
                        else:
                            logger.error(f"API重试失败: {json_data.get('FirstError', 'Unknown error')}", extra=extra)
                            raise ValidationError(json_data.get('FirstError') or 'API_FAIL')
            
        data = json_data.get('Data')
        if data is None:
            # 再次检查 ErrorCode=0，如果是则返回空列表
            error_code = json_data.get('ErrorCode')
            if error_code == 0 or str(error_code) == '0':
                logger.info('获取定投计划数据为空 (ErrorCode=0)', extra=extra)
                return []

            logger.error('解析响应数据失败: Data字段为空', extra=extra)
            raise ValidationError('Data为空')
            
        # 提取基金基本信息
        fund_code_val = data.get('fundCode', '')
        fund_name = data.get('fundName', '')
        
        # 提取分页信息中的计划数据
        page_info_data = data.get('pageInfo', {})
        plans_data = page_info_data.get('data', [])
        
        fund_plans = []
        for plan_data in plans_data:
            try:
                # 打印 plan_data 原始数据以排查字段名
                # logger.info(f"plan_data: {plan_data}", extra=extra) # 调试用，生产环境可注释
                
                # 解析executedAmount字段
                executed_amount_str = plan_data.get('executedAmount', '0')
                if executed_amount_str:
                    executed_amount_str = str(executed_amount_str).replace(',', '')
                    executed_amount = float(executed_amount_str)
                else:
                    executed_amount = 0.0

                # 尝试从多个可能的字段获取金额
                # API 可能返回 'amount', 'businBalance', 'targetAmount', 'payAmount' 等
                raw_amount = plan_data.get('amount', 0)
                if not raw_amount or str(raw_amount) == '0' or str(raw_amount) == '0.0':
                    # 尝试从 nextDeductDescription 提取
                    desc = plan_data.get('nextDeductDescription', '')
                    if desc:
                        import re
                        try:
                            match = re.search(r"扣款\D*([\d\.]+)\D*元", desc)
                            if match:
                                raw_amount = match.group(1)
                        except:
                            pass

                plan = FundPlan(
                    planId=plan_data.get('planId', ''),
                    fundCode=fund_code_val,
                    fundName=fund_name,
                    fundType='',
                    planState=str(plan_data.get('planState', '')),
                    planBusinessState='',
                    pauseType=None,
                    planExtendStatus=str(plan_data.get('planExtendStatus', '')),
                    planType=str(plan_data.get('planType', '')),
                    # periodType: 0-日, 1-周, 2-双周, 3-月
                    # API返回的字段可能是 periodType，也可能是其他
                    # 尝试从原始数据中获取更多可能的字段
                    periodType=parse_int(plan_data.get('periodType', 0)), 
                    periodValue=parse_int(plan_data.get('periodValue', 0)),
                    amount=parse_amount(raw_amount),
                    bankAccountNo='',
                    payType=0,
                    subAccountNo=plan_data.get('subAcctId', ''),
                    subAccountName=plan_data.get('subAcctName', ''),
                    currentDay='',
                    buyStrategy='',
                    redeemStrategy='',
                    planAssets=0.0,
                    rationProfit=None,
                    totalProfit=None,
                    rationProfitRate=None,
                    totalProfitRate=None,
                    unitPrice=None,
                    targetRate=None,
                    retreatPercentage=None,
                    renewal=False,
                    redemptionWay=0,
                    planStrategyId='',
                    redeemLimit='',
                    financialType=None,
                    executedAmount=executed_amount,
                    executedTime=plan_data.get('executedTime', 0),
                    nextDeductDescription=plan_data.get('nextDeductDescription', ''),
                    nextDeductDate='',
                    reTriggerDate='',
                    recentDeductDate='',
                    bankCode='',
                    showBankCode='',
                    shortBankCardNo='',
                    subDisband=None,
                    isGdlc=False,
                    retriggerTips='',
                    isDeductDay=False
                )
                fund_plans.append(plan)
            except Exception as e:
                logger.error(f'解析单个计划失败: {str(e)}', extra=extra)
                continue
                
        logger.info(f'{user.customer_name}获取基金{fund_name}{fund_code}定投计划列表成功，共{len(fund_plans)}个计划', extra=extra)
        return fund_plans
        
    except requests.exceptions.RequestException as e:
        logger.error(f'请求失败: {str(e)}', extra=extra)
        raise RetriableError(str(e))
    except Exception as e:
        logger.error(f'获取计划列表失败: {str(e)}', extra=extra)
        raise ValidationError(str(e))


def getRationCreateParameters(fund_code,user) -> ApiResponse[RationCreateParameters]:
    """
    获取基金定投参数信息
    """
    url = f'https://ibgapi{user.index}.1234567.com.cn/ration-create/getRationCreateMainInfo'
    params = [
        ('product', 'EFund'),
        ('ServerVersion', SERVER_VERSION),
        ('bizCode', '39'),
        ('passportctoken', user.passport_ctoken),
        ('passportutoken', user.passport_utoken),
        ('deviceid', MOBILE_KEY),
        ('userid', user.customer_no),
        ('version', SERVER_VERSION),
        ('ctoken', user.c_token),
        ('uid', user.customer_no),
        ('PhoneType', PHONE_TYPE),
        ('MobileKey', MOBILE_KEY),
        ('fundCode', fund_code),
        ('UserId', user.customer_no),
        ('utoken', user.u_token),
        ('plat', 'Android'),
        ('UToken', user.u_token),
        ('passportid', user.passport_id),
        ('CToken', user.c_token),
    ]
    query_string = urllib.parse.urlencode(params)
    full_url = f"{url}?{query_string}"
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Host': f'ibgapi{user.index}.1234567.com.cn',
        'If-Modified-Since': 'Sat, 26 Apr 2025 08:55:51 GMT',
        'Referer': f'https://mpservice.com/fund46516ffab83642/release/pages/home/index?fundCode={fund_code}&subAccountNo=&reference=holdDetail',
        'User-Agent': 'okhttp/3.12.13',
        'clientInfo': 'ttjj-ZTE 7534N-Android-11',
        'content-type': 'application/json',
        'gtoken': 'ceaf-4a997831b1b3b90849f585f98ca6f30e',
        'mp_instance_id': '40',
        'traceparent': '00-0000000046aa4cae00000196719ac91d-0000000000000000-01',
        'tracestate': 'pid=0xb01a105,taskid=0xa539a9d'
    }
        
    logger = get_logger("RationCreate")
    extra = {"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "action": "getRationCreateParameters", "fund_code": fund_code}
    try:
        response = requests.get(full_url, headers=headers, verify=False)
        response.raise_for_status()
        json_data = response.json()
        try:
            data = json_data.get('Data')
            if data is None:
                if not json_data.get('Success', False):
                    return ApiResponse(
                        Success=json_data.get('Success', False),
                        ErrorCode=json_data.get('ErrorCode'),
                        Data=None,
                        FirstError=json_data.get('FirstError'),
                        DebugError=json_data.get('DebugError')
                    )
                raise ValidationError('Data为空')

            discount_rates = []
            for rate_data in data.get('discountRateList', []):
                discount_rate = DiscountRate(
                    lowerLimit=float(rate_data.get('lowerLimit', 0)),
                    upperLimit=float(rate_data.get('upperLimit', 0)),
                    rate=float(rate_data.get('rate', 0)),
                    strRate=str(rate_data.get('strRate', '')),
                    discount=float(rate_data.get('discount', 0)),
                    strDiscount=str(rate_data.get('strDiscount', '')),
                    discountTips=rate_data.get('discountTips')
                )
                discount_rates.append(discount_rate)

            ration_params = RationCreateParameters(
                planStrategyList=data.get('planStrategyList', []),
                buyStrategyList=data.get('buyStrategyList', []),
                redeemStrategyList=data.get('redeemStrategyList', []),
                couponSelectList=data.get('couponSelectList', []),
                allowRedeemToHqb=data.get('allowRedeemToHqb', False),
                rationAutoPay=data.get('rationAutoPay', False),
                tjdAutoPay=data.get('tjdAutoPay', False),
                naturalDate=data.get('naturalDate', ''),
                closeMarketTip=data.get('closeMarketTip', []),
                fundCode=data.get('fundCode', ''),
                fundName=data.get('fundName', ''),
                fundType=data.get('fundType', ''),
                fundTypeTwo=data.get('fundTypeTwo', ''),
                fundTypeName=data.get('fundTypeName', ''),
                chargeTypeName=data.get('chargeTypeName', ''),
                fundRisk=data.get('fundRisk', ''),
                fundRiskName=data.get('fundRiskName', ''),
                enableDt=data.get('enableDt', False),
                financialType=data.get('financialType', ''),
                majorFundCode=data.get('majorFundCode', ''),
                isHKFund=data.get('isHKFund', False),
                isHqbFund=data.get('isHqbFund', False),
                isFinancialFund=data.get('isFinancialFund', False),
                isSpecialRateFund=data.get('isSpecialRateFund', False),
                supportSubAccount=data.get('supportSubAccount', False),
                minBusinLimit=data.get('minBusinLimit', ''),
                maxBusinLimit=data.get('maxBusinLimit', ''),
                discountRateList=discount_rates,
                orderNo=data.get('orderNo', ''),
                forceRationCode=data.get('forceRationCode'),
                isSale=data.get('isSale', False),
                isSupportWitRation=data.get('isSupportWitRation', False)
            )

            api_response = ApiResponse(
                Success=json_data.get('Success', False),
                ErrorCode=json_data.get('ErrorCode'),
                Data=ration_params,
                FirstError=json_data.get('FirstError'),
                DebugError=json_data.get('DebugError')
            )
            return api_response
        except Exception as e:
            logger.error(f'解析响应数据失败: {str(e)}', extra=extra)
            raise ValidationError(str(e))
    except requests.exceptions.RequestException as e:
        logger.error(f'请求失败: {str(e)}', extra=extra)
        raise RetriableError(str(e))

def getPlanDetailPro(plan_id, user) -> ApiResponse[FundPlanDetail]:
    """
    获取定投计划详情
    """
    u = ensure_user_fresh(user)
    url = f'https://ibgapi{u.index}.1234567.com.cn/ration/getPlanDetailPro'
    data = {
        'product': 'EFund',
        'ServerVersion': SERVER_VERSION,
        'PlanId': plan_id,
        'passportctoken': u.passport_ctoken,
        'passportutoken': u.passport_utoken,
        'deviceid': MOBILE_KEY,
        'userid': u.customer_no,
        'version': SERVER_VERSION,
        'ctoken': u.c_token,
        'uid': u.customer_no,
        'PhoneType': PHONE_TYPE,
        'MobileKey': MOBILE_KEY,
        'UserId': u.customer_no,
        'utoken': u.u_token,
        'plat': 'Android',
        'UToken': u.u_token,
        'passportid': u.passport_id,
        'CToken': u.c_token
    }
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json; charset=utf-8',
        'Host': f'ibgapi{u.index}.1234567.com.cn',
        'Referer': f'https://mpservice.com/fund46516ffab83642/release/pages/plan-detail/index?planId={plan_id}',
        'User-Agent': 'okhttp/3.12.13',
        'clientInfo': 'ttjj-ZTE 7534N-Android-11',
        'gtoken': 'ceaf-4a997831b1b3b90849f585f98ca6f30e',
        'mp_instance_id': '14'
    }
    logger = get_logger("SmartPlan")
    extra = {"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "action": "getPlanDetailPro", "plan_id": plan_id}
    try:
        response = requests.post(url, json=data, headers=headers, verify=False)
        response.raise_for_status()
        json_data = response.json()
        try:
            data = json_data.get('Data')
            if data is None:
                if not json_data.get('Success', False):
                    u2 = ensure_user_fresh(u, force_refresh=True)
                    url2 = f'https://ibgapi{u2.index}.1234567.com.cn/ration/getPlanDetailPro'
                    data2 = dict(data)
                    data2['passportctoken'] = u2.passport_ctoken
                    data2['passportutoken'] = u2.passport_utoken
                    data2['userid'] = u2.customer_no
                    data2['ctoken'] = u2.c_token
                    data2['uid'] = u2.customer_no
                    data2['UserId'] = u2.customer_no
                    data2['utoken'] = u2.u_token
                    data2['UToken'] = u2.u_token
                    data2['passportid'] = u2.passport_id
                    data2['CToken'] = u2.c_token
                    headers2 = dict(headers)
                    headers2['Host'] = f'ibgapi{u2.index}.1234567.com.cn'
                    r2 = requests.post(url2, json=data2, headers=headers2, verify=False)
                    r2.raise_for_status()
                    jd2 = r2.json()
                    d2 = jd2.get('Data')
                    if d2 is None and not jd2.get('Success', False):
                        return ApiResponse(
                            Success=jd2.get('Success', False),
                            ErrorCode=jd2.get('ErrorCode'),
                            Data=None,
                            FirstError=jd2.get('FirstError'),
                            DebugError=jd2.get('DebugError')
                        )
                    json_data = jd2
                raise ValidationError('Data为空')

            ration_plan_data = data.get('rationPlan', {})
            ration_plan = FundPlan(
                planId=ration_plan_data.get('planId', ''),
                fundCode=ration_plan_data.get('fundCode', ''),
                fundName=ration_plan_data.get('fundName', ''),
                fundType=ration_plan_data.get('fundType', ''),
                planState=str(ration_plan_data.get('planState', '')),
                planBusinessState=str(ration_plan_data.get('planBusinessState', '')),
                pauseType=ration_plan_data.get('pauseType'),
                planExtendStatus=str(ration_plan_data.get('planExtendStatus', '')),
                planType=str(ration_plan_data.get('planType', '')),
                periodType=parse_int(ration_plan_data.get('periodType', 0)),
                periodValue=parse_int(ration_plan_data.get('periodValue', 0)),
                amount=float(str(ration_plan_data.get('amount', 0)).replace(',', '')),
                bankAccountNo=ration_plan_data.get('bankAccountNo', ''),
                payType=parse_int(ration_plan_data.get('payType', 0)),
                subAccountNo=ration_plan_data.get('subAccountNo', ''),
                subAccountName=ration_plan_data.get('subAccountName', ''),
                currentDay=ration_plan_data.get('currentDay', ''),
                buyStrategy=str(ration_plan_data.get('buyStrategy', '')),
                redeemStrategy=str(ration_plan_data.get('redeemStrategy', '')),
                planAssets=float(str(ration_plan_data.get('planAssets') or 0).replace(',', '')),
                rationProfit=ration_plan_data.get('rationProfit'),
                totalProfit=ration_plan_data.get('totalProfit'),
                rationProfitRate=ration_plan_data.get('rationProfitRate'),
                totalProfitRate=ration_plan_data.get('totalProfitRate'),
                unitPrice=ration_plan_data.get('unitPrice'),
                targetRate=ration_plan_data.get('targetRate'),
                retreatPercentage=ration_plan_data.get('retreatPercentage'),
                renewal=ration_plan_data.get('renewal', False),
                redemptionWay=parse_int(ration_plan_data.get('redemptionWay', 0)),
                planStrategyId=ration_plan_data.get('planStrategyId', ''),
                redeemLimit=ration_plan_data.get('redeemLimit', '')
            )
            shares_data = data.get('shares', [])
            shares = []
            if shares_data is not None:  # 添加这个检查
                for share_data in shares_data:
                    share = Share(
                        availableVol=float(str(share_data.get('availableVol', 0)).replace(',', '')),
                        bankCode=share_data.get('bankCode', ''),
                        showBankCode=share_data.get('showBankCode', ''),
                        bankCardNo=share_data.get('bankCardNo', ''),
                        bankName=share_data.get('bankName', ''),
                        shareId=share_data.get('shareId', ''),
                        bankAccountNo=share_data.get('bankAccountNo', ''),
                        totalVol=float(str(share_data.get('totalVol', 0)).replace(',', ''))
                    )
                    shares.append(share)

            profit_trends = data.get('profitTrends', [])

            fund_plan_detail = FundPlanDetail(
                rationPlan=ration_plan,
                profitTrends=profit_trends,
                couponDetail=data.get('couponDetail'),
                shares=shares
            )

            api_response = ApiResponse(
                Success=json_data.get('Success', False),
                ErrorCode=json_data.get('ErrorCode'),
                Data=fund_plan_detail,
                FirstError=json_data.get('FirstError'),
                DebugError=json_data.get('DebugError')
            )
            return api_response
        except Exception as e:
            logger.error(f'解析响应数据失败: {str(e)}', extra=extra)
            raise ValidationError(str(e))
    except requests.exceptions.RequestException as e:
        logger.error(f'请求失败: {str(e)}', extra=extra)
        raise RetriableError(str(e))


def operateRation(user, plan_id: str, operation: str) -> ApiResponse[FundPlanDetail]:
    """
    操作定投计划
    Args:
        user: User对象，包含用户认证信息
        plan_id: 定投计划ID
        operation: 操作类型（2-终止计划）
        fund_name: 基金名称
    Returns:
        ApiResponse[FundPlanDetail]: 操作结果
    """
    url = f'https://ibgapi{user.index}.1234567.com.cn/ration/operateRation'
    md5_password = hashlib.md5(user.password.encode('utf-8')).hexdigest()
    body = {
        "product": "EFund",
        "ServerVersion": SERVER_VERSION,
        "Password": md5_password,
        "passportctoken": user.passport_ctoken,
        "passportutoken": user.passport_utoken,
        "deviceid": MOBILE_KEY,
        "userid": user.customer_no,
        "version": SERVER_VERSION,
        "ctoken": user.c_token,
        "uid": user.customer_no,
        "PhoneType": PHONE_TYPE,
        "MobileKey": MOBILE_KEY,
        "UserId": user.customer_no,
        "utoken": user.u_token,
        "planId": plan_id,
        "plat": "Android",
        "UToken": user.u_token,
        "operation": operation,
        "passportid": user.passport_id,
        "CToken": user.c_token
    }
    
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Host': f'ibgapi{user.index}.1234567.com.cn',
        'Content-Type': 'application/json; charset=utf-8',
        'User-Agent': 'okhttp/3.12.13',
        'clientInfo': 'ttjj-ZTE 7534N-Android-11',
        'mp_instance_id': '80'
    }
    
    logger = get_logger("SmartPlan")
    extra = {"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "action": "operateRation", "plan_id": plan_id}
    try:
        response = requests.post(url, json=body, headers=headers, verify=False)
        response.raise_for_status()
        json_data = response.json()
        
        try:
            data = json_data.get('Data')
            if data is None:
                if not json_data.get('Success', False):
                    return ApiResponse(
                        Success=json_data.get('Success', False),
                        ErrorCode=json_data.get('ErrorCode'),
                        Data=None,
                        FirstError=json_data.get('FirstError'),
                        DebugError=json_data.get('DebugError')
                    )
                raise ValidationError('Data为空')

            # 解析提示信息
            tips = []
            for tip_data in data.get('tips', []):
                tips.append({
                    'title': tip_data.get('title', ''),
                    'subTitle': tip_data.get('subTitle', ''),
                    'thirdTitle': tip_data.get('thirdTitle')
                })

            plan = FundPlan(
                planId=data.get('planId', ''),
                fundCode=data.get('fundCode', ''),
                fundName=data.get('fundName', ''),
                fundType=data.get('fundType', ''),
                planState=str(data.get('planState', '1')),
                planBusinessState=str(data.get('planBusinessState', '')),
                pauseType=data.get('pauseType'),
                planExtendStatus=str(data.get('planExtendStatus', '')),
                planType=str(data.get('rationType', '1')),
                periodType=parse_int(data.get('periodType', 4)),
                periodValue=parse_int(data.get('periodValue', 1)),
                amount=float(str(data.get('amount', '0')).replace(',', '') if data.get('amount') else 0),
                bankAccountNo=data.get('bankAccountNo', ''),
                payType=parse_int(data.get('payType', 1)),
                subAccountNo=data.get('subAccountNo', ''),
                subAccountName=data.get('subAccountName', ''),
                currentDay=data.get('applyTime', '').split(' ')[0] if data.get('applyTime') else '',
                buyStrategy=str(data.get('buyStrategy', '1')),
                redeemStrategy=str(data.get('redeemStrategy', '1')),
                planAssets=float(str(data.get('planAssets', 0)).replace(',', '') if data.get('planAssets') else 0),
                rationProfit=data.get('rationProfit'),
                totalProfit=data.get('totalProfit'),
                rationProfitRate=data.get('rationProfitRate'),
                totalProfitRate=data.get('totalProfitRate'),
                unitPrice=data.get('unitPrice'),
                targetRate=data.get('targetRate'),
                retreatPercentage=data.get('retreatPercentage'),
                renewal=data.get('renewal', True),
                redemptionWay=parse_int(data.get('redemptionWay', 1)),
                planStrategyId=data.get('planStrategyId', ''),
                redeemLimit=data.get('redeemLimit', '1')
            )
            
            # 创建FundPlanDetail对象，使用正确的参数
            plan_detail = FundPlanDetail(
                rationPlan=plan,
                profitTrends=[],
                couponDetail=data.get('couponInfo'),
                shares=[]
            )
            
            return ApiResponse(
                Success=json_data.get('Success', False),
                ErrorCode=json_data.get('ErrorCode'),
                Data=plan_detail,
                FirstError=json_data.get('FirstError'),
                DebugError=json_data.get('DebugError')
            )
            
        except Exception as e:
            logger.error(f'解析响应数据失败: {str(e)}', extra=extra)
            raise ValidationError(str(e))
            
    except requests.exceptions.RequestException as e:
        logger.error(f'请求失败: {str(e)}', extra=extra)
        raise RetriableError(str(e))


def createPlanV3(user, fund_code: str, amount: str = "2000.0", period_type: int = 4, 
                 period_value: str = "1", sub_account_name = None, strategy_type: int = 0,
                 target_profit_rate: Optional[Union[str, float, int]] = None) -> ApiResponse[FundPlan]:
    """
    创建基金定投计划V3版本
    Args:
        user: User对象，包含用户认证信息
        fund_code: 基金代码
        amount: 定投金额，默认2000元
        period_type: 定投周期类型 (4: 每日)
        period_value: 定投周期值
        strategy_type: 策略类型 (0: 目标止盈定投)
        sub_account_name: 子账户名称，可选参数
        target_profit_rate: 目标止盈百分比，支持 0.1/10/'10%'/None 等格式，None 默认 10%
    Returns:
        ApiResponse[FundPlan]: 定投计划创建结果
    """
    logger = get_logger("SmartPlan")
    extra = {"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "action": "createPlanV3", "fund_code": fund_code}
    
    # 获取基金限额并检查
    try:
        fund_info = get_all_fund_info(user, fund_code)
        if not fund_info:
            logger.warning(f"无法获取基金{fund_code}的信息")
            return ApiResponse(Success=False, ErrorCode="FUND_INFO_MISSING", Data=None, FirstError="基金信息获取失败", DebugError=None)
            
        if not hasattr(fund_info, 'max_purchase') or not fund_info.max_purchase:
            logger.warning(f"基金{fund_code}缺少限额信息")
            return ApiResponse(Success=False, ErrorCode="LIMIT_INFO_MISSING", Data=None, FirstError="基金限额信息缺失", DebugError=None)
            
        max_amount = float(fund_info.max_purchase)
        request_amount = float(amount)
        
        logger.info(f"基金{fund_code}限额检查: 请求金额{request_amount}, 限额{max_amount}")
        
        if request_amount > max_amount:
            logger.warning(f"定投金额{request_amount}超过基金限额{max_amount}")
            # 自动调整为限额金额
            amount = str(max_amount)
            logger.info(f"已自动调整定投金额为限额值: {amount}")
            
    except Exception as e:
        logger.error(f"限额检查失败: {str(e)}")
        return ApiResponse(Success=False, ErrorCode="LIMIT_CHECK_FAILED", Data=None, FirstError="基金限额检查失败", DebugError=str(e))
    
    md5_password = hashlib.md5(user.password.encode('utf-8')).hexdigest()  
    url = f'https://ibgapi{user.index}.1234567.com.cn/ration/createPlanV3'
    
    # 如果指定了子账户名称，获取子账户编号
    sub_account_no = None
    if sub_account_name is not None:
        sub_account_no = getSubAccountNoByName(user, sub_account_name)

    # 规范化目标止盈率
    def _fmt_target_rate(v: Optional[Union[str, float, int]]) -> str:
        try:
            if v is None:
                return "10%"
            if isinstance(v, (int, float)):
                val = float(v)
                val = val * 100 if val <= 1 else val
                return f"{val:g}%"
            s = str(v).strip()
            if s.endswith("%"):
                return s
            num = float(s)
            num = num * 100 if num <= 1 else num
            return f"{num:g}%"
        except Exception:
            return "10%"

    target_profit_rate_str = _fmt_target_rate(target_profit_rate)

    # 构建请求体，添加安全检查
    bank_acct_no = user.max_hqb_bank.AccountNo if hasattr(user.max_hqb_bank, 'AccountNo') else 'Not Available'
    body = {
        "minTimes": 0,
        "ServerVersion": "6.7.1",
        "bankAcctNo": bank_acct_no,
        "buyStrategy": 1,
        "userid": user.customer_no,
        "periodValue": period_value,
        "strategyType": strategy_type,
        "reference": "",
        "uid": user.customer_no,
        "payType": 1,
        "fundCode": fund_code,
        "MobileKey": "15a16f86a738f59811cbd40da4da1d97||iemi_tluafed_me",
        "utoken": user.u_token,
        "isCurWorkdayEffect": False,
        "targetProfitRate": target_profit_rate_str,
        "plat": "Android",
        "CToken": user.c_token,
        "Password": md5_password,
        "amount": amount,
        "product": "EFund",
        "orderNo": f"ORD-{int(time.time()*1000)}-{secrets.token_hex(8)}",
        "lockDays": -1,
        "upgrade": True,
        "targetRetraceRate": "10%",
        "renewal": True,
        "redeemLimit": 1,
        "redeemWay": "1",
        "passportctoken": user.passport_ctoken,
        "passportutoken": user.passport_utoken,
        "deviceid": "15a16f86a738f59811cbd40da4da1d97||iemi_tluafed_me",
        "version": "6.7.1",
        "ctoken": user.c_token,
        "maxTimes": 2,
        "periodType": period_type,
        "PhoneType": "Android",
        "redeemStrategy": 2,
        "amountStr": "",
        "UserId": user.customer_no,
        "ruleVersion": "1",
        "UToken": user.u_token,
        "passportid": user.passport_id
    }
    
    # 如果获取到了子账户编号，添加到请求体中
    if sub_account_no is not None:
        body["subAcctNo"] = sub_account_no

    # 构建请求头
    headers = {
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "validmark": "Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZdVcHJ8J2NdZhXTNMQR9BMpxG3EMlqXyJoFeiMLZWZZtJ1DXqiIOSu/kLYsAt37vKDXPe9BVTye1bYiFCvKVkXfAFlxGf+9vZQhrgOcMt8KwY=",
        "mp_instance_id": "40",
        "Referer": "https://mpservice.com/fund46516ffab83642/release/pages/home/index",
        "gtoken": "ceaf-4a997831b1b3b90849f585f98ca6f30e",
        "clientInfo": "ttjj-ZTE 7534N-Android-11",
        "traceparent": f"00-{uuid.uuid4().hex}-{secrets.token_hex(8)}-01",
        "tracestate": f"pid=0x{secrets.token_hex(4)},taskid=0x{secrets.token_hex(4)}",
        "Host": f'ibgapi{user.index}.1234567.com.cn',
        "User-Agent": "okhttp/3.12.13"
    }

    logger = logging.getLogger("SmartPlan")
    try:
        # 发送请求
        response = requests.post(url, json=body, headers=headers, verify=False)
        response.raise_for_status()
        json_data = response.json()
        
        # 处理响应
        if not json_data.get('Success', False):
            return ApiResponse(
                Success=False,
                ErrorCode=json_data.get('ErrorCode'),
                Data=None,
                FirstError=json_data.get('FirstError'),
                DebugError=json_data.get('DebugError')
            )
            
        data = json_data.get('Data')
        if not data:
            raise ValidationError('响应为空')
            
        # 创建FundPlan对象而不是FundPlanDetail对象
        plan = FundPlan(
            planId=data.get('planId', ''),
            fundCode=data.get('fundCode', ''),
            fundName=data.get('fundName', ''),
            fundType='',  # 可能需要从其他地方获取
            financialType=None,
            # 移除这行: isCashBag=False,
            executedAmount=0.0,
            executedTime=0,
            planState='1',  # 假设新创建的计划状态为1（正常）
            planBusinessState='',
            pauseType=None,
            planExtendStatus='',
            planType=data.get('rationType', '1'),
            nextDeductDescription='',
            periodType=period_type,
            periodValue=int(period_value),
            amount=float(amount.replace(',', '')),
            nextDeductDate=data.get('nextWorkday', ''),
            reTriggerDate='',
            recentDeductDate='',
            bankCode=data.get('bankCode', ''),
            showBankCode=data.get('showBankCode', ''),
            shortBankCardNo=data.get('bankCardNo', ''),
            bankAccountNo='',
            payType=data.get('payType', 1),
            subAccountNo=data.get('subAccountNo', ''),
            subAccountName=data.get('subAccountName', ''),
            subDisband=None,
            currentDay=data.get('applyTime', '').split(' ')[0] if data.get('applyTime') else '',
            isGdlc=False,
            buyStrategy='1',
            redeemStrategy='1',
            planAssets=0.0,
            rationProfit=None,
            totalProfit=None,
            rationProfitRate=None,
            totalProfitRate=None,
            unitPrice=None,
            targetRate=None,
            retreatPercentage=None,
            renewal=True,
            redemptionWay=1,
            planStrategyId='',
            
            redeemLimit='1'
        )
        
        # 记录成功创建定投计划的详细信息
        logger.info(f"定投计划创建成功 - 计划ID: {plan.planId}, 基金代码: {plan.fundCode}, 基金名称: {plan.fundName}, 定投金额: {plan.amount}, 定投周期: {plan.periodType}, 子账户: {plan.subAccountName}", extra=extra)
        
        return ApiResponse(
            Success=True,
            ErrorCode=0,
            Data=plan,
            FirstError=None,
            DebugError=None
        )
        
    except requests.exceptions.RequestException as e:
        logger.error(f'请求失败: {str(e)}', extra=extra)
        raise RetriableError(str(e))
    except Exception as e:
        logger.error(f'创建定投计划失败: {str(e)}', extra=extra)
        raise NonRetriableError(str(e))

def updatePlanStatus(user, plan_id: str, buyStrategySwitch: bool):
    """
    操作定投计划
    Args:
        user: User对象，包含用户认证信息
        plan_id: 定投计划ID
        buyStrategySwitch: true 代表恢复买入，false代表暂停）
        fund_name: 基金名称
    Returns:
        ApiResponse[FundPlanDetail]: 操作结果
    """
    url = f'https://ibgapi{user.index}.1234567.com.cn/ration/operateRation'
    md5_password = hashlib.md5(user.password.encode('utf-8')).hexdigest()
    body = {
        "product": "EFund",
        "ServerVersion": SERVER_VERSION,
        "Password": md5_password,
        "passportctoken": user.passport_ctoken,
        "passportutoken": user.passport_utoken,
        "deviceid": MOBILE_KEY,
        "userid": user.customer_no,
        "version": SERVER_VERSION,
        "ctoken": user.c_token,
        "uid": user.customer_no,
        "PhoneType": PHONE_TYPE,
        "MobileKey": MOBILE_KEY,
        "UserId": user.customer_no,
        "utoken": user.u_token,
        "planId": plan_id,
        "plat": "Android",
        "UToken": user.u_token,
        "buyStrategySwitch": buyStrategySwitch,
        "passportid": user.passport_id,
        "CToken": user.c_token
    }
    
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Host': f'ibgapi{user.index}.1234567.com.cn',
        'Content-Type': 'application/json; charset=utf-8',
        'User-Agent': 'okhttp/3.12.13',
        'clientInfo': 'ttjj-ZTE 7534N-Android-11',
        'mp_instance_id': '80'
    }
    
    logger = get_logger("SmartPlan")
    extra = {"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "action": "updatePlanStatus", "plan_id": plan_id}
    try:
        response = requests.post(url, json=body, headers=headers, verify=False)
        response.raise_for_status()
        json_data = response.json()
        
        try:
            data = json_data.get('Data')
            if data is None:
                if not json_data.get('Success', False):
                    return ApiResponse(
                        Success=json_data.get('Success', False),
                        ErrorCode=json_data.get('ErrorCode'),
                        Data=None,
                        FirstError=json_data.get('FirstError'),
                        DebugError=json_data.get('DebugError')
                    )
                raise ValidationError('Data为空')

            # 解析提示信息
            tips = []
            for tip_data in data.get('tips', []):
                tips.append({
                    'title': tip_data.get('title', ''),
                    'subTitle': tip_data.get('subTitle', ''),
                    'thirdTitle': tip_data.get('thirdTitle')
                })

            plan = FundPlan(
                planId=data.get('planId', ''),
                fundCode=data.get('fundCode', ''),
                fundName=data.get('fundName', ''),
                fundType=data.get('fundType', ''),
                planState=str(data.get('planState', '1')),
                planBusinessState=str(data.get('planBusinessState', '')),
                pauseType=data.get('pauseType'),
                planExtendStatus=str(data.get('planExtendStatus', '')),
                planType=str(data.get('rationType', '1')),
                periodType=parse_int(data.get('periodType', 4)),
                periodValue=parse_int(data.get('periodValue', 1)),
                amount=float(str(data.get('amount', '0')).replace(',', '') if data.get('amount') else 0),
                bankAccountNo=data.get('bankAccountNo', ''),
                payType=parse_int(data.get('payType', 1)),
                subAccountNo=data.get('subAccountNo', ''),
                subAccountName=data.get('subAccountName', ''),
                currentDay=data.get('applyTime', '').split(' ')[0] if data.get('applyTime') else '',
                buyStrategy=str(data.get('buyStrategy', '1')),
                redeemStrategy=str(data.get('redeemStrategy', '1')),
                planAssets=float(str(data.get('planAssets', 0)).replace(',', '') if data.get('planAssets') else 0),
                rationProfit=data.get('rationProfit'),
                totalProfit=data.get('totalProfit'),
                rationProfitRate=data.get('rationProfitRate'),
                totalProfitRate=data.get('totalProfitRate'),
                unitPrice=data.get('unitPrice'),
                targetRate=data.get('targetRate'),
                retreatPercentage=data.get('retreatPercentage'),
                renewal=data.get('renewal', True),
                redemptionWay=parse_int(data.get('redemptionWay', 1)),
                planStrategyId=data.get('planStrategyId', ''),
                redeemLimit=data.get('redeemLimit', '1')
            )
            
            # 创建FundPlanDetail对象，使用正确的参数
            plan_detail = FundPlanDetail(
                rationPlan=plan,
                profitTrends=[],
                couponDetail=data.get('couponInfo'),
                shares=[]
            )
            
            return ApiResponse(
                Success=json_data.get('Success', False),
                ErrorCode=json_data.get('ErrorCode'),
                Data=plan_detail,
                FirstError=json_data.get('FirstError'),
                DebugError=json_data.get('DebugError')
            )
            
        except Exception as e:
            logger.error(f'解析响应数据失败: {str(e)}', extra=extra)
            raise ValidationError(str(e))
            
    except requests.exceptions.RequestException as e:
        logger.error(f'请求失败: {str(e)}', extra=extra)
        raise RetriableError(str(e))


def updateRation(user, plan_id: str,
                 amount: Optional[Union[str, float]] = None,
                 period_type: Optional[int] = None,
                 period_value: Optional[Union[str, int]] = None,
                 pay_type: Optional[int] = None,
                 targetRate: Optional[Union[str, float]] = None,
                 renewal: Optional[bool] = None,
                 redemption_way: Optional[int] = None,
                 redeem_strategy: Optional[Union[str, int]] = None,
                 redeem_limit: Optional[str] = None) -> ApiResponse[FundPlanDetail]:
    """
    更新定投计划信息（如金额、周期、扣款方式、止盈百分比、续投、赎回策略、赎回限制）
    - 在更新前必须获取计划详情；未填写的 amount/targetRate/renewal/redemption_way/redeem_strategy/redeem_limit 用详情原值填充并下发
    - 返回更新后的计划概要信息（Data.tips、amount、periodInfo、targetRate 等）
    """
    logger = get_logger("SmartPlan")
    extra = {"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "action": "updateRation", "plan_id": plan_id}

    # 先取当前计划详情，作为默认值来源
    try:
        detail_resp = getPlanDetailPro(plan_id, user)
        if not getattr(detail_resp, "Success", False) or not getattr(detail_resp, "Data", None):
            return ApiResponse(
                Success=False,
                ErrorCode="GET_PLAN_DETAIL_FAILED",
                Data=None,
                FirstError=getattr(detail_resp, "FirstError", "获取计划详情失败"),
                DebugError=getattr(detail_resp, "DebugError", None),
            )
        rp = detail_resp.Data.rationPlan
    except Exception as e:
        return ApiResponse(
            Success=False,
            ErrorCode="GET_PLAN_DETAIL_EXCEPTION",
            Data=None,
            FirstError=str(e),
            DebugError=None,
        )

    # 规范化格式化函数
    def _fmt_amount_str(v: Optional[Union[str, float]]) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        if s == "":
            return None
        if isinstance(v, (int, float)):
            return f"{float(v):.2f}"
        return f"{parse_amount(s):.2f}"

    def _fmt_target_rate(v: Optional[Union[str, float]]) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        if s == "":
            return None
        if isinstance(v, (int, float)):
            return f"{float(v):g}%"
        if s.endswith("%"):
            return s
        try:
            num = float(s)
            return f"{num:g}%"
        except Exception:
            return None

    amount_provided = amount is not None and str(amount).strip() != ""
    # 未提供 amount 时用详情原值（两位小数）填充
    final_amount = _fmt_amount_str(amount) if amount_provided else f"{float(rp.amount):.2f}"

    final_period_type = period_type if period_type is not None else parse_int(rp.periodType)
    final_period_value = parse_int(period_value if period_value is not None else rp.periodValue)
    final_pay_type = pay_type if pay_type is not None else parse_int(rp.payType)

    # 未提供 targetRate 时用详情原值填充（若详情不存在则不下发）
    final_target_rate = (
        _fmt_target_rate(targetRate)
        if (targetRate is not None and str(targetRate).strip() != "")
        else (rp.targetRate if rp.targetRate else None)
    )

    # 处理新增参数：renewal, redemption_way, redeem_strategy, redeem_limit
    final_renewal = renewal if renewal is not None else rp.renewal
    final_redemption_way = redemption_way if redemption_way is not None else parse_int(rp.redemptionWay)
    final_redeem_strategy = str(redeem_strategy) if redeem_strategy is not None else (rp.redeemStrategy or "1")
    final_redeem_limit = str(redeem_limit) if redeem_limit is not None else (rp.redeemLimit or "1")

    url = f"https://ibgapi{user.index}.1234567.com.cn/ration/updateRation"
    md5_password = hashlib.md5(user.password.encode("utf-8")).hexdigest()
    body = {
        "product": "EFund",
        "ServerVersion": SERVER_VERSION,
        "Password": md5_password,
        "passportctoken": user.passport_ctoken,
        "passportutoken": user.passport_utoken,
        "deviceid": MOBILE_KEY,
        "userid": user.customer_no,
        "version": SERVER_VERSION,
        "ctoken": user.c_token,
        "uid": user.customer_no,
        "PhoneType": PHONE_TYPE,
        "MobileKey": MOBILE_KEY,
        "UserId": user.customer_no,
        "utoken": user.u_token,
        "planId": plan_id,
        "plat": "Android",
        "UToken": user.u_token,
        "passportid": user.passport_id,
        "CToken": user.c_token,
        "fundCode": rp.fundCode,
        "periodType": final_period_type,
        "periodValue": str(final_period_value),
        "payType": final_pay_type,
        # 新增字段
        "renewal": final_renewal,
        "redemptionWay": final_redemption_way,
        "redeemStrategy": final_redeem_strategy,
        "redeemLimit": final_redeem_limit,
    }
    # 始终携带 amount（用入参或原值）
    body["amount"] = final_amount
    # targetRate 若有入参或详情原值则携带
    if final_target_rate is not None and str(final_target_rate).strip() != "":
        body["targetRate"] = final_target_rate
        # 兼容：更新接口常用 targetProfitRate 字段
        body["targetProfitRate"] = final_target_rate
        # 补充回撤率（若详情存在），避免策略字段缺失导致止盈更新不生效
        if rp.retreatPercentage:
            body["targetRetraceRate"] = str(rp.retreatPercentage)

    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Content-Type": "application/json; charset=utf-8",
        "Host": f"ibgapi{user.index}.1234567.com.cn",
        "Referer": f"https://mpservice.com/fund46516ffab83642/release/pages/plan-detail/index?planId={plan_id}",
        "User-Agent": "okhttp/3.12.13",
        "clientInfo": "ttjj-ZTE 7534N-Android-11",
        "gtoken": "ceaf-4a997831b1b3b90849f585f98ca6f30e",
        "mp_instance_id": "14",
    }

    try:
        resp = requests.post(url, json=body, headers=headers, verify=False)
        resp.raise_for_status()
        json_data = resp.json()
        try:
            data = json_data.get("Data")
            if data is None:
                if not json_data.get("Success", False):
                    return ApiResponse(
                        Success=json_data.get("Success", False),
                        ErrorCode=json_data.get("ErrorCode"),
                        Data=None,
                        FirstError=json_data.get("FirstError"),
                        DebugError=json_data.get("DebugError"),
                    )
                raise ValidationError("Data为空")

            amount_fallback = final_amount
            plan = FundPlan(
                planId=data.get("planId", plan_id),
                fundCode=data.get("fundCode", rp.fundCode),
                fundName=data.get("fundName", rp.fundName),
                fundType="",
                planState=str(data.get("planState", "1")),
                planBusinessState=str(data.get("planBusinessState", "")),
                pauseType=data.get("pauseType"),
                planExtendStatus=str(data.get("planExtendStatus", "")),
                planType=str(data.get("planConfigId", rp.planType)),
                periodType=parse_int(data.get("periodType", final_period_type)),
                periodValue=parse_int(data.get("periodValue", final_period_value)),
                amount=parse_amount(str(data.get("amount", amount_fallback))),
                bankAccountNo=data.get("bankAccountNo", rp.bankAccountNo or ""),
                payType=parse_int(data.get("payType", final_pay_type)),
                subAccountNo=data.get("subAccountNo", rp.subAccountNo or ""),
                subAccountName=data.get("subAccountName", rp.subAccountName or ""),
                currentDay=(data.get("applyTime", "") or "").split(" ")[0] if data.get("applyTime") else (rp.currentDay or ""),
                buyStrategy=str(rp.buyStrategy or "1"),
                redeemStrategy=str(data.get("redeemStrategy") or final_redeem_strategy or "1"),
                planAssets=parse_amount(data.get("planAssets", rp.planAssets or 0)),
                rationProfit=None,
                totalProfit=None,
                rationProfitRate=None,
                totalProfitRate=None,
                unitPrice=None,
                targetRate=data.get("targetRate", final_target_rate),
                retreatPercentage=None,
                renewal=data.get("renewal", final_renewal),
                redemptionWay=parse_int(data.get("redemptionWay", final_redemption_way)),
                planStrategyId="",
                redeemLimit=data.get("redeemLimit", final_redeem_limit),
            )

            plan_detail = FundPlanDetail(
                rationPlan=plan,
                profitTrends=[],
                couponDetail=data.get("couponInfo"),
                shares=[],
            )

            return ApiResponse(
                Success=json_data.get("Success", False),
                ErrorCode=json_data.get("ErrorCode"),
                Data=plan_detail,
                FirstError=json_data.get("FirstError"),
                DebugError=json_data.get("DebugError"),
            )
        except Exception as e:
            logger.error(f"解析响应数据失败: {str(e)}", extra=extra)
            raise ValidationError(str(e))
    except requests.exceptions.RequestException as e:
        logger.error(f"请求失败: {str(e)}", extra=extra)
        raise RetriableError(str(e))
