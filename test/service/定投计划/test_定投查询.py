import pytest
import os
import sys
import logging

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# 修改导入路径，使用正确的导入路径
from src.common.constant import DEFAULT_USER
from src.service.定投管理.定投查询.定投查询 import get_all_fund_plan_details
from src.service.基金信息.基金信息 import get_all_fund_info
# 配置日志
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def test_get_all_fund_plan_details():
    """测试获取所有定投计划详情"""
    # 打印测试开始信息
    logger.info("开始测试获取所有定投计划详情")
    
    # 调用函数获取所有定投计划详情
    plan_details = get_all_fund_plan_details(DEFAULT_USER)
    
    # 验证返回结果不为None
    assert plan_details is not None, "返回结果不应为None"
    
    # 验证返回结果是列表
    assert isinstance(plan_details, list), "返回结果应该是列表"
    
    logger.info(f"{'='*80}")
    logger.info(f"{'基金定投计划概览':^80}")
    logger.info(f"{'='*80}")
    
    # 如果有定投计划，验证每个计划的基本信息
    for detail in plan_details:
        # 验证计划对象存在
        assert detail is not None, "计划详情对象不应为None"
        
        # 验证计划基本属性
        plan = detail.rationPlan
        
        # 获取实时估值信息
        estimated_change = 0.0
        estimated_nav = 0.0
        try:
            fund_info = get_all_fund_info(DEFAULT_USER, plan.fundCode)
            if fund_info:
                estimated_change = getattr(fund_info, 'estimated_change', 0.0) or 0.0
                estimated_nav = getattr(fund_info, 'estimated_value', 0.0) or 0.0
        except Exception as e:
            logger.warning(f"获取估值失败 {plan.fundCode}: {e}")
            
        # 数据格式化
        plan_id_short = plan.planId[:8] + "..." if plan.planId else "N/A"
        fund_name = plan.fundName
        fund_code = plan.fundCode
        sub_account = plan.subAccountName or "默认账户"
        
        amount = f"{plan.amount:.2f}"
        assets = f"{plan.planAssets:.2f}"
        
        profit = plan.rationProfit if plan.rationProfit is not None else 0.0
        total_profit = plan.totalProfit if plan.totalProfit is not None else 0.0
        
        profit_rate = (plan.rationProfitRate * 100) if plan.rationProfitRate is not None else 0.0
        total_profit_rate = (plan.totalProfitRate * 100) if plan.totalProfitRate is not None else 0.0
        
        # 预估收益率 = 当前收益率 + 估算涨跌幅
        estimated_profit_rate = profit_rate + float(estimated_change)
        
        # 打印详细卡片
        logger.info(f"基金: {fund_name} ({fund_code}) | 子账户: {sub_account}")
        logger.info(f"{'-'*80}")
        logger.info(f"  计划ID: {plan_id_short:<20} 状态: {plan.planState} ({plan.planExtendStatus})")
        logger.info(f"  定投金额: {amount:<15} 计划资产: {assets:<15} 单位净值: {plan.unitPrice}")
        logger.info(f"  {'-'*76}")
        logger.info(f"  {'':<15} {'当前值':<15} {'今日估算':<15} {'预估值':<15}")
        logger.info(f"  收益率:        {profit_rate:>14.2f}% {estimated_change:>14.2f}% {estimated_profit_rate:>14.2f}%")
        logger.info(f"  定投收益:     {profit:>15.2f}")
        logger.info(f"  总收益:       {total_profit:>15.2f}")
        
        if hasattr(plan, 'targetRate') and plan.targetRate:
             logger.info(f"  目标收益率:   {plan.targetRate}")
             
        logger.info(f"{'='*80}")
        logger.info("")

    # 打印测试结果摘要
    logger.info(f"测试完成，共获取到 {len(plan_details)} 个定投计划")

if __name__ == "__main__":
    # 直接运行测试
    logger.info("直接运行定投计划查询测试")
    test_get_all_fund_plan_details()