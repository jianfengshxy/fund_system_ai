import requests
import json
import logging
import sys
import os

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.domain.trade.TradeResult import TradeResult
from src.domain.asset.asset_details import AssetDetails
from src.API.资产管理.getAssetListOfSub import get_asset_list_of_sub
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.domain.user.User import User
from typing import List, Optional
from src.common.constant import DEFAULT_USER, MOBILE_KEY
from src.API.交易管理.trade import get_trades_list

def get_fund_asset_detail(user: User, sub_account_no: str,fund_code: str) -> Optional[AssetDetails]:
    """
    获取指定基金在组合下的资产详情
    
    Args:
        user: 用户对象
        fund_code: 基金代码
        sub_account_no: 组合账号
    
    Returns:
        Optional[AssetDetails]: 如果找到对应基金的资产详情则返回，否则返回None
    """
    asset_details_list = get_asset_list_of_sub(user, sub_account_no)
    
    # 查找匹配fund_code的资产详情
    for asset_detail in asset_details_list:
        if asset_detail.fund_code == fund_code:
            return asset_detail
    
    return None

def get_sub_account_asset_by_name(user: User, sub_account_name: str) -> Optional[AssetDetails]:
    """
    获取指定组合下的所有资产详情
   
    Args:
        user: 用户对象
        sub_account_name: 组合名称
    
    Returns:
        Optional[AssetDetails]: 如果找到对应基金的资产详情f则返回，否则返回None
    """
    #根据组合名称获取组合账号
    sub_account_no = getSubAccountNoByName(user, sub_account_name)    
    logging.info(f"组合名称 {sub_account_name} 对应的组合账号为 {sub_account_no}")      
    # 如果未找到组合账号，则返回None
    if not sub_account_no:
        logging.error(f"未找到组合名称 {sub_account_name} 对应的组合账号")
        return None
    asset_details_list = get_asset_list_of_sub(user, sub_account_no)
    return asset_details_list   
    