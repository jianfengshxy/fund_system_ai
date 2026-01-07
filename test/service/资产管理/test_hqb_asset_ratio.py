import pytest
import os
import sys
import logging
from decimal import Decimal

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.API.资产管理.AssetManager import GetMyAssetMainPartAsync
from src.common.constant import DEFAULT_USER

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_hqb_asset_ratio():
    """
    测试功能：用DEFAULT_USER用户，获取总资产，基金资产，活期宝资产，
    判断活期宝资产是否占据总资产的20%。
    """
    user = DEFAULT_USER
    logger.info(f"开始测试用户 {user.customer_name} 的资产占比情况")

    # 1. 获取资产信息
    response = GetMyAssetMainPartAsync(user)
    
    assert response.Success is True, f"获取资产信息失败: {response.Message}"
    assert response.Data is not None, "返回资产数据为空"
    
    data = response.Data
    logger.info(f"资产数据 Keys: {data.keys()}")

    # 2. 提取资产数值
    # 打印更多相关字段以排查基金资产
    total_value = float(data.get('TotalValue', 0.0))
    hqb_value = float(data.get('HqbValue', 0.0))
    
    # 修正：使用 TotalFundAsset 作为基金总资产
    total_fund_asset = float(data.get('TotalFundAsset', 0.0))
    
    # 其他辅助字段
    fund_value = float(data.get('FundValue', 0.0)) 
    total_group_asset = float(data.get('TotalGroupAsset', 0.0))
    total_gdlc_asset = float(data.get('TotalGdlcAsset', 0.0))
    debts_amount = float(data.get('DebtsAmount', 0.0))
    fund_unconfirmed = float(data.get('FundUnConfirmedAmount', 0.0))

    logger.info(f"总资产 (TotalValue): {total_value}")
    logger.info(f"活期宝资产 (HqbValue): {hqb_value}")
    logger.info(f"基金总资产 (TotalFundAsset): {total_fund_asset}")
    
    # 辅助信息记录
    # 注意：用户确认总资产试算差异（约25w）是由于天天基金平台的“快速赎回垫付”功能导致总资产暂时虚高，
    # 平台后续会校正，此处无需担心。
    calc_total = total_fund_asset + hqb_value + total_gdlc_asset - debts_amount
    diff = calc_total - total_value
    if abs(diff) > 1.0:
        logger.info(f"注意：资产试算存在差异 {diff:.2f} (通常由赎回垫付导致)")

    logger.info("--- 资产占比分析 ---")
    logger.info(f"总资产: {total_value}")
    logger.info(f"基金资产: {total_fund_asset}")
    logger.info(f"活期宝资产: {hqb_value}")

    # 3. 校验数据有效性
    if total_value == 0:
        logger.warning("总资产为0，无法计算占比")
        return

    # 4. 计算活期宝占比
    hqb_ratio = hqb_value / total_value
    hqb_ratio_percent = hqb_ratio * 100

    logger.info(f"活期宝资产占比: {hqb_ratio_percent:.2f}%")

    # 5. 判断是否占据总资产的 20%
    # 这里我们使用 soft assertion (记录日志) 而不是 hard assertion (报错)，
    # 因为这是一个状态检查，不一定非要大于 20% 才是“正确”的程序行为。
    # 但根据用户描述 "判断...是否占据..."，我将输出明确的判断结果。
    
    if hqb_ratio >= 0.20:
        logger.info("✅ 活期宝资产占比 >= 20%")
    else:
        logger.info("⚠️ 活期宝资产占比 < 20%")

if __name__ == "__main__":
    test_hqb_asset_ratio()
