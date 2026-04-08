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

# 新增：导入见龙在田止盈、自定义组合相关业务函数
from src.bussiness.见龙在田.redeem import redeem as jianlong_redeem_biz
from src.bussiness.自定义组合.add_new import add_new as custom_add_new_biz
from src.bussiness.自定义组合.increase import increase as custom_increase_biz
from src.bussiness.自定义组合.redeem import redeem as custom_redeem_biz
# 新增：黄金多利组合业务函数
from src.bussiness.黄金多利组合.increase import increase as gold_increase_biz
from src.bussiness.黄金多利组合.redeem import redeem as gold_redeem_biz
# 新增：黄金异次元组合业务函数
from src.bussiness.黄金异次元.increase import increase as gold_dimension_increase_biz
from src.bussiness.黄金异次元.redeem import redeem as gold_dimension_redeem_biz
# 同步用户资产数据
from src.service.数据同步.sync_user_asset import sync_user_daily_asset
from src.service.数据同步.sync_user_trade import sync_user_weekly_trades
from src.service.数据同步.sync_sub_account_asset import sync_sub_account_daily_asset
from src.service.数据同步.sync_sub_account_fund_asset import sync_sub_account_fund_asset_daily
from src.service.数据同步.sync_total_account_fund_asset import sync_total_account_fund_asset_daily
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
    try:
        sync_user_daily_asset(DEFAULT_USER)
        sync_user_weekly_trades(DEFAULT_USER)
        sync_sub_account_daily_asset(DEFAULT_USER)
        sync_sub_account_fund_asset_daily(DEFAULT_USER)
        sync_total_account_fund_asset_daily(DEFAULT_USER)
    except Exception as e:
        logger.error(f"同步用户资产数据失败: {e}")
        
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

def redeem_jianlong(event, context):
    try:
        evt, payload = parse_fc_event(event)
        account = payload.get('account')
        password = payload.get('password')
        sub_account_name = payload.get('sub_account_name')
        total_budget = payload.get('total_budget')
        extra = {"account": account, "sub_account_name": sub_account_name, "action": "jianlong_redeem"}
        
        if not all([account, password, sub_account_name]):
             logger.error("Payload缺少必填参数")
             return

        user = get_user_all_info(account, password)
        if not user:
             logger.error(f"获取用户 {account} 信息失败")
             return

        logger.info(f"[见龙在田] 开始执行止盈...", extra=extra)
        success = jianlong_redeem_biz(user, sub_account_name, total_budget)
        if success:
             logger.info(f"[见龙在田] 止盈成功", extra=extra)
        else:
             logger.error(f"[见龙在田] 止盈失败", extra=extra)

    except Exception as e:
        logger.error(f"redeem_jianlong 异常: {e}", extra={"action": "jianlong_redeem"})

