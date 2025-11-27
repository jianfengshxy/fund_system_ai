import sys
import os
import requests
import json
import logging
from src.common.logger import get_logger
import hashlib

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.domain.trade.TradeResult import TradeResult
from src.domain.user.User import User
from typing import List, Optional, Dict, Any
from src.common.constant import MOBILE_KEY

def revoke_order(user: User, busin_serial_no: str, business_type: str, fund_code: str, 
                 amount: str, sub_account_no: str = "", bank_account_no: str = "") -> Dict[str, Any]:
    """
    撤回交易订单
    Args:
        user: User对象，包含用户认证信息
        busin_serial_no: 业务流水号
        business_type: 业务类型
        fund_code: 基金代码
        amount: 申请金额/份额
        sub_account_no: 子账户编号，默认为空
        bank_account_no: 银行账户号，默认为空
    Returns:
        Dict[str, Any]: 撤单结果，包含成功状态和消息
    """
    url = f"https://tradeapilvs{user.index}.1234567.com.cn/Trade/FundTrade/RevokeOrder"
    if not user.index:
        url = "https://tradeapilvs1.1234567.com.cn/Trade/FundTrade/RevokeOrder"
    
    headers = {
        "Connection": "keep-alive",
        "Host": f"tradeapilvs{user.index}.1234567.com.cn",
        "Accept": "*/*",
        "GTOKEN": "4474AFD3E15F441E937647556C01C174",
        "User-Agent": "EMProjJijin/6.5.5 (iPhone; iOS 15.5; Scale/3.00)",
        "Accept-Language": "zh-Hans-CN;q=1",
        "Referer": "https://mpservice.com/47e7241f3f0a46af8629dfe78fe62c55/release/pages/BuyTrade",
        "clientInfo": "ttjj-iPhone12,3-iOS-iOS15.5",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    # 对密码进行MD5加密
    password_hash = hashlib.md5(user.password.encode()).hexdigest()

    # 计算撤单 TradeType 与 BusinType：优先使用数字业务代码
    bus_code = str(business_type or "")
    trade_type = f"AsyJCJY{bus_code.zfill(3)}" if bus_code.isdigit() else "AsyJCJY022"

    data = {
        "BankAccountNo": bank_account_no,
        "CouponsId": "",
        "CouponsType": "",
        "FollowingSubAccountNo": "",
        "FundAppsJson": f'[{{"fundCode": "{fund_code}", "amount": "{amount}"}}]',
        "IsPayPlus": "false",
        "IsRemittance": "",
        "MobileKey": MOBILE_KEY,
        "Password": password_hash,
        "RatioRefundType": "",
        "SubAccountNo": sub_account_no,
        "TotalAmounts": amount,
        "TraceID": f"{busin_serial_no}_zrA2NQcw4sld",
        "TradeType": trade_type,
        "appType": "ttjj",
        "cToken": user.c_token,
        "phoneType": "Iphone",
        "serverVersion": "6.6.11",
        "uToken": user.u_token,
        "userId": user.customer_no,
        "version": "6.6.11",
        "BusinId": busin_serial_no,
        "BusinType": bus_code
    }

    logger = get_logger("RevokeMrg")
    extra = {"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None),
             "action": "revoke_order",
             "fund_code": fund_code,
             "sub_account_no": sub_account_no,
             "busin_serial_no": busin_serial_no}
    try:
        response = requests.post(url, headers=headers, data=data, verify=False)
        response.raise_for_status()
        response_data = response.json()
        # logger.info(f"响应数据: {response_data}")
        
        success = response_data.get("Success", False)
        result = {
            "Success": success,
            "Message": response_data.get("FirstError", "未知错误") if not success else "撤回交易成功"
        }
        
        if success:
            logger.info(f"{user.customer_name}的基金{fund_code}撤回交易成功. 业务流水号: {busin_serial_no}", extra=extra)
        else:
            logger.error(f"撤回交易失败: {result['Message']}", extra=extra)
        
        return result
    except requests.exceptions.RequestException as e:
        logger.error(f"请求失败: {str(e)}", extra=extra)
        return {"Success": False, "Message": f"请求失败: {str(e)}"}
    except Exception as e:
        logger.error(f"撤回交易失败: {str(e)}", extra=extra)
        return {"Success": False, "Message": f"撤回交易失败: {str(e)}"}


if __name__ == "__main__":
    # 导入必要的模块
    import sys
    import os
    
    # 获取项目根目录路径
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    
    # 如果项目根目录不在Python路径中，则添加
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    
    # 导入常量
    from src.common.constant import DEFAULT_USER
    from src.service.交易管理.交易查询 import get_withdrawable_trades
    
    # 配置日志
    logger = get_logger("RevokeMrg")
    
    # 获取可撤单交易列表
    logger.info("开始获取可撤单交易列表")
    trades = get_withdrawable_trades(DEFAULT_USER)
    
    if not trades:
        logger.info("没有可撤单的交易")
        sys.exit(0)
    
    # 选择第一笔交易进行撤单测试
    trade = trades[0]
    logger.info(f"准备撤单: ID={trade.busin_serial_no}, 业务类型={trade.business_type}, 基金代码={trade.fund_code}, 金额/份额={trade.amount}")
    
    # 调用撤单接口
    result = revoke_order(
        DEFAULT_USER,
        trade.busin_serial_no,
        trade.business_type,
        trade.fund_code,
        trade.amount
    )
    
    # 打印结果
    if result["Success"]:
        logger.info("撤单成功")
    else:
        logger.error(f"撤单失败: {result['Message']}")
