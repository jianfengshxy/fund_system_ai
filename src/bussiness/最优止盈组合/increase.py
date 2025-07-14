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
from src.API.基金信息.FundRank import get_fund_growth_rate
from src.bussiness.全局智能定投处理.increase import increase_all_fund_plans

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



def increase_all_users():
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
            user.budget = budget
            logger.info(f"开始加仓用户：{user.customer_name}")
            # 执行加仓操作
            increase(user, sub_account_name)
            logger.info(f"用户：{user.customer_name} 加仓完成")
            logger.info(f"用户：{user.customer_name} 开始对定投处理")
            increase_all_fund_plans(user)
            logger.info(f"用户：{user.customer_name} 定投处理完成")
        except Exception as e:
            logger.error(f"登录失败的账号：{account}，用户名：{name}，错误信息：{str(e)}")
            continue

# 止盈算法实现
def increase(user: User, sub_account_name:str = "最优止盈") -> bool:
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
    candidate_asset_detail = []  # 初始化候选资产列表
    fund_num = 10
    day_amount = round(user.budget * 8 / 250, 2)
    day_amount_per_fund = round(day_amount / fund_num, 2)    
    
    if asset_details_list is None:
        logger.info(f"{customer_name}没有基金资产.")
        return True

    for asset_detail in asset_details_list:
        if asset_detail.fund_code is None:
            continue        
        fund_code = asset_detail.fund_code
        fund_name = asset_detail.fund_name
        available_vol = asset_detail.available_vol  
        fund_info = get_all_fund_info(user,fund_code)
        volatility = fund_info.volatility

        stop_profit_rate = min(volatility * 100, 5.0) if fund_info.estimated_change != 0.0 else 5.0
        # 处理固定收益率
        constant_profit_rate = asset_detail.constant_profit_rate * 100

        # 计算总收益率
        result = constant_profit_rate + fund_info.estimated_change
        logger.info(f"{customer_name}的基金{fund_name}{fund_code}的收益{constant_profit_rate}加上估值增长率{fund_info.estimated_change}结果{result},:{day_amount_per_fund}")
        
        if available_vol == 0.0:
            continue

        fund_info = get_all_fund_info(user, fund_code)    
        # 以下是用户提供的加仓逻辑
        on_way_transaction_count = float(asset_detail.on_way_transaction_count)

        if on_way_transaction_count > 0:
            logger.info(f"{fund_name}的在途交易个数:{on_way_transaction_count}.Skip......")
            continue
        
        # 当前基金占比不能超过10%
        if user.budget is None or user.budget == 0:
            logger.warning(f"用户 {user.customer_name} 的预算未设置或为0，无法计算基金占比。")
            fund_rate = 0
        else:
            fund_rate = float(asset_detail.asset_value) / float(user.budget) * 100
        
        if fund_rate > 10:
            logger.info(f"{fund_name}占比:{fund_rate}%.Skip......")
            continue
        
        if result >= 0:
            logger.info(f"{fund_name} 预估收益:{result}%.Skip......")
            continue
        
        rank_100 = fund_info.rank_100day
        rank_30 = fund_info.rank_30day
        if rank_100 < 20 or rank_100 > 90:
            logger.info(f"{fund_name} rank_100 {rank_100}. Skip......")
            continue
     
        if rank_30 < 5:
            logger.info(f"{fund_name} rank_30 {rank_30}. Skip......")
            continue

 
        season_growth_rate, season_item_rank, season_item_sc = get_fund_growth_rate(fund_info, '3Y')
        month_growth_rate, month_item_rank, month_item_sc = get_fund_growth_rate(fund_info, 'Y')     
        week_growth_rate, week_item_rank, week_item_sc = get_fund_growth_rate(fund_info, 'Z')     
        
        month_rank_rate  =  month_item_rank  /  month_item_sc      
        season_rank_rate  =  season_item_rank  /  season_item_sc
        week_rank_rate  =  week_item_rank  /  week_item_sc

        if float(week_growth_rate) > 5.0 or float(week_rank_rate) > 0.75:
            logger.info(f"{fund_name}周收益率预估:{week_growth_rate}%,周排名占比:{week_rank_rate:.2f}.Skip......")
            continue
        
        if month_growth_rate > 15.0 or month_rank_rate > 0.75:
            logger.info(f"{fund_name}月收益率预估:{month_growth_rate}%,月排名占比:{month_rank_rate:.2f}.Skip......")
            continue
        
        # 季度收益率小于0的时候，月收益周收益任意一个小于0，或者排名太低则跳出
        if ((season_growth_rate < 0.0) and (week_growth_rate < 0.0 or month_growth_rate < 0.0)) or season_rank_rate > 0.75:
            logger.info(f"{fund_name}季度收益率预估:{season_growth_rate}%,季度排名占比:{season_rank_rate:.2f}.Skip......")
            continue
        
        # 季度收益率大于0的时候，月收益周收益同时小于0，或者排名太低则跳出
        if ((season_growth_rate > 0.0) and (week_growth_rate < 0.0 and month_growth_rate < 0.0)) or season_rank_rate > 0.75:
            logger.info(f"{fund_name}季度收益率预估:{season_growth_rate}%,季度排名占比:{season_rank_rate:.2f}.Skip......")
            continue
        
        # 季度排名 > 月度排名,说明要保证上升趋势
        if season_item_rank < month_item_rank:
            logger.info(f"{fund_name}季度排名:{season_item_rank}，月度排名:{month_item_rank}.Skip......")
            continue
        
        logger.info(f"{user.customer_name}在组合{sub_account_name}中对基金{fund_name}({fund_code})判断为可加仓.")
        candidate_asset_detail.append(asset_detail)
        
        # 加倍定投逻辑
        if result < -5:
            logger.info(f"{fund_name} 预估收益 {result}% 小于-5%，进行加倍定投.")
            candidate_asset_detail.append(asset_detail)
            candidate_asset_detail.append(asset_detail)
    # 处理候选资产列表
    if not candidate_asset_detail:
        logger.info(f"用户 {user.customer_name} 在组合 {sub_account_name} 中没有符合加仓条件的基金.")
        return True
    logger.info(f"用户 {user.customer_name} 在组合 {sub_account_name} 中找到 {len(candidate_asset_detail)} 个可加仓的基金项（可能重复，因加倍逻辑）.")    
    # 遍历候选资产列表的前10个元素，调用commit_order
    for i, asset_detail in enumerate(candidate_asset_detail[:10]):
        fund_code = asset_detail.fund_code
        fund_amount = day_amount_per_fund
        logger.info(f"正在为用户 {user.customer_name} 购买基金 {asset_detail.fund_name}({fund_code})，金额：{fund_amount}")
        try:
            commit_order(user, sub_account_no, fund_code, fund_amount)
            logger.info(f"{customer_name}基金 {asset_detail.fund_name}({fund_code}){fund_amount}购买成功")
        except Exception as e:
            logger.error(f"{customer_name}基金 {asset_detail.fund_name}({fund_code}) 购买失败：{str(e)}")
    
    return True

# if __name__ == "__main__":
#     # 直接运行测试
#     increase_all_users()