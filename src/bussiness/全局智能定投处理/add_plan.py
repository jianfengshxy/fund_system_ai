import logging
from random import vonmisesvariate
import re
from typing import Optional
import threading
from concurrent.futures import ThreadPoolExecutor
import os
import sys
import math

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

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
from src.API.大数据.加仓风向标 import getFundInvestmentIndicators
from src.domain.fund.fund_investment_indicator import FundInvestmentIndicator
# 修改第39行的导入语句
from src.service.定投管理.智能定投.智能定投管理 import create_period_smart_investment
logger = logging.getLogger(__name__)    

# add_plan(user: User) -> None :
def add_plan(user: User,amount:int = 2000)  :
    """
    全局智能定投处理
    :param user: 用户对象
    :return: None
    """
    try:
        # 获取加仓风向标基金信息
        result = getFundInvestmentIndicators(DEFAULT_USER,page_size=20)  
    #     if result:
    #         print("\n加仓风向标基金信息获取成功:")
    #         print(f"总共获取到 {len(result)} 条基金信息（已过滤保留名称中包含字母'C'且不包含'债'的基金，并排除基金子类型等于002003的基金，按产品排名从小到大排序）")
    #         print("===================================")
            
    #         for i, indicator in enumerate(result, 1):
    #             print(f"{i}. {indicator.fund_name} ({indicator.fund_code})")
    #             print(f"   排名: {indicator.product_rank}")
    #             print(f"   一年收益率: {indicator.one_year_return if indicator.one_year_return != 0 else '暂无'}%")
    #             print(f"   成立以来收益率: {indicator.since_launch_return}%")
    #             print(f"   基金类型: {indicator.fund_type}")
    #             print(f"   基金子类型: {indicator.fund_sub_type}")
    #             print(f"   更新时间: {indicator.update_time}")
                
    #             # 输出所有属性和值
    #             print("   所有属性:")
    #             for attr, value in vars(indicator).items():
    #                 print(f"      {attr}: {value}")
                
    #             print("-----------------------------------")
    #     else:
    #         print("获取加仓风向标基金信息失败: 返回结果为空")
    except Exception as e:
        print(f"执行过程中发生异常: {str(e)}")
    # 获取所有的定投计划详情
    fund_plan_details = get_all_fund_plan_details(user)
    # 过滤出periodType == 4 且 planType == '1' 的定投计划集合
    filtered_fund_plan_details = [
        fund_plan_detail for fund_plan_detail in fund_plan_details
        if fund_plan_detail.rationPlan.periodType == 4 and fund_plan_detail.rationPlan.planType == '1'
    ]
    # 遍历加仓风向标基金信息集合    
    for indicator in result:
        #判断indicator的基金fund_code在filtered_fund_plan_details中是否存在
        if not any(indicator.fund_code == fund_plan_detail.rationPlan.fundCode for fund_plan_detail in filtered_fund_plan_details):
            #输出要为und_plan_detail.rationPlan.fundName添加计划
            print(f"要为{indicator.fund_name}添加计划")
            create_period_smart_investment(user=user,fund_code=indicator.fund_code,amount = amount, period_type = 4,period_value = 1)
        else:
            #输出indicator.fund_name已经存在计划
            print(f"{indicator.fund_name}已经存在计划")

if __name__ == '__main__':
    # 获取所有定投计划详情
    add_plan(DEFAULT_USER)

