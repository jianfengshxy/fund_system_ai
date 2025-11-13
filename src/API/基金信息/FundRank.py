from typing import Optional, Tuple
import logging
from src.common.logger import get_logger
from src.common.errors import RetriableError, ValidationError
import requests
import urllib3
import numpy as np
from domain.fund.fund_info import FundInfo
from common.constant import SERVER_VERSION, PHONE_TYPE, MOBILE_KEY, DEVICE_ID

# 禁用SSL证书验证警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_nav_rank(user, fund_info: FundInfo, N: int, nav: Optional[float] = None) -> Optional[int]:
    """
    获取基金净值在最近N个交易日中的排名
    
    Args:
        user: User对象，包含用户认证信息
        fund_info: FundInfo对象，包含基金的基本信息
        N: 最近的交易日数量
        nav: 当前净值，如果为None则使用最新一天的净值
        
    Returns:
        int: 净值排名，如果获取失败返回None
    """
    url = 'https://fundmobapi.eastmoney.com/FundMNewApi/FundMNHisNetList'
    
    headers = {
        'Connection': 'keep-alive',
        'Host': 'fundmobapi.eastmoney.com',
        'Accept': '*/*',
        'GTOKEN': '4474AFD3E15F441E937647556C01C174',
        'clientInfo': 'ttjj-iPhone12,3-iOS-iOS15.5',
        'Accept-Language': 'zh-Hans-CN;q=1',
        'validmark': 'Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZd9JYBOfWXLz4ujEjOUCkzX5OOMubE0Xuw+PGl6/XhtW6uCaNvvGARgUd92574Ft++7hwQ65WREqAHqpIQXfammA==',
        'User-Agent': 'EMProjJijin/6.5.5 (iPhone; iOS 15.5; Scale/3.00)',
        'Referer': 'https://mpservice.com/516939c37bdb4ba2b1138c50cf69a2e1/release/pages/fundHistoryWorth/index',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = {
        'FCODE': fund_info.fund_code,
        'IsShareNet': 'true',
        'MobileKey': MOBILE_KEY,
        'OSVersion': '15.5',
        'appType': 'ttjj',
        'appVersion': SERVER_VERSION,
        'cToken': user.c_token,
        'deviceid': DEVICE_ID,
        'pageIndex': '0',
        'pageSize': str(N),
        'passportid': user.passport_id,
        'plat': PHONE_TYPE,
        'product': 'EFund',
        'serverVersion': SERVER_VERSION,
        'uToken': user.u_token,
        'userId': user.customer_no,
        'version': SERVER_VERSION
    }
    
    logger = get_logger("FundRank")
    extra = {"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "action": "get_nav_rank", "fund_code": fund_info.fund_code}
    try:
        response = requests.post(url, headers=headers, data=data, verify=False, timeout=10)
        response.raise_for_status()
        
        json_data = response.json()
        logger.debug(f"响应数据: {json_data}")
        
        if not json_data.get('Success', False):
            error_msg = json_data.get('ErrMsg', '未知错误')
            logger.error(f"获取基金净值历史数据失败: {error_msg}", extra=extra)
            raise ValidationError(error_msg)
            
        datas = json_data.get('Datas', [])
        if not datas:
            logger.error("未找到基金净值历史数据", extra=extra)
            raise ValidationError("DATA_EMPTY")
            
        try:
            # 如果未提供nav，使用最新一天的净值
            if nav is None:
                nav = float(datas[0].get('DWJZ', 0))
                logger.debug(f"基金{fund_info.fund_code}{fund_info.fund_name}，使用最新净值：{nav}", extra=extra)
            
            # 获取所有净值并排序
            sorted_navs = [float(data.get('DWJZ', 0)) for data in datas if data.get('DWJZ') is not None]
            sorted_navs.append(nav)
            sorted_navs.sort()
            
            # 计算排名
            rank = sorted_navs.index(nav) + 1
            logger.debug(f"基金{fund_info.fund_code}{fund_info.fund_name}，当前净值：{nav}，在最近{N}个交易日中的排名：{rank}")
            
            return rank
            
        except (ValueError, TypeError, IndexError) as e:
            logger.error(f"解析净值数据失败: {str(e)}", extra=extra)
            raise ValidationError(str(e))
            
    except requests.exceptions.RequestException as e:
        logger.error(f"请求失败: {str(e)}", extra=extra)
        raise RetriableError(str(e))
    except Exception as e:
        logger.error(f"处理过程发生异常: {str(e)}", extra=extra)
        raise ValidationError(str(e))


def get_fund_volatility(user, fund_info: FundInfo, N: int) -> Optional[Tuple[float, float, float]]:
    """
    获取基金在最近N个交易日的波动率信息
    
    Args:
        user: User对象，包含用户认证信息
        fund_info: FundInfo对象，包含基金的基本信息
        N: 最近的交易日数量
        
    Returns:
        Tuple[float, float, float]: (平均值, 方差, 波动率)的元组，如果计算失败返回None
    """
    url = 'https://fundmobapi.eastmoney.com/FundMNewApi/FundMNHisNetList'
    
    headers = {
        'Connection': 'keep-alive',
        'Host': 'fundmobapi.eastmoney.com',
        'Accept': '*/*',
        'GTOKEN': '4474AFD3E15F441E937647556C01C174',
        'clientInfo': 'ttjj-iPhone12,3-iOS-iOS15.5',
        'Accept-Language': 'zh-Hans-CN;q=1',
        'validmark': 'Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZd9JYBOfWXLz4ujEjOUCkzX5OOMubE0Xuw+PGl6/XhtW6uCaNvvGARgUd92574Ft++7hwQ65WREqAHqpIQXfammA==',
        'User-Agent': 'EMProjJijin/6.5.5 (iPhone; iOS 15.5; Scale/3.00)',
        'Referer': 'https://mpservice.com/516939c37bdb4ba2b1138c50cf69a2e1/release/pages/fundHistoryWorth/index',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = {
        'FCODE': fund_info.fund_code,
        'IsShareNet': 'true',
        'MobileKey': MOBILE_KEY,
        'OSVersion': '15.5',
        'appType': 'ttjj',
        'appVersion': SERVER_VERSION,
        'cToken': user.c_token,
        'deviceid': DEVICE_ID,
        'pageIndex': '0',
        'pageSize': str(N),
        'passportid': user.passport_id,
        'plat': PHONE_TYPE,
        'product': 'EFund',
        'serverVersion': SERVER_VERSION,
        'uToken': user.u_token,
        'userId': user.customer_no,
        'version': SERVER_VERSION
    }
    
    logger = get_logger("FundRank")
    extra = {"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "action": "get_volatility", "fund_code": fund_info.fund_code}
    try:
        response = requests.post(url, headers=headers, data=data, verify=False, timeout=10)
        response.raise_for_status()
        
        json_data = response.json()
        logger.debug(f"响应数据: {json_data}")
        
        if not json_data.get('Success', False):
            error_msg = json_data.get('ErrMsg', '未知错误')
            logger.error(f"获取基金净值历史数据失败: {error_msg}", extra=extra)
            raise ValidationError(error_msg)
            
        datas = json_data.get('Datas', [])
        if not datas:
            logger.error("未找到基金净值历史数据", extra=extra)
            raise ValidationError("DATA_EMPTY")
            
        try:
            # 获取所有净值
            navs = [float(data.get('DWJZ', 0)) for data in datas if data.get('DWJZ') is not None]
            
            if len(navs) >= 2:
                # 计算平均值
                mean = np.mean(navs)
                # 计算方差（使用样本方差公式，分母为 n-1）
                variance = np.var(navs, ddof=1)
                
                # 检查方差是否为零
                if variance == 0:
                    logger.error("方差为零，无法计算波动率")
                    return mean, variance, 0  # 返回0作为波动率，因为方差为零
                else:
                    # 计算波动率（标准差）
                    volatility = np.sqrt(variance)
                    logger.debug(f"基金{fund_info.fund_code}{fund_info.fund_name}，平均净值：{mean:.4f}，方差：{variance:.4f}，波动率：{volatility:.4f}", extra=extra)
                    return mean, variance, volatility
            else:
                logger.error("数据不足，无法计算波动率", extra=extra)
                raise ValidationError("DATA_INSUFFICIENT")
                
        except (ValueError, TypeError, IndexError) as e:
            logger.error(f"解析净值数据失败: {str(e)}", extra=extra)
            raise ValidationError(str(e))
            
    except requests.exceptions.RequestException as e:
        logger.error(f"请求失败: {str(e)}", extra=extra)
        raise RetriableError(str(e))
    except Exception as e:
        logger.error(f"处理过程发生异常: {str(e)}", extra=extra)
        raise ValidationError(str(e))


def get_fund_growth_rate(fund_info: FundInfo, period_type: str) -> tuple[float, int, int]:
    """获取基金在特定时期的增长率信息
    
    Args:
        fund_info: FundInfo对象，包含基金的基本信息
        period_type: 时间周期类型，可选值："3Y", "Z", "Y"
        
    Returns:
        tuple: (增长率, 排名, 总数)
            - 增长率: 包含估算涨跌幅的综合增长率
            - 排名: 当前基金在同类基金中的排名
            - 总数: 同类基金的总数
    """
    fund_code = fund_info.fund_code
    gszzl = fund_info.estimated_change
    logger = get_logger("FundRank")
 
    def safe_float(value, default=0.0) -> float:
        """安全地将值转换为浮点数"""
        if value is None or (isinstance(value, str) and (not value.strip() or value.strip() == '--')):
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
            
    def safe_int(value, default=0) -> int:
        """安全地将值转换为整数"""
        if value is None or (isinstance(value, str) and not value.strip()):
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    url = "https://fundcomapi.tiantianfunds.com/mm/FundMNewApi/FundPeriodIncrease"
    headers = {
        "Host": "fundcomapi.tiantianfunds.com",
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "EMProjJijin/6.5.9 (iPhone; iOS 15.6.1; Scale/3.00)",
        "Connection": "keep-alive",
        "Accept-Language": "zh-Hans-CN;q=1",
        "MobileKey": MOBILE_KEY,
        "deviceid": DEVICE_ID,
        "plat": PHONE_TYPE,
        "appVersion": SERVER_VERSION,
        "serverVersion": SERVER_VERSION,
        "version": SERVER_VERSION
    }
    
    params = {
        "FCODE": fund_code,
        "deviceid": DEVICE_ID,
        "plat": PHONE_TYPE,
        "product": "EFund",
        "version": SERVER_VERSION,
        "MobileKey": MOBILE_KEY,
        "appType": "ttjj",
        "OSVersion": "15.6.1",
        "appVersion": SERVER_VERSION,
        "serverVersion": SERVER_VERSION
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10, verify=False)
        response.raise_for_status()
        data = response.json()
        logger.debug(f"基金{fund_code}增长率响应数据: {data}")

        # 修正：data["data"] 直接为 list
        data_list = data.get("data")
        if not isinstance(data_list, list) or not data_list:
            logger.error(f"基金{fund_code}增长率数据为空或格式错误")
            return 0.0, 0, 0

        for item in data_list:
            if item.get("title") == period_type:
                syl = safe_float(item.get("syl"))
                gszzl_value = safe_float(gszzl)
                growth_rate = syl + gszzl_value

                item_rank = safe_int(item.get("rank"))
                item_sc = safe_int(item.get("sc"))

                logger.debug(f"基金{fund_code}在{period_type}期间的增长率: {growth_rate:.2f}%, "
                            f"排名: {item_rank}/{item_sc}")

                return growth_rate, item_rank, item_sc

        logger.warning(f"未找到基金{fund_code}在{period_type}期间的增长率信息")
        return 0.0, 0, 0
        
    except requests.exceptions.RequestException as e:
        logger.error(f"请求基金{fund_code}增长率信息失败: {str(e)}")
        return 0.0, 0, 0
    except (ValueError, KeyError) as e:
        logger.error(f"解析基金{fund_code}增长率数据失败: {str(e)}")
        return 0.0, 0, 0
    except Exception as e:
        logger.error(f"获取基金{fund_code}增长率信息时发生未知异常: {str(e)}")
        return 0.0, 0, 0
