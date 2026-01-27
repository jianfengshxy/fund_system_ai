import os
from datetime import datetime
from zoneinfo import ZoneInfo
import sys
import logging
import urllib3  # 添加对 urllib3 的导入
from src.common.fc_event import parse_fc_event  # 局部导入，避免额外修改导入区
# 禁用 urllib3 的警告信息
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 添加 src 到 Python 模块路径
sys.path.append('src')

# 导入需要的变量和函数
from src.common.constant import SERVER_VERSION, PASSPORT_CTOKEN
from src.common.constant import DEFAULT_USER
# 将业务层导入改为带别名，避免与下方同名包装函数冲突
from src.bussiness.全局智能定投处理.increase import increase_all_fund_plans as increase_all_fund_plans_biz
from src.bussiness.全局智能定投处理.redeem import redeem_all_fund_plans as redeem_all_fund_plans_biz
from src.bussiness.全局智能定投处理.dissolve_plan import dissolve_daily_plan
# 添加 add_plan 函数的导入
from src.bussiness.全局智能定投处理.add_plan import add_plan
# 添加组合定投管理函数的导入
from src.bussiness.组合定投.指数型组合定投管理 import create_plan_by_group_for_index_funds,dissolve_plan_by_group_for_index_funds
from src.domain.user.User import User
from src.common.constant import DEFAULT_USER, DEFAULT_FUND_PLAN_DETAIL, QIU_XIAOYU

# 在现有导入语句后添加
from src.bussiness.组合定投.主动型组合定投管理 import create_plan_by_group, dissolve_plan_by_group
from src.bussiness.组合定投.increase import increase as portfolio_increase  # 新增导入
from src.service.大数据.加仓风向标服务 import save_fund_investment_indicators
import json

# 新增导入 get_user_all_info
from src.service.用户管理.用户信息 import get_user_all_info

# 新增导入 add_new_funds
from src.bussiness.最优止盈组合.add_new import add_new_funds as add_new_biz
# 新增：导入 bussiness 层的加仓薄封装（避免命名冲突，使用别名）
from src.bussiness.最优止盈组合.increase import increase as increase_biz
# 新增：导入 bussiness 层的止盈薄封装
from src.bussiness.最优止盈组合.redeem import redeem as redeem_biz
from src.common.errors import RetriableError, ValidationError, NonRetriableError

# 新增：导入“见龙在田”业务层新增薄封装
from src.bussiness.见龙在田.add_new import add_new_funds as jianlong_add_new_biz

# 导入大数据服务相关函数
from src.service.大数据.增加高频加仓基金到自选组合 import add_frequent_funds_to_fast_profit_group
from src.service.大数据.删除高频加仓基金到自选组合 import remove_infrequent_funds_from_group
from src.bussiness.特殊止盈.定投固定比率止盈 import process_fixed_ratio_redeem

# 初始化日志记录器
from src.common.logger import get_logger
logger = get_logger(__name__)

def redeem(event, context):
    try:
        evt, payload = parse_fc_event(event)

        # 提取参数（与 add_new/increase 的风格保持一致）
        account = payload.get('account')
        password = payload.get('password')
        sub_account_name = payload.get('sub_account_name')
        total_budget = payload.get('total_budget')
        extra = {"account": account, "sub_account_name": sub_account_name, "action": "redeem"}

        # 校验
        if not all([account, password, sub_account_name]):
            logger.error("Payload缺少必填参数: account, password, sub_account_name")
            return

        # 获取用户对象
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return

        logger.info(f"开始为用户 {user.customer_name} 执行止盈操作，组合：{sub_account_name}，预算：{total_budget}", extra=extra)

        # 委托业务层薄封装
        success = redeem_biz(user, sub_account_name, total_budget)

        if success:
            logger.info(f"用户 {user.customer_name} 止盈操作成功", extra=extra)
        else:
            logger.error(f"用户 {user.customer_name} 止盈操作失败", extra=extra)

    except RetriableError as e:
        logger.warning(f"执行止盈时发生异常可重试: {e}", extra={"action": "redeem"})
    except ValidationError as e:
        logger.error(f"执行止盈时发生异常参数错误: {e}", extra={"action": "redeem"})
    except NonRetriableError as e:
        logger.error(f"执行止盈时发生异常不可重试: {e}", extra={"action": "redeem"})
    except Exception as e:
        logger.error(f"执行止盈时发生异常: {e}", extra={"action": "redeem"})

