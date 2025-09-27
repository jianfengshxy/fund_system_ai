import logging
from random import vonmisesvariate
import re
from typing import Optional
import threading
from concurrent.futures import ThreadPoolExecutor
import os
import sys  # 添加此行，如果未导入

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
from src.service.交易管理.购买基金 import commit_order
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
from src.service.定投管理.组合定投.组合定投管理 import dissolve_period_investment_by_group
from src.service.用户管理.用户信息 import get_user_all_info

logging.basicConfig(
    stream=sys.stdout,  # 添加此行
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

#第一列：手机号 account
# 第二列：密码 password
# 第三列：支付密码
# 第四列：姓名
# 第五列：sub_account_name组合名称
# 第六列：预算
user_list = [
    ("13918797997","Zj951103","Zj951103","仇晓钰","最优止盈",300000.0),
    # ("13918199137", "sWX15706","sWX15706","最优止盈","飞龙在天",1000000.0),
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


def redeem(user: User, sub_account_name: str, total_budget: Optional[float] = None) -> bool:
    """
    业务薄封装：止盈
    - 统一参数处理（含 total_budget 的缺省处理）
    - 委托 service 层算法实现（完整版：风向标跳过 + 多触发条件 + 余额兜底）
    """
    logger.info(f"业务层止盈调用：用户={getattr(user, 'customer_name', 'unknown')}, 组合={sub_account_name}")
    logger.info("将使用服务层风向标止盈策略（完整版）")
    try:
        from src.service.加仓风向标组合算法.加仓风向标止盈 import redeem_funds as service_redeem_funds
        return service_redeem_funds(user, sub_account_name, total_budget)
    except Exception as e:
        logger.error(f"业务层止盈委托失败: {e}")
        return False

if __name__ == "__main__":
    # 测试 amount 不传的情况
    try:
        success = redeem(DEFAULT_USER, "飞龙在天",1000000)  
        if success:
            logging.info("测试成功（amount 未传）")
        else:
            logging.info("测试失败（amount 未传）")
    except Exception as e:
        logging.error(f"测试用户处理失败：{str(e)}")