"""
基金历史净值衍生指标接口。

本文件围绕 `FundMNHisNetList` 和 `FundPeriodIncrease` 两类接口，
提供三组常用能力：
1. `get_nav_rank()`：当前净值在最近 N 个交易日中的相对排名；
2. `get_fund_volatility()`：最近 N 个交易日的平均净值、方差和波动率；
3. `get_fund_growth_rate()`：基金在特定收益区间内的增长率与同类排名。

常见参数含义：
- `FCODE`: 基金代码。
- `DWJZ`: 单位净值。
- `pageSize`: 拉取的历史净值条数，通常等于观察窗口 `N`。
- `period_type`: 收益区间类型。
  - `Z`: 近一周
  - `Y`: 近一月
  - `3Y`: 近三月
"""

from typing import Optional, Tuple

if __name__ == "__main__":
    import os
    import sys

    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.common.errors import RetriableError, ValidationError
import math
import requests
import statistics
from src.common.requests_session import session
from src.domain.fund.fund_info import FundInfo
from src.common.constant import DEFAULT_GTOKEN, DEVICE_ID, IOS_CLIENT_INFO, IOS_OS_VERSION, IOS_USER_AGENT, MOBILE_KEY, PHONE_TYPE, PLATFORM, SERVER_VERSION

def get_nav_rank(user, fund_info: FundInfo, N: int, nav: Optional[float] = None) -> Optional[int]:
    """
    获取基金净值在最近 N 个交易日中的相对排名。

    排名逻辑：
    1. 先拉取最近 `N` 个交易日的历史单位净值；
    2. 若未显式传入 `nav`，则默认以最新一日净值为当前净值；
    3. 将当前净值插入样本后排序，返回从小到大的位置排名。

    Args:
        user: 用户对象，主要提供 `c_token/u_token/passport_id/customer_no` 等鉴权上下文。
        fund_info: 基金对象，至少需要 `fund_code`、`fund_name`。
        N: 历史净值窗口大小，例如 `30` 表示最近 30 个交易日。
        nav: 可选的“当前净值”。如果传入，通常可以用估算净值参与排名；
            如果不传，则默认使用历史列表中的最新正式净值。

    Returns:
        int: 排名结果，数值越小代表净值越低；
        失败时抛出异常，由调用方决定是否降级。
    """
    url = 'https://fundmobapi.eastmoney.com/FundMNewApi/FundMNHisNetList'
    
    headers = {
        'Connection': 'keep-alive',
        'Host': 'fundmobapi.eastmoney.com',
        'Accept': '*/*',
        'GTOKEN': DEFAULT_GTOKEN,
        'clientInfo': IOS_CLIENT_INFO,
        'Accept-Language': 'zh-Hans-CN;q=1',
        'validmark': 'Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZd9JYBOfWXLz4ujEjOUCkzX5OOMubE0Xuw+PGl6/XhtW6uCaNvvGARgUd92574Ft++7hwQ65WREqAHqpIQXfammA==',
        'User-Agent': IOS_USER_AGENT,
        'Referer': 'https://mpservice.com/516939c37bdb4ba2b1138c50cf69a2e1/release/pages/fundHistoryWorth/index',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = {
        'FCODE': fund_info.fund_code,
        'IsShareNet': 'true',
        'MobileKey': MOBILE_KEY,
        'OSVersion': IOS_OS_VERSION,
        'appType': 'ttjj',
        'appVersion': SERVER_VERSION,
        'cToken': user.c_token,
        'deviceid': DEVICE_ID,
        'pageIndex': '0',
        'pageSize': str(N),
        'passportid': user.passport_id,
        'plat': PLATFORM,
        'product': 'EFund',
        'serverVersion': SERVER_VERSION,
        'uToken': user.u_token,
        'userId': user.customer_no,
        'version': SERVER_VERSION
    }
    
    logger = get_logger("FundRank")
    extra = {"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "action": "get_nav_rank", "fund_code": fund_info.fund_code}
    try:
        response = session.post(url, headers=headers, data=data, verify=False, timeout=30)
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
    获取基金最近 N 个交易日的净值波动统计。

    这里的波动率不是年化波动率，而是基于最近 `N` 条单位净值
    直接计算出来的样本标准差，适合在策略里做相对比较或阈值判断。

    Args:
        user: 用户对象，提供查询历史净值所需的鉴权字段。
        fund_info: 基金对象，至少需要 `fund_code`、`fund_name`。
        N: 参与统计的最近交易日数量，例如 `5`、`30`。

    Returns:
        Tuple[float, float, float]:
        - 第 1 个值：平均净值
        - 第 2 个值：样本方差
        - 第 3 个值：样本标准差（波动率）
    """
    url = 'https://fundmobapi.eastmoney.com/FundMNewApi/FundMNHisNetList'
    
    headers = {
        'Connection': 'keep-alive',
        'Host': 'fundmobapi.eastmoney.com',
        'Accept': '*/*',
        'GTOKEN': DEFAULT_GTOKEN,
        'clientInfo': IOS_CLIENT_INFO,
        'Accept-Language': 'zh-Hans-CN;q=1',
        'validmark': 'Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZd9JYBOfWXLz4ujEjOUCkzX5OOMubE0Xuw+PGl6/XhtW6uCaNvvGARgUd92574Ft++7hwQ65WREqAHqpIQXfammA==',
        'User-Agent': IOS_USER_AGENT,
        'Referer': 'https://mpservice.com/516939c37bdb4ba2b1138c50cf69a2e1/release/pages/fundHistoryWorth/index',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = {
        'FCODE': fund_info.fund_code,
        'IsShareNet': 'true',
        'MobileKey': MOBILE_KEY,
        'OSVersion': IOS_OS_VERSION,
        'appType': 'ttjj',
        'appVersion': SERVER_VERSION,
        'cToken': user.c_token,
        'deviceid': DEVICE_ID,
        'pageIndex': '0',
        'pageSize': str(N),
        'passportid': user.passport_id,
        'plat': PLATFORM,
        'product': 'EFund',
        'serverVersion': SERVER_VERSION,
        'uToken': user.u_token,
        'userId': user.customer_no,
        'version': SERVER_VERSION
    }
    
    logger = get_logger("FundRank")
    extra = {"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "action": "get_volatility", "fund_code": fund_info.fund_code}
    try:
        response = session.post(url, headers=headers, data=data, verify=False, timeout=30)
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
            def safe_float(value) -> Optional[float]:
                if value is None:
                    return None
                if isinstance(value, str):
                    v = value.strip()
                    if not v or v == "--":
                        return None
                    try:
                        return float(v)
                    except (ValueError, TypeError):
                        return None
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return None

            navs = []
            for item in datas:
                nav = safe_float(item.get("DWJZ"))
                if nav is not None:
                    navs.append(nav)

            if len(navs) >= 1:
                mean = float(statistics.fmean(navs))
                if len(navs) >= 2:
                    variance = float(statistics.variance(navs))
                    volatility = float(math.sqrt(variance)) if variance > 0 else 0.0
                else:
                    variance = 0.0
                    volatility = 0.0

                logger.debug(
                    f"基金{fund_info.fund_code}{fund_info.fund_name}，平均净值：{mean:.4f}，方差：{variance:.6f}，波动率：{volatility:.6f}",
                    extra=extra
                )
                return mean, variance, volatility

            logger.error("净值数据为空或不可解析，无法计算指标", extra=extra)
            raise ValidationError("DATA_EMPTY")
                
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
    """
    获取基金在指定区间内的增长率与同类排名。

    该接口返回的是基金官方区间收益率，函数内部会把当前估算涨跌幅
    `estimated_change` 叠加到区间收益中，使结果更接近当前时点的盘中表现。

    Args:
        fund_info: 基金对象，至少需要 `fund_code` 和 `estimated_change`。
        period_type: 区间类型。
            - `Z`: 近一周
            - `Y`: 近一月
            - `3Y`: 近三月

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
        "User-Agent": IOS_USER_AGENT,
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
        "OSVersion": IOS_OS_VERSION,
        "appVersion": SERVER_VERSION,
        "serverVersion": SERVER_VERSION
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30, verify=False)
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