def increase(event, context):
    try:
        evt, payload = parse_fc_event(event)

        # 提取参数（与 add_new 一致的方式）
        account = payload.get('account')
        password = payload.get('password')
        sub_account_name = payload.get('sub_account_name')
        total_budget = payload.get('total_budget')  
        amount = payload.get('amount')              # Optional
        fund_type = payload.get('fund_type', 'all')
        extra = {"account": account, "sub_account_name": sub_account_name, "action": "increase"}

        # 校验
        if not all([account, password, sub_account_name,total_budget]):
            logger.error("Payload缺少必填参数: account, password, sub_account_name 或 total_budget")
            return

        # 获取用户对象
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")

        logger.info(f"开始为用户 {user.customer_name} 执行加仓操作，组合：{sub_account_name}，预算：{total_budget}，amount：{amount}，fund_type：{fund_type}", extra=extra)

        # 业务调用（与 add_new 的调用风格一致）
        success = increase_biz(user, sub_account_name, total_budget, amount, fund_type)

        if success:
            logger.info(f"用户 {user.customer_name} 加仓操作成功", extra=extra)
        else:
            logger.error(f"用户 {user.customer_name} 加仓操作失败", extra=extra)

    except RetriableError as e:
        logger.warning(f"执行加仓时发生异常可重试: {e}", extra={"action": "increase"})
    except ValidationError as e:
        logger.error(f"执行加仓时发生异常参数错误: {e}", extra={"action": "increase"})
    except NonRetriableError as e:
        logger.error(f"执行加仓时发生异常不可重试: {e}", extra={"action": "increase"})
    except Exception as e:
        logger.error(f"执行加仓时发生异常: {e}", extra={"action": "increase"})

#加仓风向标的新增基金调用
def add_new(event, context):
    try:

        evt, payload = parse_fc_event(event)

        # 提取参数
        account = payload.get('account')
        password = payload.get('password')
        sub_account_name = payload.get('sub_account_name')
        total_budget = payload.get('total_budget')
        amount = payload.get('amount')  # Optional
        fund_type = payload.get('fund_type', 'all')
        extra = {"account": account, "sub_account_name": sub_account_name, "action": "add_new"}

        # 校验
        if not all([account, password, sub_account_name, total_budget]):
            logger.error("Payload缺少必填参数: account, password, sub_account_name 或 total_budget")
            return

        # 获取用户对象
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return

        logger.info(f"开始为用户 {user.customer_name} 执行新增基金操作", extra=extra)

        # 业务调用（改为与 add_new 一致的参数风格）
        success = add_new_biz(user, sub_account_name, total_budget, amount, fund_type)

    except RetriableError as e:
        logger.warning(f"add_new 异常可重试: {e}", extra={"action": "add_new"})
    except ValidationError as e:
        logger.error(f"add_new 异常参数错误: {e}", extra={"action": "add_new"})
    except NonRetriableError as e:
        logger.error(f"add_new 异常不可重试: {e}", extra={"action": "add_new"})
    except Exception as e:
        logger.error(f"add_new 函数执行错误: {str(e)}", extra={"action": "add_new"})
        return

def add_new_jianlong(event, context):
    try:
        evt, payload = parse_fc_event(event)

        # 提取参数
        account = payload.get('account')
        password = payload.get('password')
        sub_account_name = payload.get('sub_account_name')
        total_budget = payload.get('total_budget')
        amount = payload.get('amount')  # Optional
        fund_type = payload.get('fund_type', 'all')
        fund_num = payload.get('fund_num', 1)
        spread_days = payload.get('spread_days', 5)
        extra = {"account": account, "sub_account_name": sub_account_name, "action": "jianlong_add_new"}

        # 校验
        if not all([account, password, sub_account_name, total_budget]):
            logger.error("Payload缺少必填参数: account, password, sub_account_name 或 total_budget")
            return

        # 获取用户对象
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return

        logger.info(f"[见龙在田] 开始为用户 {user.customer_name} 执行新增基金操作，组合：{sub_account_name}，预算：{total_budget}，amount：{amount}，fund_type：{fund_type}，fund_num：{fund_num}，spread_days：{spread_days}", extra=extra)

        # 业务调用（见龙在田的新增）
        success = jianlong_add_new_biz(user, sub_account_name, total_budget, amount, fund_type, fund_num, spread_days)

        if success:
            logger.info(f"[见龙在田] 用户 {user.customer_name} 新增基金操作成功", extra=extra)
        else:
            logger.error(f"[见龙在田] 用户 {user.customer_name} 新增基金操作失败", extra=extra)

    except RetriableError as e:
        logger.warning(f"add_new_jianlong 异常可重试: {e}", extra={"action": "jianlong_add_new"})
    except ValidationError as e:
        logger.error(f"add_new_jianlong 异常参数错误: {e}", extra={"action": "jianlong_add_new"})
    except NonRetriableError as e:
        logger.error(f"add_new_jianlong 异常不可重试: {e}", extra={"action": "jianlong_add_new"})
    except Exception as e:
        logger.error(f"add_new_jianlong 函数执行错误: {str(e)}", extra={"action": "jianlong_add_new"})
        return

