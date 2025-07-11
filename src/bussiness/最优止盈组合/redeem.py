import logging
from random import vonmisesvariate
import re
from typing import Optional
import threading
from concurrent.futures import ThreadPoolExecutor
import os
import sys

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.domain.fund import fund_info
from src.service.定投管理.定投查询.定投查询 import get_all_fund_plan_details
from src.domain.user.User import User
from src.domain.user.User import User  
from src.domain.fund_plan.fund_plan_detail import FundPlanDetail
from src.API.交易管理.sellMrg import super_transfer
from src.service.基金信息.基金信息 import get_all_fund_info
from src.API.交易管理.trade import get_trades_list
from src.API.交易管理.revokMrg import revoke_order
from src.API.交易管理.buyMrg import commit_order
from src.domain.trade.TradeResult import TradeResult
from src.common.constant import DEFAULT_USER
from src.API.资产管理.getAssetListOfSub import get_asset_list_of_sub
from src.service.资产管理.get_fund_asset_detail import get_fund_asset_detail
import datetime
from datetime import datetime
import math
from src.domain.fund_plan.fund_plan import FundPlan
from src.domain.fund_plan.fund_plan_detail import FundPlanDetail
from src.API.基金信息.FundRank import get_fund_growth_rate
from src.service.交易管理.赎回基金 import sell_0_fee_shares
from src.service.交易管理.赎回基金 import sell_low_fee_shares
from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name
from src.common.constant import DEFAULT_USER
from src.domain.asset.asset_details import AssetDetails
from src.API.交易管理.buyMrg import commit_order
from src.API.交易管理.sellMrg import super_transfer
from src.API.交易管理.revokMrg import revoke_order
from src.API.交易管理.trade import get_trades_list
from src.domain.trade.TradeResult import TradeResult
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.API.交易管理.trade import get_bank_shares
import requests

from src.API.登录接口.login import inference_passport_for_bind,login
from src.domain.user import User
from src.common.constant import DEFAULT_USER

logger = logging.getLogger(__name__)

#第一列：手机号 account
# 第二列：密码 password
# 第三列：支付密码
# 第四列：姓名
# 第五列：sub_account_name组合名称
# 第六列：budget 预算
user_list = [
    ("13918797997","Zj951103","Zj951103","仇晓钰","最优止盈",1000000.0),
#     ("13918199137", "sWX15706","sWX15706","施小雨","最优止盈",1000000.0),
    ("13820198186", "tang8186","tang8186","唐祖华","最优止盈",450000.0),
    ("17782571152", "s00127479","s00127479","邵科","最优止盈",150000.0),
    # ("13830702104", "chb201106?","chb201106?","程斌","最优止盈",100000.0),
    ("13851562586", "muyi0628","muyi0628","铁宏安","最优止盈",30000.0),
    ("13910680799", "fuliang223147","fuliang223147","梁红兵","最优止盈",40000.0),
    ("13974549306", "huigengsi937367","huigengsi937367","朱沅罗尘","最优止盈",50000.0),
    ("13977796363", "tang6363","tang6363","唐显扬","最优止盈",400000.0),
      # ("15184175351", "duxingchen123","duxingchen123","都星辰","最优止盈",20000.0),
    ("15373193078", "sy811123","sy811123","张莹莹","最优止盈",50000.0),
    ("15936530625", "wch601249697","wch601249697","王长海","最优止盈",50000.0),
    ("18648900788", "ldw88888","ldw88888","李代文","最优止盈",50000.0),
    ("13426206037", "fuyj223147","fuyj223147","付一军","最优止盈",50000.0),
    ("13500819290", "guojing1985","guojing1985","郭婧","最优止盈",200000.0),
    ("13562500306", "lilin926","lilin926","刘文杰","最优止盈",60000.0),
    ("13571973393", "wj121109","wj121109","安城","最优止盈",500000.0),
    ("13584903800", "hu123321","hu123321","胡春红","最优止盈",300000.0),
    #("13611617975", "65253056lml","65253056lml","胡琳元","最优止盈",100000000.0),
    # ("13636306263", "cy863391X","cy863391X","陈扬","最优止盈",200000.0),
    ("13817533699", "demone40","demone40","东岳亮","最优止盈",150000.0)
]



