import os
import sys
import logging
from src.common.logger import get_logger
from typing import Any, Dict, Optional

import requests

# 添加“src”目录到 sys.path（从 src/API/工具/ 回退 3 层 => src），保持与 FundInfo.py 一致
SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from common.constant import SERVER_VERSION, PHONE_TYPE, MOBILE_KEY, DEFAULT_USER
from domain.fund_plan import ApiResponse
# 注意：删除了对自身模块的导入，避免循环导入
# from src.API.工具.utils import get_fund_system_time_trade


def get_fund_system_time_trade(user) -> ApiResponse[Dict[str, Any]]:
    """
    调用东财 FundSystemTimeTrade 接口，获取系统时间与是否处于可交易时段等信息。
    """
    url = "https://fundmobapi.eastmoney.com/FundMNewApi/FundSystemTimeTrade"

    # 参考项目内其它 API 的风格组织 headers（字段取自抓包样例，按需精简）
    headers = {
        "Connection": "keep-alive",
        "Accept": "*/*",
        "GTOKEN": "4474AFD3E15F441E937647556C01C174",
        "Clientinfo": "ttjj-iPhone 11 Pro-iOS-iOS16.2",
        "Mp-Version": "1.5.6",
        "Accept-Language": "zh-Hans-CN;q=1",
        "Validmark": "Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZd9JYBOfWXLz4ujEjOUCkzX5OOMubE0Xuw+PGl6/XhtW58ZqXh/Xc3OOE5LZ58h/eoII25voWA/jdiRh3oRljk0Q==",
        "User-Agent": "EMProjJijin/6.6.3 (iPhone; iOS 16.2; Scale/3.00)",
        "Referer": "https://mpservice.com/770ddc37537896dae8ecd8160cb25336/release/pages/fundList/customListPage",
        "Content-Type": "application/x-www-form-urlencoded",
        "Host": "fundmobapi.eastmoney.com",
    }

    # data 参考抓包字段，并结合现有 user 对象/项目常量
    # 根据已有登录与 passport 逻辑，Passportid 优先使用 user.passport_uid，不存在则回退 user.customer_no
    passport_id = getattr(user, "passport_uid", None) or getattr(user, "passport_id", None) or user.customer_no
    user_id = getattr(user, "passport_uid", None) or user.customer_no

    data = {
        "CToken": user.c_token,
        "CustomerNo": user.customer_no,
        "MobileKey": MOBILE_KEY,
        "Passportid": passport_id,
        "PhoneType": PHONE_TYPE,          # 示例：IOS16.2.0 或 Android 11，由常量统一维护
        "ServerVersion": SERVER_VERSION,  # 示例：6.6.3，由常量统一维护
        "UToken": user.u_token,
        "UserId": user_id,
        "appVersion": SERVER_VERSION,
        "customerNo": user.customer_no,
        "deviceid": MOBILE_KEY,
        "plat": "Iphone",                 # 与抓包保持一致；如需统一，也可改为从常量派生
        "product": "EFund",
        "version": SERVER_VERSION,
    }

    logger = get_logger("FundSystemTimeTrade")
    extra = {"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "action": "fund_system_time_trade"}
    try:
        response = requests.post(url, headers=headers, data=data, verify=False, timeout=10)
        response.raise_for_status()
        json_data: Dict[str, Any] = response.json()

        # 统一兼容大小写差异
        success = json_data.get("Success")
        if success is None:
            success = json_data.get("success", False)

        error_code = json_data.get("ErrorCode")
        if error_code is None:
            error_code = json_data.get("ErrCode")

        # 提取 Datas 作为有效业务数据返回
        datas = json_data.get("Datas")

        first_error = (
            json_data.get("ErrMsg")
            or json_data.get("ErrorMessage")
            or json_data.get("Message")
        )

        return ApiResponse(
            Success=bool(success),
            ErrorCode=error_code,
            Data=datas,
            FirstError=first_error,
            DebugError=None,
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"请求失败: {str(e)}", extra=extra)
        return ApiResponse(
            Success=False,
            ErrorCode="REQUEST_ERROR",
            Data=None,
            FirstError=f"请求失败: {str(e)}",
            DebugError=None,
        )
    except Exception as e:
        logger.error(f"调用异常: {str(e)}", extra=extra)
        return ApiResponse(
            Success=False,
            ErrorCode="UNKNOWN_ERROR",
            Data=None,
            FirstError=f"未知错误: {str(e)}",
            DebugError=None,
        )


__all__ = ["get_fund_system_time_trade"]

if __name__ == "__main__":
    ret = get_fund_system_time_trade(DEFAULT_USER)
    if ret.Success:
        print(ret.Data)  # {'SystemTime': '...', 'IsTrade': True/False, 'LastTwoTradeDays': [...]}
    else:
        print(ret.FirstError)
