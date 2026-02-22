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

from src.common.logger import get_logger

from src.domain.trade.TradeResult import TradeResult
from src.domain.asset.asset_details import AssetDetails
from src.API.资产管理.getAssetListOfSub import get_asset_list_of_sub
from src.API.资产管理.getFundAssetDetailsOfBaseSubHdt import get_fund_asset_details_of_base_sub_hdt
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.domain.user.User import User
from typing import List, Optional
from src.common.constant import DEFAULT_USER, MOBILE_KEY
from src.API.交易管理.trade import get_trades_list
from src.service.基金信息.基金信息 import get_all_fund_info
from src.common.errors import RetriableError, ValidationError
from src.API.登录接口.login import ensure_user_fresh
from concurrent.futures import ThreadPoolExecutor, as_completed

def get_fund_total_asset_detail(user: User, fund_code: str) -> Optional[AssetDetails]:
    """
    获取指定基金在整个账户上的资产详情
    
    Args:
        user: 用户对象
        fund_code: 基金代码
    
    Returns:
        Optional[AssetDetails]: 如果找到对应基金的资产详情则返回，否则返回None
    """
    fresh_user = ensure_user_fresh(user, 600)
    asset_detail, meta = get_fund_asset_details_of_base_sub_hdt(fresh_user, fund_code, with_meta=True)
    
    if not asset_detail:
        if meta.get("token_error"):
            fresh_user = ensure_user_fresh(user, 600, True)
            asset_detail, meta = get_fund_asset_details_of_base_sub_hdt(fresh_user, fund_code, with_meta=True)
            
    return asset_detail

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
    fresh_user = ensure_user_fresh(user, 600)
    asset_details_list, meta = get_asset_list_of_sub(fresh_user, sub_account_no, with_meta=True)
    if not asset_details_list:
        if meta.get("token_error"):
            fresh_user = ensure_user_fresh(user, 600, True)
            asset_details_list, meta = get_asset_list_of_sub(fresh_user, sub_account_no, with_meta=True)
    
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
    logger = get_logger("AssetService")
    logger.info(f"组合名称 {sub_account_name} 对应的组合账号为 {sub_account_no}", extra={"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "sub_account_name": sub_account_name, "action": "get_assets"})      
    # 如果未找到组合账号，则返回None
    if not sub_account_no:
        logger.error(f"未找到组合名称 {sub_account_name} 对应的组合账号", extra={"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "sub_account_name": sub_account_name, "action": "get_assets"})
        return None
    
    # 获取资产列表并添加详细日志
    fresh_user = ensure_user_fresh(user, 600)
    asset_details_list, meta = get_asset_list_of_sub(fresh_user, sub_account_no, with_meta=True)
    if not asset_details_list:
        if meta.get("token_error"):
            fresh_user = ensure_user_fresh(user, 600, True)
            asset_details_list, meta = get_asset_list_of_sub(fresh_user, sub_account_no, with_meta=True)
    
    if asset_details_list:
        logger.info(f"获取到组合 {sub_account_name} 的资产详情:", extra={"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "sub_account_name": sub_account_name, "action": "get_assets"})
        
        def process_log_asset(asset):
            try:
                fund_info = get_all_fund_info(user, asset.fund_code)
            except RetriableError as e:
                logger.warning(f"基金信息可重试: {e}", extra={"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "sub_account_name": sub_account_name, "fund_code": asset.fund_code, "action": "get_assets"})
                fund_info = None
            except ValidationError as e:
                logger.error(f"基金信息解析错误: {e}", extra={"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "sub_account_name": sub_account_name, "fund_code": asset.fund_code, "action": "get_assets"})
                fund_info = None
            estimated_change = fund_info.estimated_change if fund_info else 0.0
            estimated_profit_rate = (asset.constant_profit_rate or asset.hold_profit_rate or 0.0) + estimated_change
            logger.info(f"  基金 {asset.fund_name}({asset.fund_code}): "
                       f"资产值={asset.asset_value}, "
                       f"可用份额={asset.available_vol}, "
                       f"收益率={asset.constant_profit_rate or asset.hold_profit_rate}, "
                       f"预估收益率={estimated_profit_rate}", extra={"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "sub_account_name": sub_account_name, "fund_code": asset.fund_code, "action": "get_assets"})

        with ThreadPoolExecutor(max_workers=10) as executor:
            executor.map(process_log_asset, asset_details_list)
    else:
        logger.warning(f"组合 {sub_account_name} 没有资产详情", extra={"account": getattr(user, 'mobile_phone', None) or getattr(user, 'account', None), "sub_account_name": sub_account_name, "action": "get_assets"})
    
    return asset_details_list
    
if __name__ == "__main__":
    # get_sub_account_asset_by_name(DEFAULT_USER,"飞龙在天")
    
    # Test get_fund_total_asset_detail
    fund_code = "020516" # Example from user input
    asset_detail = get_fund_total_asset_detail(DEFAULT_USER, fund_code)
    if asset_detail:
        print(f"Fund {fund_code} details:")
        print(asset_detail)
    else:
        print(f"Fund {fund_code} not found or error occurred.")
    pass
