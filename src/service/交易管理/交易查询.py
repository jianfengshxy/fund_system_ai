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
from src.domain.user.User import User
from typing import List, Optional
from src.common.constant import DEFAULT_USER, MOBILE_KEY
from src.API.交易管理.trade import get_trades_list

def get_withdrawable_trades(user, sub_account_no="", fund_code="", bus_type="", status="7"):
    """
    获取可撤单交易列表
    Args:
        user: User对象，包含用户认证信息
        sub_account_no: 子账户编号，默认为空
        fund_code: 基金代码，默认为空
        bus_type: 业务类型，默认为空
        status: 状态，默认为"7"表示可撤单
    Returns:
        List[TradeResult]: 可撤单交易结果列表
    """
    logger = logging.getLogger("TradeQuery")
    logger.info("开始获取可撤单交易列表")
    
    # 调用API层的get_trades_list函数，传入状态参数"7"表示可撤单
    trades = get_trades_list(user, sub_account_no, fund_code, bus_type, status)
    
    logger.info(f"获取到 {len(trades)} 条可撤单交易记录")
    return trades

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("TradeQuery")
    
    # 调用函数获取可撤单交易列表
    trades = get_withdrawable_trades(DEFAULT_USER)
    
    # 打印结果
    for i, trade in enumerate(trades):
        logger.info(f"\n{'='*50}")
        logger.info(f"可撤单交易记录 {i+1} 详细信息:")
        logger.info(f"{'-'*50}")
        logger.info(f"交易ID(busin_serial_no): {trade.busin_serial_no}")
        logger.info(f"业务类型(business_type): {trade.business_type}")
        logger.info(f"申请工作日(apply_work_day): {trade.apply_work_day}")
        logger.info(f"申请金额/份额(amount): {trade.amount}")
        logger.info(f"交易状态(status): {trade.status}")
        logger.info(f"显示属性(show_com_prop): {trade.show_com_prop}")
        logger.info(f"基金代码(fund_code): {trade.fund_code}")
        logger.info(f"{'='*50}")