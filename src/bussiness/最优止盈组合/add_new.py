import logging
import sys
import os
import logging
from typing import List, Optional, Set
from concurrent.futures import ThreadPoolExecutor

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.domain.user.User import User
from src.common.constant import DEFAULT_USER
from src.API.登录接口.login import inference_passport_for_bind, login
from src.API.大数据.加仓风向标 import getFundInvestmentIndicators
from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name
from src.API.银行卡信息.CashBag import getCashBagAvailableShareV2
from src.API.交易管理.buyMrg import commit_order
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.service.基金信息.基金信息 import get_all_fund_info
from src.domain.fund.fund_info import FundInfo
from src.domain.asset.asset_details import AssetDetails

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

#第一列：手机号 account
# 第二列：密码 password
# 第三列：支付密码
# 第四列：姓名
# 第五列：sub_account_name组合名称
# 第六列：budget 预算
user_list = [
    # ("13918797997","Zj951103","Zj951103","仇晓钰","最优止盈",1000000.0),
#     ("13918199137", "sWX15706","sWX15706","施小雨","最优止盈",1000000.0),
    ("13820198186", "tang8186","tang8186","唐祖华","最优止盈",450000.0),
    ("17782571152", "s00127479","s00127479","邵科","最优止盈",150000.0),
    # ("13830702104", "chb201106?","chb201106?","程斌","最优止盈",100000.0),
    ("13851562586", "muyi0628","muyi0628","铁宏安","最优止盈",30000.0),
    ("13910680799", "fuliang223147","fuliang223147","梁红兵","最优止盈",40000.0),
    ("13974549306", "huigengsi937367","huigengsi937367","朱沅罗尘","最优止盈",50000.0),
    ("13977796363", "tang6363","tang6363","唐显扬","最优止盈",400000.0),
      # ("15184175351", "duxingchen123","duxingchen123","都星辰","最优止盈",20000.0),
    ("15373193078", "sy811123","sy811123","张莹莹","最优止盈",50000.0),
    ("15936530625", "wch601249697","wch601249697","王长海","最优止盈",50000.0),
    ("18648900788", "ldw88888","ldw88888","李代文","最优止盈",50000.0),
    ("13426206037", "fuyj223147","fuyj223147","付一军","最优止盈",50000.0),
    ("13500819290", "guojing1985","guojing1985","郭婧","最优止盈",200000.0),
    ("13562500306", "lilin926","lilin926","刘文杰","最优止盈",60000.0),
    ("13571973393", "wj121109","wj121109","安城","最优止盈",500000.0),
    ("13584903800", "hu123321","hu123321","胡春红","最优止盈",300000.0),
    #("13611617975", "65253056lml","65253056lml","胡琳元","最优止盈",100000000.0),
    # ("13636306263", "cy863391X","cy863391X","陈扬","最优止盈",200000.0),
    ("13817533699", "demone40","demone40","东岳亮","最优止盈",150000.0)
]