def add_new_custom(event, context):
    try:
        evt, payload = parse_fc_event(event)
        account = payload.get('account')
        password = payload.get('password')
        
        if not all([account, password]):
            logger.error("Payload缺少必填参数: account, password")
            return
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return
        from src.service.自选基金.自选组合服务 import get_all_group_names, get_group_funds_by_name
        from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name
        from src.bussiness.自定义组合.add_new import add_new as biz_add_new
        from src.API.组合管理.SubAccountMrg import getSubAssetMultList
        # 先拿到用户所有自选组合名字
        all_favorite_groups = get_all_group_names(user)
        if not all_favorite_groups:
            logger.warning("该用户下无任何自选组合，直接返回")
            return
        favorite_set = {g for g in all_favorite_groups}
        # 获取用户所有资产组合
        sub_asset_response = getSubAssetMultList(user)
        if not sub_asset_response.Success or not sub_asset_response.Data:
            logger.warning("获取用户资产组合列表失败或为空")
            return
        # 解析 sub_account_list，构建配置映射
        sub_account_list = payload.get('sub_account_list', [])
        sub_account_config = {}
        if isinstance(sub_account_list, list):
            for item in sub_account_list:
                name = item.get('sub_account_name')
                if name:
                    sub_account_config[name] = {
                        "amount": item.get('amount'),
                        "total_budget": item.get('total_budget', 100000.0)
                    }

        for group in sub_asset_response.Data.list_group:
            sub_account_name = group.group_name
            extra = {"account": account, "sub_account_name": sub_account_name, "action": "custom_add_new"}
            if not sub_account_name:
                continue
            # 只在自选组合名集合里才继续
            if sub_account_name not in favorite_set:
                continue
            
            # 确定 amount 和 total_budget
            amount_val = 10000.0
            total_budget_val = 0.0
            
            if sub_account_name in sub_account_config:
                cfg = sub_account_config.get(sub_account_name)
                # amount
                cfg_amt = cfg.get("amount")
                if cfg_amt is not None:
                    try:
                        amount_val = float(cfg_amt)
                    except (ValueError, TypeError):
                        pass
                # total_budget
                cfg_budget = cfg.get("total_budget")
                if cfg_budget is not None:
                    try:
                        total_budget_val = float(cfg_budget)
                    except (ValueError, TypeError):
                        pass

            logger.info(f"组合 {sub_account_name} 准备新增，使用金额: {amount_val}，预算限制: {total_budget_val}", extra=extra)

            assets = get_sub_account_asset_by_name(user, sub_account_name)
            if not assets:
                logger.warning(f"资产组合未找到详细资产信息，跳过：{sub_account_name}", extra=extra)
                continue
            funds = get_group_funds_by_name(sub_account_name, user)
            if not funds:
                logger.warning(f"自选组合基金为空，跳过：{sub_account_name}", extra=extra)
                continue
            fund_list = []
            for item in funds:
                code = item.get("fcode") or item.get("FundCode") or item.get("fund_code") or item.get("FCODE") or item.get("code")
                name_val = item.get("shortname") or item.get("fname") or item.get("FundName") or item.get("fund_name") or item.get("name")
                if not code:
                    continue
                fund_list.append({"fund_code": code, "fund_name": name_val, "amount": amount_val})
            logger.info(f"[自定义组合-新增] 开始为用户 {user.customer_name} 执行新增，组合：{sub_account_name}，基金数：{len(fund_list)}", extra=extra)
            success = biz_add_new(user, sub_account_name, fund_list, total_budget=total_budget_val)
            if success:
                logger.info(f"[自定义组合-新增] 用户 {user.customer_name} 新增完成：{sub_account_name}", extra=extra)
            else:
                logger.info(f"[自定义组合-新增] 无新增交易或候选未达条件（非失败）：{sub_account_name}", extra=extra)
    except RetriableError as e:
        logger.warning(f"[自定义组合-新增] 异常可重试：{e}", extra={"action": "custom_add_new"})
    except ValidationError as e:
        logger.error(f"[自定义组合-新增] 异常参数错误：{e}", extra={"action": "custom_add_new"})
    except NonRetriableError as e:
        logger.error(f"[自定义组合-新增] 异常不可重试：{e}", extra={"action": "custom_add_new"})
    except Exception as e:
        logger.error(f"[自定义组合-新增] 入口异常：{e}", extra={"action": "custom_add_new"})

