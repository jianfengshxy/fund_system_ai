import requests
import logging
from src.common.constant import MOBILE_KEY, C_TOKEN, U_TOKEN, USER_ID, SERVER_VERSION

def getFee(user, fund_code: str):
    """
    获取基金赎回手续费信息
    Args:
        user: User对象，包含用户认证信息
        sub_account_no: 子账户编号
        fund_code: 基金代码
    Returns:
        dict: 手续费相关信息，失败返回None
    """
    logger = logging.getLogger("FeeMrg")
    url = f"https://tradeapilvs{user.index}.95021.com/Business/Rate/GetShareAndRedeemRateList"
    headers = {
        "Connection": "keep-alive",
        "Host": f"tradeapilvs{user.index}.1234567.com.cn",
        "Accept": "*/*",
        "GTOKEN": "4474AFD3E15F441E937647556C01C174",
        "clientInfo": "ttjj-iPhone12,3-iOS-iOS15.6",
        "MP-VERSION": "3.11.0",
        "Accept-Language": "zh-Hans-CN;q=1",
        "User-Agent": "EMProjJijin/6.5.7 (iPhone; iOS 15.6; Scale/3.00)",
        "Referer": "https://mpservice.com/6ddf65da15dd416ca1c964efb606471f/release/pages/fundSalePage/index",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = (
        f"AppType=ttjj&CToken={user.c_token or C_TOKEN}&CustomerNo={user.customer_no}"
        f"&IsBaseAsset=false&MobileKey={MOBILE_KEY}&PhoneType=Iphone&ServerVersion={SERVER_VERSION}"
        f"&UToken={user.u_token or U_TOKEN}&UserId={user.customer_no or USER_ID}&Version={SERVER_VERSION}"
        f"&FundCode={fund_code}"
    )
    try:
        response = requests.post(url, headers=headers, data=data, verify=False)
        response.raise_for_status()
        result = response.json()
        logger.info(f"手续费查询响应: {result}")
        if result.get("Success") and "Data" in result:
            return result["Data"]
        else:
            logger.error(f"手续费查询失败: {result.get('FirstError') or result.get('ErrorMessage')}")
            return None
    except Exception as e:
        logger.error(f"手续费查询异常: {str(e)}")
        return None