def add_new_funds(user: User, sub_account_name: str = "最优止盈", total_budget: float = 10000.0) -> bool:
    """
    新增基金算法实现：
    1. 获取加仓风向标数据
    2. 获取用户组合中的所有基金
    3. 筛选出用户未持有的基金或指数基金
    4. 执行买入操作
    
    Args:
        user: 用户对象
        sub_account_name: 组合名称，默认为"最优止盈"
        total_budget: 总预算金额，默认10000元
    
    Returns:
        bool: 操作是否成功
    """
    logger.info(f"开始为用户 {user.customer_name} 执行新增基金操作，总预算：{total_budget}元")
    
    # 使用increase.py的公式计算每个基金的购买金额
    fund_num = 10
    day_amount = round(total_budget * 8 / 250, 2)
    budget_per_fund = round(day_amount / fund_num, 2)
    logger.info(f"计算得出单个基金购买金额：{budget_per_fund}元")
    
    customer_name = user.customer_name
    logger.info(f"========== 开始执行新增基金算法 ==========")
    logger.info(f"用户: {customer_name}")
    logger.info(f"组合名称: {sub_account_name}")
    logger.info(f"每个基金预算: {budget_per_fund}元")
    
    try:
        # 步骤1: 获取加仓风向标数据
        logger.info("=== 步骤1: 获取加仓风向标数据 ===")
        wind_vane_funds = getFundInvestmentIndicators(user, page_size=20)
        if not wind_vane_funds:
            logger.error("获取加仓风向标数据失败")
            return False
        
        logger.info(f"获取到 {len(wind_vane_funds)} 个加仓风向标基金")
        for i, fund in enumerate(wind_vane_funds, 1):
            logger.info(f"  风向标基金{i}: {fund.fund_name}({fund.fund_code}) - 类型:{fund.fund_type} - 排名:{fund.product_rank}")
        
        # 步骤2: 获取用户对应组合里面所有的基金
        logger.info("=== 步骤2: 获取用户组合中的所有基金 ===")
        user_assets = get_sub_account_asset_by_name(user, sub_account_name)
        if user_assets is None:
            logger.error(f"获取用户组合 {sub_account_name} 资产失败")
            return False
        
        # 提取用户持有的基金代码和跟踪指数
        user_fund_codes = set()
        user_index_codes = set()
        
        logger.info(f"用户组合中共有 {len(user_assets)} 个基金")
        for i, asset in enumerate(user_assets, 1):
            user_fund_codes.add(asset.fund_code)
            logger.info(f"  持有基金{i}: {asset.fund_name}({asset.fund_code}) - 份额:{asset.available_vol}")
            
            # 如果是指数基金，获取跟踪指数
            try:
                fund_info = get_all_fund_info(user, asset.fund_code)
                if fund_info and hasattr(fund_info, 'fund_type') and fund_info.fund_type == "000":
                    if hasattr(fund_info, 'index_code') and fund_info.index_code:
                        user_index_codes.add(fund_info.index_code)
                        logger.info(f"    指数基金跟踪指数: {fund_info.index_code}")
            except Exception as e:
                logger.warning(f"获取基金 {asset.fund_code} 详细信息失败: {e}")
        
        logger.info(f"用户持有基金代码: {user_fund_codes}")
        logger.info(f"用户持有指数基金跟踪的指数: {user_index_codes}")
        
        # 步骤3: 检查用户预算
        logger.info("=== 步骤3: 检查用户可用资金 ===")
        bank_cards = getCashBagAvailableShareV2(user)
        if not bank_cards:
            logger.error("获取银行卡信息失败")
            return False
        
        available_balance = bank_cards[0].CurrentRealBalance
        logger.info(f"用户可用余额: {available_balance}元")
        
        if available_balance < budget_per_fund:
            logger.warning(f"用户可用余额 {available_balance}元 小于单个基金预算 {budget_per_fund}元")
            budget_per_fund = min(available_balance * 0.8, budget_per_fund)  # 使用80%的可用余额
            logger.info(f"调整单个基金预算为: {budget_per_fund}元")
        
        # 获取组合账号
        sub_account_no = getSubAccountNoByName(user, sub_account_name)
        if not sub_account_no:
            logger.error(f"未找到组合名称 {sub_account_name} 对应的组合账号")
            return False
        
        logger.info(f"组合账号: {sub_account_no}")
        
        # 步骤4: 筛选需要买入的基金
        logger.info("=== 步骤4: 筛选需要买入的基金 ===")
        funds_to_buy = []
        
        for fund in wind_vane_funds:
            should_buy = False
            reason = ""
            
            # 检查基金是否已在用户组合中
            if fund.fund_code in user_fund_codes:
                logger.info(f"跳过基金 {fund.fund_name}({fund.fund_code}): 用户已持有")
                continue
            
            # 如果是指数基金（类型000），检查跟踪指数是否重复
            if fund.fund_type == "000":
                try:
                    fund_info = get_all_fund_info(user, fund.fund_code)
                    if fund_info and hasattr(fund_info, 'index_code') and fund_info.index_code:
                        if fund_info.index_code in user_index_codes:
                            logger.info(f"跳过指数基金 {fund.fund_name}({fund.fund_code}): 用户已持有跟踪相同指数({fund_info.index_code})的基金")
                            continue
                        else:
                            should_buy = True
                            reason = f"指数基金，跟踪指数 {fund_info.index_code} 用户未持有"
                    else:
                        should_buy = True
                        reason = "指数基金，无法获取跟踪指数信息，但用户未持有该基金"
                except Exception as e:
                    logger.warning(f"获取指数基金 {fund.fund_code} 详细信息失败: {e}")
                    should_buy = True
                    reason = "指数基金，获取详细信息失败，但用户未持有该基金"
            else:
                # 非指数基金，直接买入
                should_buy = True
                reason = f"非指数基金（类型:{fund.fund_type}），用户未持有"
            
            if should_buy:
                funds_to_buy.append(fund)
                logger.info(f"选择买入基金: {fund.fund_name}({fund.fund_code}) - 原因: {reason}")
        
        if not funds_to_buy:
            logger.info("没有需要买入的新基金")
            return True
        
        logger.info(f"共选择 {len(funds_to_buy)} 个基金进行买入")
        
        # 执行买入操作
        logger.info("=== 开始执行买入操作 ===")
        success_count = 0
        
        for i, fund in enumerate(funds_to_buy, 1):
            logger.info(f"正在买入第 {i}/{len(funds_to_buy)} 个基金: {fund.fund_name}({fund.fund_code})")
            
            try:
                # 检查基金是否可申购
                fund_info = get_all_fund_info(user, fund.fund_code)
                if fund_info and hasattr(fund_info, 'can_purchase') and not fund_info.can_purchase:
                    logger.warning(f"基金 {fund.fund_name}({fund.fund_code}) 当前不可申购，跳过")
                    continue
                
                # 执行买入
                trade_result = commit_order(user, sub_account_no, fund.fund_code, budget_per_fund)
                
                if trade_result:
                    logger.info(f"买入成功: {fund.fund_name}({fund.fund_code}) - 金额: {budget_per_fund}元 - 订单号: {trade_result.busin_serial_no}")
                    success_count += 1
                else:
                    logger.error(f"买入失败: {fund.fund_name}({fund.fund_code})")
                    
            except Exception as e:
                logger.error(f"买入基金 {fund.fund_name}({fund.fund_code}) 时发生异常: {e}")
        
        logger.info(f"=== 新增基金操作完成 ===")
        logger.info(f"成功买入 {success_count}/{len(funds_to_buy)} 个基金")
        
        return success_count > 0
        
    except Exception as e:
        logger.error(f"新增基金算法执行失败: {e}")
        import traceback
        logger.error(f"异常堆栈: {traceback.format_exc()}")
        return False

