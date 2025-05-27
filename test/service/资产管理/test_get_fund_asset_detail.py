import pytest
import os
import sys

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.service.资产管理.get_fund_asset_detail import get_fund_asset_detail
from src.common.constant import DEFAULT_USER
from src.domain.asset.asset_details import AssetDetails

def test_get_fund_asset_detail_success():
    # 准备测试数据
    user = DEFAULT_USER
    sub_account_no = "20891029"
    fund_code = "018125"
    
    # 调用被测试的函数
    asset_detail = get_fund_asset_detail(user, sub_account_no, fund_code)
    print(asset_detail)
    # 验证返回结果
    assert asset_detail is not None, "未找到基金资产详情"
    assert asset_detail.fund_code == fund_code, f"基金代码不匹配，期望：{fund_code}，实际：{asset_detail.fund_code}"
    assert hasattr(asset_detail, 'constant_profit_rate'), "资产详情缺少constant_profit_rate属性"
    assert isinstance(asset_detail.constant_profit_rate, float), "constant_profit_rate类型不是float"

def test_get_fund_asset_detail_not_found():
    # 准备测试数据
    user = DEFAULT_USER
    sub_account_no = "20891029"
    fund_code = "000000"  # 使用一个不存在的基金代码
    
    # 调用被测试的函数
    asset_detail = get_fund_asset_detail(user, sub_account_no, fund_code)
    # 验证返回结果
    assert asset_detail is None, "对于不存在的基金代码应该返回None"
    #打印结果   
    print(asset_detail) 
    

if __name__ == "__main__":
    # 直接运行测试
    test_get_fund_asset_detail_success()