def increase_custom(event, context):
    try:
        evt, payload = parse_fc_event(event)
        account = payload.get('account')
        password = payload.get('password')
        if not all([account, password]):
            logger.error("Payload缺少必填参数: account, password")
            return
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return
        from src.service.自选基金.自选组合服务 import get_all_group_names, get_group_funds_by_name
        from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name
        from src.bussiness.自定义组合.increase import increase as biz_increase
        from src.API.组合管理.SubAccountMrg import getSubAssetMultList
        all_favorite_groups = get_all_group_names(user)
        if not all_favorite_groups:
            logger.warning("该用户下无任何自选组合，直接返回")
            return
        favorite_set = {g for g in all_favorite_groups}
        # 获取用户所有资产组合
        sub_asset_response = getSubAssetMultList(user)
        if not sub_asset_response.Success or not sub_asset_response.Data:
            logger.warning("获取用户资产组合列表失败或为空")
            return
        # 解析 sub_account_list，构建 amount 映射
        sub_account_list = payload.get('sub_account_list', [])
        sub_account_config = {}
        if isinstance(sub_account_list, list):
            for item in sub_account_list:
                name = item.get('sub_account_name')
                amt = item.get('amount')
                if name:
                    sub_account_config[name] = amt

        for group in sub_asset_response.Data.list_group:
            sub_account_name = group.group_name
            extra = {"account": account, "sub_account_name": sub_account_name, "action": "custom_increase"}
            if not sub_account_name:
                continue
            if sub_account_name not in favorite_set:
                continue
            
            # 确定 amount: 优先使用 payload 中对应组合的 amount，否则使用默认值 10000.0
            amount_val = 10000.0
            if sub_account_name in sub_account_config:
                cfg_amt = sub_account_config.get(sub_account_name)
                if cfg_amt is not None:
                    try:
                        amount_val = float(cfg_amt)
                    except (ValueError, TypeError):
                        pass

            logger.info(f"组合 {sub_account_name} 准备加仓，使用金额: {amount_val}", extra=extra)

            assets = get_sub_account_asset_by_name(user, sub_account_name)
            if not assets:
                logger.warning(f"资产组合未找到详细资产信息，跳过：{sub_account_name}", extra=extra)
                continue
            funds = get_group_funds_by_name(sub_account_name, user)
            if not funds:
                logger.warning(f"自选组合基金为空，跳过：{sub_account_name}", extra=extra)
                continue
            fund_list = []
            for item in funds:
                code = item.get("fcode") or item.get("FundCode") or item.get("fund_code") or item.get("FCODE") or item.get("code")
                name_val = item.get("shortname") or item.get("fname") or item.get("FundName") or item.get("fund_name") or item.get("name")
                if not code:
                    continue
                fund_list.append({"fund_code": code, "fund_name": name_val, "amount": amount_val})
            logger.info(f"[自定义组合-加仓] 开始为用户 {user.customer_name} 执行加仓，组合：{sub_account_name}，基金数：{len(fund_list)}", extra=extra)
            success = biz_increase(user, sub_account_name, fund_list)
            if success:
                logger.info(f"[自定义组合-加仓] 用户 {user.customer_name} 加仓完成：{sub_account_name}", extra=extra)
            else:
                logger.info(f"[自定义组合-加仓] 无加仓交易或候选未达条件（非失败）：{sub_account_name}", extra=extra)
    except RetriableError as e:
        logger.warning(f"[自定义组合-加仓] 异常可重试：{e}", extra={"action": "custom_increase"})
    except ValidationError as e:
        logger.error(f"[自定义组合-加仓] 异常参数错误：{e}", extra={"action": "custom_increase"})
    except NonRetriableError as e:
        logger.error(f"[自定义组合-加仓] 异常不可重试：{e}", extra={"action": "custom_increase"})
    except Exception as e:
        logger.error(f"[自定义组合-加仓] 入口异常：{e}", extra={"action": "custom_increase"})
        

def redeem_custom(event, context):
    try:
        evt, payload = parse_fc_event(event)
        account = payload.get('account')
        password = payload.get('password')
        if not all([account, password]):
            logger.error("Payload缺少必填参数: account, password")
            return
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return
        from src.service.自选基金.自选组合服务 import get_all_group_names, get_group_funds_by_name
        from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name
        from src.bussiness.自定义组合.redeem import redeem as biz_redeem
        from src.API.组合管理.SubAccountMrg import getSubAssetMultList
        all_favorite_groups = get_all_group_names(user)
        if not all_favorite_groups:
            logger.warning("该用户下无任何自选组合，直接返回")
            return
        favorite_set = {g for g in all_favorite_groups}
        # 获取用户所有资产组合
        sub_asset_response = getSubAssetMultList(user)
        if not sub_asset_response.Success or not sub_asset_response.Data:
            logger.warning("获取用户资产组合列表失败或为空")
            return
        
        # 解析 sub_account_list，构建 amount 映射
        sub_account_list = payload.get('sub_account_list', [])
        sub_account_config = {}
        if isinstance(sub_account_list, list):
            for item in sub_account_list:
                name = item.get('sub_account_name')
                amt = item.get('amount')
                if name:
                    sub_account_config[name] = amt

        for group in sub_asset_response.Data.list_group:
            sub_account_name = group.group_name
            extra = {"account": account, "sub_account_name": sub_account_name, "action": "custom_redeem"}
            if not sub_account_name:
                continue
            if sub_account_name not in favorite_set:
                continue
            
            # 确定 amount: 优先使用 payload 中对应组合的 amount，否则使用默认值 10000.0
            amount_val = 10000.0
            if sub_account_name in sub_account_config:
                cfg_amt = sub_account_config.get(sub_account_name)
                if cfg_amt is not None:
                    try:
                        amount_val = float(cfg_amt)
                    except (ValueError, TypeError):
                        pass

            logger.info(f"组合 {sub_account_name} 准备止盈，使用金额: {amount_val}", extra=extra)

            fund_list = None
            funds = get_group_funds_by_name(sub_account_name, user)
            if funds:
                built_list = []
                for item in funds:
                    code = item.get("fcode") or item.get("FundCode") or item.get("fund_code") or item.get("FCODE") or item.get("code")
                    name_val = item.get("shortname") or item.get("fname") or item.get("FundName") or item.get("fund_name") or item.get("name")
                    if not code:
                        continue
                    built_list.append({"fund_code": code, "fund_name": name_val, "amount": amount_val})
                if built_list:
                    fund_list = built_list

            logger.info(
                f"[自定义组合-止盈] 开始为用户 {user.customer_name} 执行止盈，组合：{sub_account_name}，候选基金数：{len(fund_list) if fund_list else 0}",
                extra=extra,
            )
            success = biz_redeem(user, sub_account_name, fund_list)
            if success:
                logger.info(f"[自定义组合-止盈] 用户 {user.customer_name} 止盈完成：{sub_account_name}", extra=extra)
            else:
                logger.info(f"[自定义组合-止盈] 无止盈交易或候选未达条件（非失败）：{sub_account_name}", extra=extra)
    except RetriableError as e:
        logger.warning(f"[自定义组合-止盈] 异常可重试：{e}", extra={"action": "custom_redeem"})
    except ValidationError as e:
        logger.error(f"[自定义组合-止盈] 异常参数错误：{e}", extra={"action": "custom_redeem"})
    except NonRetriableError as e:
        logger.error(f"[自定义组合-止盈] 异常不可重试：{e}", extra={"action": "custom_redeem"})
    except Exception as e:
        logger.error(f"[自定义组合-止盈] 入口异常：{e}", extra={"action": "custom_redeem"})

