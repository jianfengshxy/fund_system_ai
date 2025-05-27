import pytest
import os
import sys
import logging
import time

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.API.交易管理.trade import get_bank_shares
from src.API.交易管理.sellMrg import super_transfer
from src.API.交易管理.revokMrg import revoke_order
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.common.constant import DEFAULT_USER
from src.API.资产管理.getAssetListOfSub import get_asset_list_of_sub


def test_get_asset_list_of_sub_success():
    asset_details_list = get_asset_list_of_sub(DEFAULT_USER, '20891029')
    #这里输出asset_details_list里面元素信息 
    for asset_details in asset_details_list:
        print("------------------------")  
        # asset_details 里面每个元素的类型是AssetDetails
        # 所以可以直接输出asset_details里面的元素
        # 这里输出asset_details里面的元素信息
        print(asset_details.fund_code)
        print(asset_details.fund_name)
   
    assert len(asset_details_list) > 0


if __name__ == "__main__":
    # 直接运行测试
    test_get_asset_list_of_sub_success()
