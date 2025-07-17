import sys
import os
import logging
import urllib.parse
import urllib3
import warnings
import hashlib
import requests
from urllib.parse import quote_plus
from typing import Dict, Any, Optional, Union,List

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

# 然后进行其他导入
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
    planTypes: 计划类型数组，1代表普通定投，2代表目标止盈定投，默认为空数组
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

    url = f'https://ibgapi{user.index}.1234567.com.cn/ration-list/getFundRations'
    
    headers = {
        'Connection': 'keep-alive',
        'Host': f'ibgapi{user.index}.1234567.com.cn',
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
        "passportctoken": user.passport_ctoken,
        "fundTypes": fundTypes,  # 使用传入的fundTypes参数
        "passportutoken": user.passport_utoken,
        "PhoneType": PHONE_TYPE,
        "pageIndex": page_index,
        "periodTypes": [],
        "sortType": "1",
        "MobileKey": MOBILE_KEY,
        "UserId": user.customer_no,
        "planStates": 0,
        "UToken": user.u_token,
        "usingNew": False,
        "CToken": user.c_token,
        "passportid": user.passport_id
    }
    
    logger = logging.getLogger("SmartPlan")
    try:
        response = requests.post(url, json=body, headers=headers, verify=False)
        response.raise_for_status()
        json_data = response.json()
        # logger.debug(f"响应数据: {json_data}")
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
                raise Exception('解析响应数据失败: Data字段为空')
            plans = []
            for item in data.get('data', []):
                # 在 getFundRations 函数中修改 FundPlan 初始化
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
                    amount=parse_amount(item.get('amount', 0)),
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
            return api_response
        except Exception as e:
            logger.error(f'解析响应数据失败: {str(e)}')
            raise Exception(f'解析响应数据失败: {str(e)}')
    except requests.exceptions.RequestException as e:
        logger.error(f'请求失败: {str(e)}')
        raise Exception(f'请求失败: {str(e)}')

def getFundPlanList(fund_code, user) -> List[FundPlan]:
    """
    获取指定基金定投计划列表
    返回: FundPlan对象列表
    """
    url = f'https://ibgapi{user.index}.1234567.com.cn/asset/getFundPlanListV2'
    params = [
        ('ServerVersion', SERVER_VERSION),
        ('pageSize', PAGE_SIZE),
        ('passportctoken', user.passport_ctoken),
        ('type', PLAN_TYPE),
        ('passportutoken', user.passport_utoken),
        ('subAccountNo', ''),
        ('PhoneType', PHONE_TYPE),
        ('MobileKey', MOBILE_KEY),
        ('fundCode', fund_code),
        ('pageIndex', PAGE_INDEX),
        ('UserId', user.customer_no),
        ('UToken', user.u_token),
        ('CToken', user.c_token),
        ('passportid', user.passport_id),
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
        'traceparent': '00-0000000046aa4cae00000196719b333e-0000000000000000-01',
        'tracestate': 'pid=0xb01a105,taskid=0x651cc79'
    }
    logger = logging.getLogger("SmartPlan")
    try:
        response = requests.get(full_url, headers=headers, verify=False)
        response.raise_for_status()
        json_data = response.json()
        # logger.info(f"响应数据: {json_data}")
        
        # 检查API调用是否成功
        if not json_data.get('Success', False):
            logger.error(f"API调用失败: {json_data.get('FirstError', 'Unknown error')}")
            return []
            
        data = json_data.get('Data')
        if data is None:
            logger.error('解析响应数据失败: Data字段为空')
            return []
            
        # 提取基金基本信息
        fund_code_val = data.get('fundCode', '')
        fund_name = data.get('fundName', '')
        
        # 提取分页信息中的计划数据
        page_info_data = data.get('pageInfo', {})
        plans_data = page_info_data.get('data', [])
        
        fund_plans = []
        for plan_data in plans_data:
            try:
                # 解析executedAmount字段
                executed_amount_str = plan_data.get('executedAmount', '0')
                if executed_amount_str:
                    executed_amount_str = str(executed_amount_str).replace(',', '')
                    executed_amount = float(executed_amount_str)
                else:
                    executed_amount = 0.0

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
                    periodType=0,
                    periodValue=0,
                    amount=0.0,
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
                logger.error(f'解析单个计划失败: {str(e)}')
                continue
                
        logger.info(f'获取基金定投计划列表成功，共{len(fund_plans)}个计划')
        return fund_plans
        
    except requests.exceptions.RequestException as e:
        logger.error(f'请求失败: {str(e)}')
        return []
    except Exception as e:
        logger.error(f'获取计划列表失败: {str(e)}')
        return []


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
        
    logger = logging.getLogger("RationCreate")
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
                raise Exception('解析响应数据失败: Data字段为空')

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
            logger.error(f'解析响应数据失败: {str(e)}')
            raise Exception(f'解析响应数据失败: {str(e)}')
    except requests.exceptions.RequestException as e:
        logger.error(f'请求失败: {str(e)}')
        raise Exception(f'请求失败: {str(e)}')