def increase_gold_portfolio(event, context):
    try:
        evt, payload = parse_fc_event(event)
        account = payload.get('account')
        password = payload.get('password')
        sub_account_name = payload.get('sub_account_name')
        amount = payload.get('amount', 10000.0) # Default 10000.0 if not specified
        
        extra = {"account": account, "sub_account_name": sub_account_name, "action": "gold_increase"}
        
        if not all([account, password, sub_account_name]):
            logger.error("Payload缺少必填参数")
            return

        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return

        logger.info(f"[黄金多利组合] 开始执行加仓检查...", extra=extra)
        success = gold_increase_biz(user, sub_account_name, amount)
        if success:
            logger.info(f"[黄金多利组合] 加仓检查/执行成功", extra=extra)
        else:
            logger.info(f"[黄金多利组合] 未触发加仓或执行失败", extra=extra)

    except Exception as e:
        logger.error(f"increase_gold_portfolio 异常: {e}", extra={"action": "gold_increase"})

def redeem_gold_portfolio(event, context):
    try:
        evt, payload = parse_fc_event(event)
        account = payload.get('account')
        password = payload.get('password')
        sub_account_name = payload.get('sub_account_name')
        
        extra = {"account": account, "sub_account_name": sub_account_name, "action": "gold_redeem"}
        
        if not all([account, password, sub_account_name]):
            logger.error("Payload缺少必填参数")
            return

        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return

        logger.info(f"[黄金多利组合] 开始执行止盈检查...", extra=extra)
        success = gold_redeem_biz(user, sub_account_name)
        if success:
            logger.info(f"[黄金多利组合] 止盈检查/执行成功", extra=extra)
        else:
            logger.info(f"[黄金多利组合] 未触发止盈或执行失败", extra=extra)

    except Exception as e:
        logger.error(f"redeem_gold_portfolio 异常: {e}", extra={"action": "gold_redeem"})

def increase_gold_dimension_portfolio(event, context):
    try:
        evt, payload = parse_fc_event(event)
        account = payload.get('account')
        password = payload.get('password')
        sub_account_name = payload.get('sub_account_name')
        amount = payload.get('amount', 50000.0) # Default 50000.0 if not specified
        
        extra = {"account": account, "sub_account_name": sub_account_name, "action": "gold_dimension_increase"}
        
        if not all([account, password, sub_account_name]):
            logger.error("Payload缺少必填参数")
            return

        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return

        logger.info(f"[黄金异次元组合] 开始执行加仓检查...", extra=extra)
        success = gold_dimension_increase_biz(user, sub_account_name, amount)
        if success:
            logger.info(f"[黄金异次元组合] 加仓检查/执行成功", extra=extra)
        else:
            logger.info(f"[黄金异次元组合] 未触发加仓或执行失败", extra=extra)

    except Exception as e:
        logger.error(f"increase_gold_dimension_portfolio 异常: {e}", extra={"action": "gold_dimension_increase"})

