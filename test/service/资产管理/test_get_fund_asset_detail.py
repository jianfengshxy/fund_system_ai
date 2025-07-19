import logging
import os
import sys

# 配置 logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.service.资产管理.get_fund_asset_detail import get_fund_asset_detail
from src.common.constant import DEFAULT_USER
from src.domain.asset.asset_details import AssetDetails
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName

logger = logging.getLogger(__name__)

def test_get_fund_asset_detail_success():
    """测试 get_fund_asset_detail 函数 - 成功案例"""
    logger.info("开始测试 get_fund_asset_detail 函数 - 成功案例")
    
    user = DEFAULT_USER
    sub_account_name = "低风险组合"
    fund_code = "001770"
    
    sub_account_no = getSubAccountNoByName(user, sub_account_name)
    if not sub_account_no:
        logger.warning(f"未找到组合 {sub_account_name} 的 sub_account_no")
        return
    
    asset_detail = get_fund_asset_detail(user, sub_account_no, fund_code)
    
    if asset_detail:
        logger.info(f"基金资产详情: {asset_detail}")
        if asset_detail.fund_code == fund_code and hasattr(asset_detail, 'constant_profit_rate') and isinstance(asset_detail.constant_profit_rate, float):
            logger.info("测试成功: 基金代码匹配且 constant_profit_rate 是 float 类型")
        else:
            logger.warning("测试失败: 基金代码不匹配或 constant_profit_rate 属性无效")
    else:
        logger.warning("测试失败: 未找到基金资产详情")
    
    logger.info("测试 get_fund_asset_detail 函数 - 成功案例完成")


if __name__ == "__main__":
    test_get_fund_asset_detail_success()
  
