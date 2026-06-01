"""
基金历史排名图表接口（FundRankDiagram）。

本文件封装 `https://fundcomapi.tiantianfunds.com/mm/FundMNewApi/FundRankDiagram`，
用于获取某只基金在不同时间区间内的“同类排名走势/排名分位”图表数据（用于前端画图）。

与 `FundRank/FundInfo` 的区别：
- `FundInfo` 更偏“基金基础信息 + 净值/估值/收益率”
- `FundRank` 更偏“历史净值序列衍生指标（排名、波动率）”
- `FundRankDiagram` 返回的是“排名走势图表数据”，适合直接展示趋势图/区间排名变化
"""

from typing import Optional, Dict, Any, List
import logging

if __name__ == "__main__":
    import os
    import sys

    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.common.errors import RetriableError, ValidationError
import requests
import json
from src.common.constant import (
    DEFAULT_GTOKEN,
    IOS_CLIENT_INFO,
    IOS_USER_AGENT,
    MOBILE_KEY,
    PLATFORM,
    SERVER_VERSION,
    MP_VERSION_DEFAULT,
)
from src.common.requests_session import session

RANGE_DESCRIPTIONS: Dict[str, str] = {
    "1y": "近1月",
    "3y": "近3月",
}

ALLOWED_RANGE_VALUES = set(RANGE_DESCRIPTIONS.keys())


def get_fund_rank_diagram(user, fund_code: str, range_value: str = "3y") -> Optional[dict]:
    """
    获取基金历史排名图表数据（排名走势/分位图）。

    Args:
        user: User对象，包含用户认证信息
        fund_code: 基金代码
        range_value: 时间范围参数（接口字段名为 RANGE）。
            已验证可用且当前业务使用的取值：`1y/3y`，分别表示：
            - 1y: 近1月
            - 3y: 近3月
    Returns:
        dict: 基金历史排名图表数据，如果获取失败返回None
    """
    if range_value not in ALLOWED_RANGE_VALUES:
        raise ValidationError(f"Unsupported RANGE={range_value}, allowed={sorted(ALLOWED_RANGE_VALUES)}")
    url = "https://fundcomapi.tiantianfunds.com/mm/FundMNewApi/FundRankDiagram"
    
    headers = {
        'Host': 'fundcomapi.tiantianfunds.com',
        'tracestate': 'pid=0x104d5e3f0,taskid=0x174db1bc0',
        'Accept': '*/*',
        'GTOKEN': DEFAULT_GTOKEN,
        'clientInfo': IOS_CLIENT_INFO,
        'MP-VERSION': MP_VERSION_DEFAULT,
        'Accept-Language': 'zh-Hans-CN;q=1',
        'validmark': 'Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZdSIrQ1Lx4ygfw5br2rQnUfMES8ernsO5lB/RKZKLdR3yjfnrfzfHdSgXTLHDA0NGIiANDpxJn4QqsyZYAe8zKMA==',
        'User-Agent': IOS_USER_AGENT,
        'Referer': 'https://mpservice.com/516939c37bdb4ba2b1138c50cf69a2e1/release/pages/increase-list/index',
        'traceparent': '00-8f41444868164c8a91be49506978b527-0000000000000000-01',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    # 使用 user 对象中的 token 信息
    # 注意：原 curl 命令使用了特定的 deviceid 和 plat (Iphone)，这里尝试使用 user 对象和常量
    # 如果失败，可能需要回退到硬编码的 deviceid/plat，但通常 API 应该通用
    
    data = {
        'FCODE': fund_code,
        'RANGE': range_value,
        'ctoken': user.c_token,
        'deviceid': MOBILE_KEY,
        'passportctoken': user.passport_ctoken,
        'passportid': user.passport_id,
        'passportutoken': user.passport_utoken,
        'plat': PLATFORM,
        'product': 'EFund',
        'uid': user.customer_no,
        'userid': user.customer_no,
        'utoken': user.u_token,
        'version': SERVER_VERSION
    }
    
    logger = get_logger("FundRankDiagram")
    extra = {
        "account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None),
        "action": "get_fund_rank_diagram",
        "fund_code": fund_code,
        "range": range_value,
    }
    try:
        response = session.post(url, headers=headers, data=data, verify=False, timeout=15)
        response.raise_for_status()
        
        try:
            return response.json()
        except json.JSONDecodeError as e:
            logger.error(f"解析基金排名图表数据失败: {str(e)}，响应内容: {response.text[:200]}", extra=extra)
            raise ValidationError(str(e))
            
    except requests.exceptions.RequestException as e:
        logger.error(f"请求基金排名图表数据失败: {str(e)}", extra=extra)
        raise RetriableError(str(e))
    except Exception as e:
        logger.error(f"处理基金排名图表数据时发生异常: {str(e)}", extra=extra)
        raise ValidationError(str(e))

def _extract_points(payload: dict) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("Datas", "Data", "List", "Points", "points"):
            val = data.get(key)
            if isinstance(val, list):
                return val
    return []


if __name__ == '__main__':
    from src.common.constant import DEFAULT_USER
    from src.API.登录接口.login import ensure_user_fresh

    logging.basicConfig(level=logging.INFO)

    user = ensure_user_fresh(DEFAULT_USER)

    fund_code = '011707'
    print(f"Testing get_fund_rank_diagram for {fund_code}...")

    candidates = ["1y", "3y"]
    for range_value in candidates:
        desc = RANGE_DESCRIPTIONS.get(range_value, range_value)
        try:
            result = get_fund_rank_diagram(user, fund_code, range_value=range_value)
            ok = bool(result.get("success")) if isinstance(result, dict) else False
            points = _extract_points(result) if isinstance(result, dict) else []
            print("\n" + "=" * 90)
            print(f"RANGE={range_value} ({desc})")
            print(f"success={ok} | points={len(points)}")
            if isinstance(result, dict) and not ok:
                print(f"error={result.get('firstError') or result.get('message')}")

            if points:
                first = points[0]
                last = points[-1]
                print("\nPoints preview:")
                print(f"  first={first}")
                print(f"  last={last}")

            print("\nFull response:")
            print(json.dumps(result, indent=2, ensure_ascii=False) if result is not None else "None")
        except Exception as e:
            print("\n" + "=" * 90)
            print(f"RANGE={range_value} ({desc}) | error={e}")