def add_new_all_users():
    """为所有用户执行新增基金操作"""
    for user_info in user_list:
        account = user_info[0]
        password = user_info[1]
        pay_password = user_info[2]
        customer_name = user_info[3]
        sub_account_name = user_info[4]
        total_budget = user_info[5]
        
        try:
            # 登录用户
            user = login(account, password)
            user = inference_passport_for_bind(user)
            user.pay_password = pay_password
            user.budget = total_budget
            logging.info(f"开始为用户 {user.customer_name} 执行新增基金操作，总预算：{total_budget}元")
            
            # 执行新增基金操作
            add_new_funds(user, sub_account_name, total_budget)
            
            logging.info(f"用户 {user.customer_name} 新增基金操作完成")
            
        except Exception as e:
            logging.error(f"登录失败的账号：{account}，用户名：{customer_name}，错误信息：{str(e)}")
            continue

if __name__ == "__main__":
    # 测试单个用户的新增基金流程
    try:
        test_user = DEFAULT_USER    
        logging.info(f"测试用户 {test_user.customer_name} 登录成功")
        
        # 测试新增基金
        add_new_funds(test_user, "最优止盈", 10000)
        
        logging.info("测试新增基金操作完成")
        
    except Exception as e:
        logging.error(f"测试用户登录失败：{str(e)}")
        