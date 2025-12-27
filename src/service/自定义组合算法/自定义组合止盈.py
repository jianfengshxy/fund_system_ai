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
from src.API.交易管理.trade import get_bank_shares
from src.service.交易管理.赎回基金 import (
    sell_0_fee_shares,
    sell_low_fee_shares,
    sell_usable_non_zero_fee_shares,
)
from src.service.资产管理.get_fund_asset_detail import (
    get_sub_account_asset_by_name,
    get_fund_asset_detail
)
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.API.资产管理.AssetManager import GetMyAssetMainPartAsync
from src.API.资产管理.getAssetListOfSub import get_asset_list_of_sub
from src.service.定投管理.定投查询.定投查询 import get_all_fund_plan_details
from src.common.constant import DEFAULT_USER

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def redeem_funds(user: User, sub_account_name: str, fund_list: Optional[list] = None) -> bool:
    """自定义组合算法止盈：从 payload 传入的 fund_list 获取要交易的基金及其金额，
    不依赖定投计划；止盈逻辑与 bussiness 层保持一致。
    """
    customer_name = user.customer_name
    logger.info(f"开始为用户 {customer_name} 执行止盈操作，组合: {sub_account_name}")

    # 获取组合账号
    sub_account_no = getSubAccountNoByName(user, sub_account_name)
    if not sub_account_no:
        logger.error(f"未找到组合 {sub_account_name} 的账号")
        return False

    success_count = 0

    assets = get_asset_list_of_sub(user, sub_account_no)
    for asset in assets:
        try:
            fund_code = asset.fund_code

            fund_info = get_all_fund_info(user, fund_code)
            fund_name = fund_info.fund_name
            logger.info(f"基金信息：{fund_name}({fund_code})，可申购：{fund_info.can_purchase}，可赎回：{fund_info.can_redeem}")

            shares = get_bank_shares(user, sub_account_no, fund_code)

            # 资产详情（复制业务层字段与日志）
            try:
                asset_detail = get_fund_asset_detail(user, sub_account_no, fund_code)
                if asset_detail is not None:
                    plan_assets = asset_detail.asset_value
                    fund_type = fund_info.fund_type
                    constant_profit_rate = asset_detail.constant_profit_rate
                    logger.info(
                        f"{fund_name}资产详情获取成功 - 资产价值: {asset_detail.asset_value}, 基金类型:{fund_type},收益率: {constant_profit_rate}%, 估值增长率: {fund_info.estimated_change}%, 在途交易数: {asset_detail.on_way_transaction_count}"
                    )
                else:
                    logger.info(f"组合{sub_account_no}的{fund_name}{fund_code}资产为空。Skip .........")
                    continue
            except Exception as e:
                logger.error(f"获取资产详情失败: {e}")
                continue

            try:
                # 尝试从传入的 fund_list 中获取单次投资金额
                fund_amount = 0.0
                if fund_list:
                    for item in fund_list:
                        if item.get("fund_code") == fund_code:
                            fund_amount = float(item.get("amount", 0.0))
                            break
                
                # 如果没找到或为0，则默认使用当前资产（此时 times = 1.0，即不触发低仓位保护）
                if fund_amount <= 0:
                     fund_amount = float(plan_assets) if plan_assets and float(plan_assets) > 0 else 1.0

                times = round(float(plan_assets) / float(fund_amount), 2)
            except Exception:
                logger.info(f"基金 {fund_name}{fund_code} 的资产解析失败，跳过")
                continue
            volatility = fund_info.volatility 

            # 收益率计算（与业务层一致）
            current_profit_rate = constant_profit_rate if constant_profit_rate is not None else 0.0
            estimated_change = fund_info.estimated_change if fund_info.estimated_change is not None else 0.0
            estimated_profit_rate = current_profit_rate + estimated_change
            rank_100 = fund_info.rank_100day

            logger.info(f"收益率计算：当前收益率{current_profit_rate}%，估值变化{estimated_change}%，预估收益率{estimated_profit_rate}%")
            logger.info(f"其他指标：波动率{volatility}%，100日排名{rank_100}，投资次数{times}")

            if shares == []:
                logger.info("份额为空，跳过该计划")
                continue
            if times < 0.98 and times > 0.0:
                logger.info(f"组合{sub_account_no}，基金{fund_name}({fund_code})资产{plan_assets:.2f}，当前资产倍数{times},满足限购保护，停止止盈。")
                continue
            if estimated_profit_rate < 1.0:
                logger.info(f"组合{sub_account_no}的{fund_name}{fund_code}的收益率{estimated_profit_rate}小于1.0.")
                continue

            logger.info("开始检查止盈条件...")
            stop_rate = 5.0
            # 指数基金：排名>90 且 >1% 即止盈（赎回低费率）
            # if fund_type == '000' and estimated_profit_rate > 1.0 and rank_100 > 90 and fund_info.estimated_change != 0.0:
            #     logger.info(f"{customer_name}的止盈操作开始：指数基金{fund_name}{fund_code}预估收益{estimated_profit_rate},100日排名:{rank_100},实际止盈点:1.0")
            #     res = sell_low_fee_shares(user, sub_account_no, fund_code, shares)
            #     if res is not None and getattr(res, 'busin_serial_no', None):
            #         success_count += 1
            #     continue

            # 赎回 0 费率份额
            if  estimated_profit_rate > 3.0:
                logger.info(f"{customer_name}的止盈操作开始：基金{fund_name}{fund_code}预估收益{estimated_profit_rate},赎回0费率份额,实际止盈点:3.0")
                sell_0_fee_shares(user, sub_account_no, fund_code, shares)

            # 基本止盈：预估收益率 > 动态止盈点 -> 赎回低费率份额
            if estimated_profit_rate > stop_rate:
                logger.info(f"{customer_name}的止盈操作开始：基金{fund_name}{fund_code}预估收益{estimated_profit_rate},实际止盈点:{stop_rate}")
                res = sell_low_fee_shares(user, sub_account_no, fund_code, shares)
                if res is not None and getattr(res, 'busin_serial_no', None):
                    success_count += 1
                # 与业务层一致：命中基本止盈后直接继续
                continue
            else:
                logger.info(f"基本止盈条件检查：预估收益{estimated_profit_rate} <= 止盈点{stop_rate}，不满足条件")

        except Exception as e:
            logger.error(f"处理 {fund_code} 失败: {e}")

    logger.info(f"止盈完成：{customer_name} 成功执行 {success_count} 次赎回操作")
    return success_count > 0