def redeem_all_users():
    # 遍历用户列表  
    for user_info in user_list:
        account = user_info[0]
        password = user_info[1]
        pay_password = user_info[2]
        name = user_info[3]
        sub_account_name = user_info[4]
        budget = user_info[5]
        
        try:
            user = login(account, password)
            user = inference_passport_for_bind(user)
            logger.info(f"开始赎回用户：{user.customer_name}")
            # 执行止盈操作
            redeem(user, sub_account_name)
            logger.info(f"用户：{user.customer_name} 赎回完成")
        except Exception as e:
            logger.error(f"登录失败的账号：{account}，用户名：{name}，错误信息：{str(e)}")
            continue

# 止盈算法实现
def redeem(user: User, sub_account_name:str = "最优止盈") -> bool:
    """最优止盈算法实现：
    1. 获取用户的指定组合sub_account_name的基金资产
    2. 遍历每个基金资产
    3. 获取基金资产的基金代码   
    4. 获取基金资产的份额
    5. 获取基金资产的基金名称
    6. 获取基金资产的当前净值
    7. 获取基金资产的预期收益率
    8. 获取基金资产的当前收益率
    9. 如果当前收益率大于预期收益率，则进行止盈操作
    10. 如果当前收益率小于预期收益率，则成功退出
    Args:
        user: 用户对象
        sub_account_name: 组合名称
    Returns:
        bool: 是否成功
    """
    customer_name = user.customer_name
    #根据组合名称获取组合账号
    sub_account_no = getSubAccountNoByName(user, sub_account_name)  
    # 从用户的子账户列表中查找指定名称的子账户编号
    asset_details_list = get_sub_account_asset_by_name(user, sub_account_name)
    if asset_details_list is None:
        logger.info(f"{customer_name}没有基金资产.")
        return False

    for asset_detail in asset_details_list:
        if asset_detail.fund_code is None:
            continue        
        fund_code = asset_detail.fund_code
        fund_name = asset_detail.fund_name
        fund_type = asset_detail.fund_type
        available_vol = asset_detail.available_vol  
        fund_info = get_all_fund_info(user,fund_code)
        volatility = fund_info.volatility

        stop_profit_rate = min(volatility * 100, 5.0) if fund_info.estimated_change != 0.0 else 5.0
        # 处理固定收益率
        constant_profit_rate = asset_detail.constant_profit_rate * 100

        # 计算总收益率
        result = constant_profit_rate + fund_info.estimated_change
        logger.info(f"{customer_name}的基金{fund_name}{fund_code}的收益{constant_profit_rate}加上估值增长率{fund_info.estimated_change}结果{result},计算止盈点:{volatility},实际止盈点:{stop_profit_rate}")
        
        if available_vol == 0.0:
            logger.info(f"{customer_name}的基金{fund_name}{fund_code}可用份额为0, 跳过赎回.")
            continue
        # 执行止盈操作
        if result >  stop_profit_rate and result > 1.0:
            bank_shares = get_bank_shares(user,sub_account_no, fund_code)
            logger.info(f"{customer_name}的止盈操作开始：基金{fund_name}{fund_code}预估收益{result},计算止盈点:{volatility},实际止盈点:{stop_profit_rate}. 满足止盈条件: result({result}) > stop_profit_rate({stop_profit_rate}) and result({result}) > 1.0")
            sell_low_fee_shares(user,sub_account_no,fund_code,bank_shares)
        else:
            logger.info(f"{customer_name}的基金{fund_name}{fund_code}的收益{constant_profit_rate}加上估值增长率{fund_info.estimated_change}结果{result},计算止盈点:{volatility},实际止盈点:{stop_profit_rate}. 未满足止盈条件: result > stop_profit_rate ({result > stop_profit_rate}), result > 1.0 ({result > 1.0}). Skip...........")
 
    return True
        
    

if __name__ == "__main__":
    # 直接运行测试
    redeem_all_users()