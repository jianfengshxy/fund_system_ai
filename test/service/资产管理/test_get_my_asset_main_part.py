import pytest
import os
import sys
import logging

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.API.资产管理.AssetManager import GetMyAssetMainPartAsync
from src.common.constant import DEFAULT_USER
from src.domain.fund_plan import ApiResponse

def test_get_my_asset_main_part_success():
    # 准备测试数据
    user = DEFAULT_USER
    
    # 调用被测试的函数
    response = GetMyAssetMainPartAsync(user)
    print(f"资产信息响应: {response}")
    
    # 验证返回结果
    assert isinstance(response, ApiResponse), "返回结果不是 ApiResponse 类型"
    assert response.Success is True, "请求不成功"
    assert response.ErrorCode is None or response.ErrorCode == '', "存在错误代码"
    assert response.Data is not None, "返回数据为空"
    
    # 验证返回的数据结构
    data = response.Data
    assert 'TotalAsset' in data, "返回数据缺少总资产信息"
    assert isinstance(float(data['TotalAsset']), float), "总资产不是数值类型"

def test_get_my_asset_main_part_with_invalid_token():
    # 准备测试数据：使用无效的 token
    user = DEFAULT_USER
    original_token = user.c_token
    user.c_token = "invalid_token"
    
    try:
        # 调用被测试的函数
        response = GetMyAssetMainPartAsync(user)
        
        # 验证返回结果
        assert isinstance(response, ApiResponse), "返回结果不是 ApiResponse 类型"
        assert response.Success is False, "使用无效token应该请求失败"
        assert response.ErrorCode is not None, "应该返回错误代码"
    finally:
        # 恢复原始 token
        user.c_token = original_token

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)d)')
    # 直接运行测试
    test_get_my_asset_main_part_success()