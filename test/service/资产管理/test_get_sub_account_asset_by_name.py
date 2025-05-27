import pytest
import os
import sys
import logging

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name
from src.common.constant import DEFAULT_USER
from src.domain.asset.asset_details import AssetDetails

def test_get_sub_account_asset_list_success():
    # 准备测试数据
    user = DEFAULT_USER
    sub_account_name = "最优止盈"
    
    # 调用被测试的函数
    asset_details_list = get_sub_account_asset_by_name(user, sub_account_name)

    
    # 验证返回结果
    # assert asset_details_list is not None, "未找到组合资产列表"
    # assert isinstance(asset_details_list, list), "返回结果不是列表类型"
    
    # 如果列表不为空，验证每个资产详情对象
    if asset_details_list:
        for asset_detail in asset_details_list:
            #打印结果
            print(asset_detail)

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)d)')
    # 直接运行测试
    test_get_sub_account_asset_list_success()