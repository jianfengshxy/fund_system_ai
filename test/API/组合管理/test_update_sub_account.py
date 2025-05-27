import pytest
import requests
from src.API.组合管理.SubAccountMrg import createSubAccount, updateSubAccount, getSubAssetMultList
from src.domain.user import ApiResponse
from src.domain.sub_account.sub_account_response import SubAccountResponse
from src.domain.sub_account.sub_asset_mult_list_response import SubAssetMultListResponse
from src.common.constant import DEFAULT_USER

def test_update_sub_account_state():
    """测试子账户状态更新流程"""
    print("开始测试更新子账户状态")
    
    # 第一步：将子账户设置为公开状态
    result = updateSubAccount(user=DEFAULT_USER, sub_account_no="26674586", open_state=2)
    print(f"设置公开状态API响应结果: {result}")
    
    assert isinstance(result, ApiResponse)
    assert result.Success == True
    assert isinstance(result.Data, SubAccountResponse)
    assert result.Data.open_state == 2  # 验证open_state值为2（公开状态）
    print("公开状态设置验证通过")
    
    # 检查状态是否更新成功
    asset_result = getSubAssetMultList(user=DEFAULT_USER)
    assert isinstance(asset_result, ApiResponse)
    assert asset_result.Success == True
    assert isinstance(asset_result.Data, SubAssetMultListResponse)
    
    target_account = None
    for group in asset_result.Data.list_group:
        if group.sub_account_no == "26674586":
            target_account = group
            break
    
    assert target_account is not None
    assert target_account.open_flag == "2"  # 验证是否为公开状态
    print("公开状态检查验证通过")
    
    # 第二步：将子账户设置为关闭状态
    result = updateSubAccount(user=DEFAULT_USER, sub_account_no="26674586", open_state=3)
    print(f"设置关闭状态API响应结果: {result}")
    
    assert isinstance(result, ApiResponse)
    assert result.Success == True
    assert isinstance(result.Data, SubAccountResponse)
    assert result.Data.open_state == 3  # 验证open_state值为3（关闭状态）
    print("关闭状态设置验证通过")
    
    # 再次检查状态是否更新成功
    asset_result = getSubAssetMultList(user=DEFAULT_USER)
    assert isinstance(asset_result, ApiResponse)
    assert asset_result.Success == True
    
    target_account = None
    for group in asset_result.Data.list_group:
        if group.sub_account_no == "26674586":
            target_account = group
            break
    
    assert target_account is not None
    assert target_account.open_flag == "3"  # 验证是否为关闭状态
    print("关闭状态检查验证通过")