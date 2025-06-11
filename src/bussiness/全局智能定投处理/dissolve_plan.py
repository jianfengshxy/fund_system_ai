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

logger = logging.getLogger(__name__)    