# 新增：见龙在田加仓入口（参考 add_new_jianlong）
def increase_jianlong(event, context):
    try:
        evt, payload = parse_fc_event(event)

        # 提取参数（与 add_new_jianlong 对齐）
        account = payload.get('account')
        password = payload.get('password')
        sub_account_name = payload.get('sub_account_name')
        total_budget = payload.get('total_budget')
        amount = payload.get('amount')  # Optional
        fund_type = payload.get('fund_type', 'all')
        fund_num = payload.get('fund_num', 5)
        spread_days = payload.get('spread_days', 5)
        extra = {"account": account, "sub_account_name": sub_account_name, "action": "jianlong_increase"}

        # 校验
        if not all([account, password, sub_account_name, total_budget]):
            logger.error("Payload缺少必填参数: account, password, sub_account_name 或 total_budget")
            return

        # 获取用户对象
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return

        logger.info(f"[见龙在田] 开始为用户 {user.customer_name} 执行加仓操作，组合：{sub_account_name}，预算：{total_budget}，amount：{amount}，fund_type：{fund_type}，fund_num：{fund_num}，spread_days：{spread_days}", extra=extra)

        # 业务调用（见龙在田的加仓）
        # 导入见龙在田的加仓业务逻辑
        from src.bussiness.见龙在田.increase import increase as jianlong_increase_biz
        success = jianlong_increase_biz(user, sub_account_name, total_budget, amount, fund_type, fund_num, spread_days)

        if success:
            logger.info(f"[见龙在田] 用户 {user.customer_name} 加仓操作成功", extra=extra)
        else:
            logger.error(f"[见龙在田] 用户 {user.customer_name} 加仓操作失败", extra=extra)

    except RetriableError as e:
        logger.warning(f"increase_jianlong 异常可重试: {e}", extra={"action": "jianlong_increase"})
    except ValidationError as e:
        logger.error(f"increase_jianlong 异常参数错误: {e}", extra={"action": "jianlong_increase"})
    except NonRetriableError as e:
        logger.error(f"increase_jianlong 异常不可重试: {e}", extra={"action": "jianlong_increase"})
    except Exception as e:
        logger.error(f"increase_jianlong 函数执行错误: {str(e)}", extra={"action": "jianlong_increase"})
        return

def increase_all_fund_plans(event, context):
    """为所有基金定投计划执行加仓"""
    increase_all_fund_plans_biz(DEFAULT_USER)
    increase_all_fund_plans_biz(QIU_XIAOYU)
    pass

def redeem_all_fund_plans(event, context):
    """为所有基金定投计划执行止盈"""
    redeem_all_fund_plans_biz(DEFAULT_USER)
    redeem_all_fund_plans_biz(QIU_XIAOYU)
    pass

#每日任务
def daily_task(event, context):
    save_fund_investment_indicators(DEFAULT_USER)
    add_frequent_funds_to_fast_profit_group(user=DEFAULT_USER, group_name="快速止盈")
    remove_infrequent_funds_from_group(user=DEFAULT_USER, group_name="快速止盈")
    logger.info("同步加仓数据完成")
    
def create_period_index_investment(event, context):
    """创建指数型基金定投计划"""
    create_plan_by_group_for_index_funds(DEFAULT_USER, "指数基金组合", 200000.0, 10000.0)
    pass

def dissolve_period_index_investment(event, context):
    """解散指数型基金定投计划"""
    dissolve_plan_by_group_for_index_funds(DEFAULT_USER, "指数基金组合")
    pass

def fixed_ratio_redeem(event, context):
    try:
        evt, payload = parse_fc_event(event)
        
        account = payload.get('account')
        password = payload.get('password')
        extra = {"account": account, "action": "fixed_ratio_redeem"}
        
        if not all([account, password]):
            logger.error("Payload缺少必填参数: account, password")
            return

        # 获取用户对象
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return

        logger.info(f"开始执行固定比率止盈，用户：{user.customer_name}", extra=extra)
        
        process_fixed_ratio_redeem(user, payload)
        
        logger.info(f"用户 {user.customer_name} 固定比率止盈执行完成", extra=extra)

    except Exception as e:
        logger.error(f"执行固定比率止盈时发生异常: {e}", extra={"action": "fixed_ratio_redeem"})
