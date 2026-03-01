from typing import Any, Dict
from datetime import datetime

if __name__ == "__main__":
    import os
    import sys

    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.API._core.auth import build_auth_fields
from src.API._core.client import default_client
from src.API._core.headers import build_headers
from src.API._core.normalize import error_code, error_message, is_success
from src.common.constant import DEFAULT_USER, SERVER_VERSION
from src.common.logger import get_logger
from src.domain.fund_plan import ApiResponse

# 注意：删除了对自身模块的导入，避免循环导入
# from src.API.工具.utils import get_fund_system_time_trade


def get_fund_system_time_trade(user) -> ApiResponse[Dict[str, Any]]:
    """
    调用东财 FundSystemTimeTrade 接口，获取系统时间与是否处于可交易时段等信息。
    """
    url = "https://fundmobapi.eastmoney.com/FundMNewApi/FundSystemTimeTrade"

    headers = build_headers(
        host="fundmobapi.eastmoney.com",
        content_type="application/x-www-form-urlencoded",
        referer="https://mpservice.com/770ddc37537896dae8ecd8160cb25336/release/pages/fundList/customListPage",
        user_agent="EMProjJijin/6.6.3 (iPhone; iOS 16.2; Scale/3.00)",
        client_info="ttjj-iPhone 11 Pro-iOS-iOS16.2",
        mp_version="1.5.6",
        gtoken="4474AFD3E15F441E937647556C01C174",
    )

    u = user
    try:
        from src.API.登录接口.login import ensure_user_fresh

        u = ensure_user_fresh(user)
    except Exception:
        u = user

    data = build_auth_fields(u, include_passport=True, include_lowercase=True)
    data.update(
        {
            "appVersion": SERVER_VERSION,
            "product": "EFund",
            "plat": "Iphone",
        }
    )

    logger = get_logger("FundSystemTimeTrade")
    extra = {"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "action": "fund_system_time_trade"}
    try:
        json_data = default_client.post_form(url, headers=headers, data=data, timeout=10)
        datas = json_data.get("Datas")
        ec = error_code(json_data)
        return ApiResponse(
            Success=is_success(json_data),
            ErrorCode=0 if (ec == 0 or str(ec) == "0") else (int(ec) if str(ec).isdigit() else -1),
            Data=datas,
            FirstError=error_message(json_data) or None,
            DebugError=None,
        )
    except Exception as e:
        logger.error(f"调用失败: {str(e)}", extra=extra)
        return ApiResponse(
            Success=False,
            ErrorCode=-1,
            Data=None,
            FirstError=str(e),
            DebugError=None,
        )


def is_long_holiday(user) -> bool:
    """
    判断是否为长假期（距离下一个交易日超过3天）
    逻辑：LastTwoTradeDays 里面的第一个交易日 和 SystemTime 的间隔时间大于3天
    """
    resp = get_fund_system_time_trade(user)
    if not resp.Success or not resp.Data:
        return False
    
    data = resp.Data
    system_time_str = data.get("SystemTime")
    last_two_trade_days = data.get("LastTwoTradeDays")
    
    if not system_time_str or not last_two_trade_days or len(last_two_trade_days) < 1:
        return False
        
    try:
        # Parse system time
        # Format: "2026-03-01 22:55:05"
        system_dt = datetime.strptime(system_time_str, "%Y-%m-%d %H:%M:%S")
        
        # Parse next trade day
        # Format: "2026-03-02"
        next_trade_str = last_two_trade_days[0].strip()
        next_trade_dt = datetime.strptime(next_trade_str, "%Y-%m-%d")
        
        # Calculate difference in days
        diff = next_trade_dt.date() - system_dt.date()
        
        # Return True if interval is greater than 3 days
        return diff.days > 3
        
    except Exception as e:
        logger = get_logger("is_long_holiday")
        logger.error(f"Error checking holiday status: {e}")
        return False


__all__ = ["get_fund_system_time_trade", "is_long_holiday"]

if __name__ == "__main__":
    ret = get_fund_system_time_trade(DEFAULT_USER)
    if ret.Success:
        print(ret.Data)  # {'SystemTime': '...', 'IsTrade': True/False, 'LastTwoTradeDays': [...]}
        print(f"Is Long Holiday: {is_long_holiday(DEFAULT_USER)}")
    else:
        print(ret.FirstError)