def getPlanDetailPro(plan_id, user) -> ApiResponse[FundPlanDetail]:
    """
    获取定投计划详情
    """
    url = f'https://ibgapi{user.index}.1234567.com.cn/ration/getPlanDetailPro'
    data = {
        'product': 'EFund',
        'ServerVersion': SERVER_VERSION,
        'PlanId': plan_id,
        'passportctoken': user.passport_ctoken,
        'passportutoken': user.passport_utoken,
        'deviceid': MOBILE_KEY,
        'userid': user.customer_no,
        'version': SERVER_VERSION,
        'ctoken': user.c_token,
        'uid': user.customer_no,
        'PhoneType': PHONE_TYPE,
        'MobileKey': MOBILE_KEY,
        'UserId': user.customer_no,
        'utoken': user.u_token,
        'plat': 'Android',
        'UToken': user.u_token,
        'passportid': user.passport_id,
        'CToken': user.c_token
    }
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json; charset=utf-8',
        'Host': f'ibgapi{user.index}.1234567.com.cn',
        'Referer': f'https://mpservice.com/fund46516ffab83642/release/pages/plan-detail/index?planId={plan_id}',
        'User-Agent': 'okhttp/3.12.13',
        'clientInfo': 'ttjj-ZTE 7534N-Android-11',
        'gtoken': 'ceaf-4a997831b1b3b90849f585f98ca6f30e',
        'mp_instance_id': '14'
    }
    logger = logging.getLogger("SmartPlan")
    try:
        response = requests.post(url, json=data, headers=headers, verify=False)
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
                raise Exception('解析响应数据失败: Data字段为空')

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
            logger.error(f'解析响应数据失败: {str(e)}')
            raise Exception(f'解析响应数据失败: {str(e)}')
    except requests.exceptions.RequestException as e:
        logger.error(f'请求失败: {str(e)}')
        raise Exception(f'请求失败: {str(e)}')


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
    
    logger = logging.getLogger("SmartPlan")
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
                raise Exception('解析响应数据失败: Data字段为空')

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
            logger.error(f'解析响应数据失败: {str(e)}')
            raise Exception(f'解析响应数据失败: {str(e)}')
            
    except requests.exceptions.RequestException as e:
        logger.error(f'请求失败: {str(e)}')
        raise Exception(f'请求失败: {str(e)}')


def createPlanV3(user, fund_code: str, amount: str = "2000.0", period_type: int = 4, 
                 period_value: str = "1",sub_account_name = None,strategy_type: int = 0) -> ApiResponse[FundPlan]:
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
    Returns:
        ApiResponse[FundPlan]: 定投计划创建结果
    """
    md5_password = hashlib.md5(user.password.encode('utf-8')).hexdigest()
    
    url = f'https://ibgapi{user.index}.1234567.com.cn/ration/createPlanV3'
    
    # 如果指定了子账户名称，获取子账户编号
    sub_account_no = None
    if sub_account_name is not None:
        sub_account_no = getSubAccountNoByName(user, sub_account_name)
    
    # 构建请求体
    body = {
        "minTimes": 0,
        "ServerVersion": "6.7.1",
        "bankAcctNo": user.max_hqb_bank.AccountNo,
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
        "targetProfitRate": "5%",
        "plat": "Android",
        "CToken": user.c_token,
        "Password": md5_password,
        "amount": amount,
        "product": "EFund",
        "orderNo": "",
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
        "redeemStrategy": 1,
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
        "traceparent": "00-0000000046aa4cae00000196719b333e-0000000000000000-01",
        "tracestate": "pid=0xb01a105,taskid=0x651cc79",
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
            raise Exception('响应数据为空')
            
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
        logger.info(f"定投计划创建成功 - 计划ID: {plan.planId}, 基金代码: {plan.fundCode}, 基金名称: {plan.fundName}, 定投金额: {plan.amount}, 定投周期: {plan.periodType}, 子账户: {plan.subAccountName}")
        
        return ApiResponse(
            Success=True,
            ErrorCode=0,
            Data=plan,
            FirstError=None,
            DebugError=None
        )
        
    except requests.exceptions.RequestException as e:
        logger.error(f'请求失败: {str(e)}')
        raise Exception(f'请求失败: {str(e)}')
    except Exception as e:
        logger.error(f'创建定投计划失败: {str(e)}')
        raise Exception(f'创建定投计划失败: {str(e)}')

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
    
    logger = logging.getLogger("SmartPlan")
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
                raise Exception('解析响应数据失败: Data字段为空')

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
            logger.error(f'解析响应数据失败: {str(e)}')
            raise Exception(f'解析响应数据失败: {str(e)}')
            
    except requests.exceptions.RequestException as e:
        logger.error(f'请求失败: {str(e)}')
        raise Exception(f'请求失败: {str(e)}')



if __name__ == '__main__':
    # 配置logger
    logger = logging.getLogger("SmartPlan")
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    getFundPlanList("021490", DEFAULT_USER) 
    # 测试创建定投计划
    # response = createPlanV3(
    #     user=DEFAULT_USER,
    #     fund_code="021490",
    #     amount="2000.0",
    #     period_type=4,
    #     period_value= "1",
    #     sub_account_name="最优止盈",
    #     strategy_type= 3
    # )

    # # 检查响应
    # if response.Success:
    #     plan = response.Data
    #     print(f"创建成功! 计划ID: {plan.planId}")
    #     print(f"基金名称: {plan.fundName}")
    #     print(f"下次扣款日期: {plan.nextDeductDate}")
    # else:
    #     print(f"创建失败: {response.FirstError}")