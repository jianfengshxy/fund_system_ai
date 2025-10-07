import logging
import os
import sys
from typing import Optional

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.domain.user.User import User
from src.service.基金信息.基金信息 import get_all_fund_info
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.service.资产管理.get_fund_asset_detail import (
    get_sub_account_asset_by_name,
)
from src.service.交易管理.购买基金 import commit_order
from src.common.constant import DEFAULT_USER

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def increase_funds(user: User, sub_account_name: str, fund_list: Optional[list] = None) -> bool:
    """自定义组合算法新增：从 payload 传入的 fund_list 获取要交易的基金及其金额。
    对于组合中未持有的基金，直接按 amount 进行购买；已持有基金暂不处理。
    """
    customer_name = user.customer_name
    logger.info(f"开始为用户 {customer_name} 执行新增操作，组合: {sub_account_name}")

    # 获取组合账号
    sub_account_no = getSubAccountNoByName(user, sub_account_name)
    if not sub_account_no:
        logger.error(f"未找到组合 {sub_account_name} 的账号")
        return False

    # 校验 payload 的基金列表
    if not fund_list or not isinstance(fund_list, list):
        logger.info(f"未提供 fund_list 或格式不正确，跳过自定义组合新增")
        return False

    # 获取组合资产，构建已持有基金集合
    asset_details = get_sub_account_asset_by_name(user, sub_account_name) or []
    held_codes = {getattr(a, 'fund_code', '') for a in asset_details if getattr(a, 'fund_code', None)}
    logger.info(f"组合 {sub_account_name} 当前持有基金数: {len(held_codes)}")

    success_count = 0

    for fund_item in fund_list:
        try:
            fund_code = (fund_item or {}).get('fund_code')
            fund_amount = (fund_item or {}).get('amount')
            if not fund_code:
                logger.info("fund_code 缺失，跳过该条目")
                continue
            if not fund_amount or float(fund_amount) <= 0:
                logger.info(f"基金 {fund_code} 的 amount 缺失或无效，跳过该基金")
                continue

            fund_info = get_all_fund_info(user, fund_code)
            fund_name = getattr(fund_info, 'fund_name', fund_code)
            logger.info(f"基金信息：{fund_name}({fund_code})，可申购：{getattr(fund_info, 'can_purchase', None)}")

            # 若基金不在资产列表中，则直接购买
            if fund_code not in held_codes:
                logger.info(f"发现新基金，未持有，准备购买：{fund_name}({fund_code})，金额: {fund_amount}")
                try:
                    res = commit_order(user, sub_account_no, fund_code, float(fund_amount))
                    if res is not None and getattr(res, 'status', None) == 1:
                        success_count += 1
                        logger.info(f"购买成功：{fund_name}({fund_code})，金额: {fund_amount}")
                    else:
                        logger.info(f"购买未成功或被系统保护跳过：{fund_name}({fund_code})")
                except Exception as e:
                    logger.error(f"购买失败：{fund_name}({fund_code})，异常: {e}")
                # 新增逻辑只覆盖“未持有→购买”，继续处理下一只
                continue

            # 已持有基金：当前先不处理新增（后续补充完整加仓逻辑）
            logger.info(f"已持有基金，新增逻辑不处理：{fund_name}({fund_code})")

        except Exception as e:
            logger.error(f"处理 {fund_item} 失败: {e}")

    logger.info(f"新增完成：{customer_name} 成功执行 {success_count} 次购买操作")
    return success_count > 0


if __name__ == "__main__":
    try:
        increase_funds(
            DEFAULT_USER,
            "海外基金组合",
            fund_list=[
                {"fund_code": "016702", "fund_name": "银华海外数字经济量化选股混合发起式(QDII)C", "amount": 5000.0},
                {"fund_code": "006105", "fund_name": "宏利印度股票(QDII)", "amount": 5000.0},
                {"fund_code": "161226", "fund_name": "国投瑞银白银期货(LOF)A", "amount": 5000.0},
                {"fund_code": "017873", "fund_name": "汇添富香港优势精选混合(QDII)C", "amount": 5000.0},
                {"fund_code": "019449", "fund_name": "摩根日本精选股票(QDII)C", "amount": 5000.0}
            ]
        )
        logging.info(f"用户 {DEFAULT_USER.customer_name} 新增操作完成")
    except Exception as e:
        logging.error(f"测试用户处理失败：{str(e)}")