def redeem_gold_dimension_portfolio(event, context):
    try:
        evt, payload = parse_fc_event(event)
        account = payload.get('account')
        password = payload.get('password')
        sub_account_name = payload.get('sub_account_name')
        
        extra = {"account": account, "sub_account_name": sub_account_name, "action": "gold_dimension_redeem"}
        
        if not all([account, password, sub_account_name]):
            logger.error("Payload缺少必填参数")
            return

        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return

        logger.info(f"[黄金异次元组合] 开始执行止盈检查...", extra=extra)
        success = gold_dimension_redeem_biz(user, sub_account_name)
        if success:
            logger.info(f"[黄金异次元组合] 止盈检查/执行成功", extra=extra)
        else:
            logger.info(f"[黄金异次元组合] 未触发止盈或执行失败", extra=extra)

    except Exception as e:
        logger.error(f"redeem_gold_dimension_portfolio 异常: {e}", extra={"action": "gold_dimension_redeem"})

if __name__ == "__main__":
    def invoke(func, payload_str, name):
        print(f"\n--- Invoking {name} ---")
        try:
            event = {"payload": payload_str}
            func(event, None)
        except Exception as e:
            print(f"Error invoking {name}: {e}")

    # 1. fixed_ratio_redeem
    p_fixed = '{"account": "13918199137", "password": "sWX15706", "fundcodelist": [{"fundcode":"021740","stoprate":"1.0"}]}'
    invoke(fixed_ratio_redeem, p_fixed, "fixed_ratio_redeem")

    # 2. add_new_jianlong
    # p_add_jianlong = '{"account": "13918199137","password": "sWX15706","sub_account_name": "见龙在田","total_budget": 1000000.0,"amount": 100000.0,"fund_type": "all"}'
    # invoke(add_new_jianlong, p_add_jianlong, "add_new_jianlong")

    # 3. add_new
    # p_add_new = '{"account": "13918199137","password": "sWX15706","sub_account_name": "飞龙在天","total_budget": 1000000.0,"fund_type": "non_index"}'
    # invoke(add_new, p_add_new, "add_new")

    # 4. increase_jianlong
    # p_inc_jianlong = '{"account": "13918199137","password": "sWX15706","sub_account_name": "见龙在田","total_budget": 1000000.0,"fund_type": "all"}'
    # invoke(increase_jianlong, p_inc_jianlong, "increase_jianlong")

    # 5. increase
    # p_increase = '{"account": "13918199137","password": "sWX15706","sub_account_name": "飞龙在天","total_budget": 1000000.0,"fund_type": "non_index"}'
    # invoke(increase, p_increase, "increase")
    
    # 6. redeem_jianlong
    # p_red_jianlong = '{"account": "13918199137","password": "sWX15706","sub_account_name": "见龙在田","total_budget":1000000.0}'
    # invoke(redeem_jianlong, p_red_jianlong, "redeem_jianlong")

    # 7. redeem
    # p_redeem = '{"account": "13918199137","password": "sWX15706","sub_account_name": "飞龙在天","total_budget":1000000.0}'
    # invoke(redeem, p_redeem, "redeem")

    # 8. Custom Portfolio
    p_custom = '{"account": "13918199137", "password": "sWX15706", "sub_account_list": [{"sub_account_name": "海外基金组合", "amount": 5000.0,"total_budget": 200000.0},{"sub_account_name": "快速止盈", "amount": 30000.0,"total_budget": 1000000.0}]}'
    # invoke(add_new_custom, p_custom, "add_new_custom")
    # invoke(increase_custom, p_custom, "increase_custom")
    # invoke(redeem_custom, p_custom, "redeem_custom")

    # 9. Daily Task
    # p_daily = '{"account": "13918199137","password": "sWX15706","sub_account_name": "飞龙在天","total_budget": 1000000.0,"fund_type": "non_index"}'
    # invoke(daily_task, p_daily, "daily_task")

    # 10. Batch Operations
    # invoke(increase_all_fund_plans, p_daily, "increase_all_fund_plans")
    # invoke(redeem_all_fund_plans, p_daily, "redeem_all_fund_plans")