if __name__ == "__main__":
    try:
        redeem_funds(
            DEFAULT_USER,
            "海外基金组合",
            fund_list=[
                {"fund_code": "016702", "fund_name": "银华海外数字经济量化选股混合发起式(QDII)C", "amount": 5000.0},
                {"fund_code": "006105", "fund_name": "宏利印度股票(QDII)", "amount": 5000.0},
                {"fund_code": "161226", "fund_name": "国投瑞银白银期货(LOF)A", "amount": 5000.0},
                {"fund_code": "017873", "fund_name": "汇添富香港优势精选混合(QDII)C", "amount": 5000.0},
                {"fund_code": "019449", "fund_name": "摩根日本精选股票(QDII)C", "amount": 5000.0},
                {"fund_code": "501018", "fund_name": "南方原油A", "amount": 5000.0},
                {"fund_code": "016453", "fund_name": "南方纳斯达克100指数发起(QDII)C", "amount": 5000.0},
                {"fund_code": "000614", "fund_name": "华安德国(DAX)联接(QDII)A", "amount": 5000.0},
                {"fund_code": "021539", "fund_name": "华安法国CAC40ETF发起式联接(QDII)A", "amount": 5000.0},
                {"fund_code": "015016", "fund_name": "华安德国(DAX)联接(QDII)C", "amount": 5000.0},
                {"fund_code": "008764", "fund_name": "天弘越南市场股票发起(QDII)C", "amount": 5000.0},
                {"fund_code": "501312", "fund_name": "华宝海外科技股票(QDII-LOF)A", "amount": 5000.0},
                {"fund_code": "017204", "fund_name": "华宝海外科技股票(QDII-LOF)C", "amount": 5000.0},
                {"fund_code": "021540", "fund_name": "华安法国CAC40ETF发起式联接(QDII)C", "amount": 5000.0},
                {"fund_code": "009975", "fund_name": "华宝标普美国消费人民币C", "amount": 5000.0},
                {"fund_code": "008706", "fund_name": "建信富时100指数(QDII)C人民币", "amount": 5000.0},
                {"fund_code": "007844", "fund_name": "华宝标普油气上游股票人民币C", "amount": 5000.0}
            ]
        )
        logging.info(f"用户 {DEFAULT_USER.customer_name} 止盈操作完成")
    except Exception as e:
        logging.error(f"测试用户处理失败：{str(e)}")
