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
from src.common.constant import DEFAULT_USER, DEFAULT_FUND_PLAN_DETAIL

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

# 新增：导入“见龙在田”业务层新增薄封装
from src.bussiness.见龙在田.add_new import add_new_funds as jianlong_add_new_biz

# 初始化日志记录器
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def redeem(event, context):
    try:
        evt, payload = parse_fc_event(event)

        # 提取参数（与 add_new/increase 的风格保持一致）
        account = payload.get('account')
        password = payload.get('password')
        sub_account_name = payload.get('sub_account_name')
        total_budget = payload.get('total_budget')

        # 校验
        if not all([account, password, sub_account_name]):
            logger.error("Payload缺少必填参数: account, password, sub_account_name")
            return

        # 获取用户对象
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return

        logger.info(f"开始为用户 {user.customer_name} 执行止盈操作，组合：{sub_account_name}，预算：{total_budget}")

        # 委托业务层薄封装
        success = redeem_biz(user, sub_account_name, total_budget)

        if success:
            logger.info(f"用户 {user.customer_name} 止盈操作成功")
        else:
            logger.error(f"用户 {user.customer_name} 止盈操作失败")

    except Exception as e:
        logger.error(f"执行止盈时发生异常: {e}")

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

        # 校验
        if not all([account, password, sub_account_name,total_budget]):
            logger.error("Payload缺少必填参数: account, password, sub_account_name 或 total_budget")
            return

        # 获取用户对象
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")

        logger.info(f"开始为用户 {user.customer_name} 执行加仓操作，组合：{sub_account_name}，预算：{total_budget}，amount：{amount}，fund_type：{fund_type}")

        # 业务调用（与 add_new 的调用风格一致）
        success = increase_biz(user, sub_account_name, total_budget, amount, fund_type)

        if success:
            logger.info(f"用户 {user.customer_name} 加仓操作成功")
        else:
            logger.error(f"用户 {user.customer_name} 加仓操作失败")

    except Exception as e:
        logger.error(f"执行加仓时发生异常: {e}")

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

        # 校验
        if not all([account, password, sub_account_name, total_budget]):
            logger.error("Payload缺少必填参数: account, password, sub_account_name 或 total_budget")
            return

        # 获取用户对象
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return

        logger.info(f"开始为用户 {user.customer_name} 执行新增基金操作")

        # 业务调用（改为与 add_new 一致的参数风格）
        success = add_new_biz(user, sub_account_name, total_budget, amount, fund_type)

    except Exception as e:
        logger.error(f"add_new 函数执行错误: {str(e)}")
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

        # 校验
        if not all([account, password, sub_account_name, total_budget]):
            logger.error("Payload缺少必填参数: account, password, sub_account_name 或 total_budget")
            return

        # 获取用户对象
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return

        logger.info(f"[见龙在田] 开始为用户 {user.customer_name} 执行新增基金操作，组合：{sub_account_name}，预算：{total_budget}，amount：{amount}，fund_type：{fund_type}，fund_num：{fund_num}，spread_days：{spread_days}")

        # 业务调用（见龙在田的新增）
        success = jianlong_add_new_biz(user, sub_account_name, total_budget, amount, fund_type, fund_num, spread_days)

        if success:
            logger.info(f"[见龙在田] 用户 {user.customer_name} 新增基金操作成功")
        else:
            logger.error(f"[见龙在田] 用户 {user.customer_name} 新增基金操作失败")

    except Exception as e:
        logger.error(f"add_new_jianlong 函数执行错误: {str(e)}")
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

        # 校验
        if not all([account, password, sub_account_name, total_budget]):
            logger.error("Payload缺少必填参数: account, password, sub_account_name 或 total_budget")
            return

        # 获取用户对象
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return

        logger.info(f"[见龙在田] 开始为用户 {user.customer_name} 执行加仓操作，组合：{sub_account_name}，预算：{total_budget}，amount：{amount}，fund_type：{fund_type}，fund_num：{fund_num}，spread_days：{spread_days}")

        # 业务调用（见龙在田的加仓）
        # 导入见龙在田的加仓业务逻辑
        from src.bussiness.见龙在田.increase import increase as jianlong_increase_biz
        success = jianlong_increase_biz(user, sub_account_name, total_budget, amount, fund_type, fund_num, spread_days)

        if success:
            logger.info(f"[见龙在田] 用户 {user.customer_name} 加仓操作成功")
        else:
            logger.error(f"[见龙在田] 用户 {user.customer_name} 加仓操作失败")

    except Exception as e:
        logger.error(f"increase_jianlong 函数执行错误: {str(e)}")
        return

def increase_all_fund_plans(event, context):
    """为所有基金定投计划执行加仓"""
    increase_all_fund_plans_biz(DEFAULT_USER)
    pass

def redeem_all_fund_plans(event, context):
    """为所有基金定投计划执行止盈"""
    redeem_all_fund_plans_biz(DEFAULT_USER)
    pass

def sync_fund_investment_indicators(event, context):
    save_fund_investment_indicators(DEFAULT_USER)
    logger.info("同步加仓数据完成")

def create_period_index_investment(event, context):
    """创建指数型基金定投计划"""
    create_plan_by_group_for_index_funds(DEFAULT_USER, "指数基金组合", 200000.0, 10000.0)
    pass

def dissolve_period_index_investment(event, context):
    """解散指数型基金定投计划"""
    dissolve_plan_by_group_for_index_funds(DEFAULT_USER, "指数基金组合", 1000000.0)
    pass

def create_period_smart_investment(event, context):   
    # add_plan(DEFAULT_USER, 3000)
    create_plan_by_group(DEFAULT_USER,"飞龙在天",1000000.0,50000.0)
    pass

def dissolve_period_smart_investment(event, context):          
    # dissolve_daily_plan(DEFAULT_USER)
    dissolve_plan_by_group(DEFAULT_USER,"飞龙在天",1000000.0)
    pass

def redeem_jianlong(event, context):
    try:
        evt, payload = parse_fc_event(event)

        # 提取参数（与 add_new_jianlong/increase_jianlong 对齐）
        account = payload.get('account')
        password = payload.get('password')
        sub_account_name = payload.get('sub_account_name')
        total_budget = payload.get('total_budget')
        # 新增：可选止盈阈值（未传或格式异常时默认 20）
        profit_threshold = payload.get('profit_threshold')
        try:
            profit_threshold = float(profit_threshold) if profit_threshold is not None else 20.0
        except Exception:
            profit_threshold = 20.0

        # 校验（保持原有：阈值为可选，不纳入必填校验）
        if not all([account, password, sub_account_name, total_budget]):
            logger.error("Payload缺少必填参数: account, password, sub_account_name 或 total_budget")
            return

        # 获取用户对象
        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return

        logger.info(f"[见龙在田] 开始为用户 {user.customer_name} 执行止盈操作，组合：{sub_account_name}，预算：{total_budget}，止盈阈值：{profit_threshold}%")

        # 业务调用（见龙在田的止盈）
        from src.bussiness.见龙在田.redeem import redeem as jianlong_redeem_biz
        try:
            tb = float(total_budget)
        except Exception:
            tb = 100000.0
        success = jianlong_redeem_biz(user, sub_account_name, tb, profit_threshold)
        if success:
            logger.info(f"[见龙在田] 用户 {user.customer_name} 止盈操作完成")
        else:
            logger.error(f"[见龙在田] 用户 {user.customer_name} 止盈操作失败")
        return
    except Exception as e:
        logger.error(f"[见龙在田] 止盈入口异常：{e}")
        return

def add_new_custom(event, context):
    try:
        evt, payload = parse_fc_event(event)

        account = payload.get('account')
        password = payload.get('password')
        sub_account_name = payload.get('sub_account_name')
        fund_list = payload.get('fund_list')

        if not all([account, password, sub_account_name, fund_list]):
            logger.error("Payload缺少必填参数: account, password, sub_account_name 或 fund_list")
            return

        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return

        logger.info(f"[自定义组合-新增] 开始为用户 {user.customer_name} 执行新增，组合：{sub_account_name}，基金数：{len(fund_list)}")

        from src.service.自定义组合算法.自定义组合新增 import increase_funds as add_new_service
        success = add_new_service(user, sub_account_name, fund_list)

        if success:
            logger.info(f"[自定义组合-新增] 用户 {user.customer_name} 新增完成")
        else:
            logger.error(f"[自定义组合-新增] 用户 {user.customer_name} 新增失败")
    except Exception as e:
        logger.error(f"[自定义组合-新增] 入口异常：{e}")

def increase_custom(event, context):
    try:
        evt, payload = parse_fc_event(event)

        account = payload.get('account')
        password = payload.get('password')
        sub_account_name = payload.get('sub_account_name')
        fund_list = payload.get('fund_list')

        if not all([account, password, sub_account_name, fund_list]):
            logger.error("Payload缺少必填参数: account, password, sub_account_name 或 fund_list")
            return

        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return

        logger.info(f"[自定义组合-加仓] 开始为用户 {user.customer_name} 执行加仓，组合：{sub_account_name}，基金数：{len(fund_list)}")

        from src.service.自定义组合算法.自定义组合加仓 import increase_funds as increase_service
        success = increase_service(user, sub_account_name, fund_list)

        if success:
            logger.info(f"[自定义组合-加仓] 用户 {user.customer_name} 加仓完成")
        else:
            logger.error(f"[自定义组合-加仓] 用户 {user.customer_name} 加仓失败")
    except Exception as e:
        logger.error(f"[自定义组合-加仓] 入口异常：{e}")

def redeem_custom(event, context):
    try:
        evt, payload = parse_fc_event(event)

        account = payload.get('account')
        password = payload.get('password')
        sub_account_name = payload.get('sub_account_name')
        fund_list = payload.get('fund_list')

        if not all([account, password, sub_account_name, fund_list]):
            logger.error("Payload缺少必填参数: account, password, sub_account_name 或 fund_list")
            return

        user = get_user_all_info(account, password)
        if not user:
            logger.error(f"获取用户 {account} 信息失败")
            return

        logger.info(f"[自定义组合-止盈] 开始为用户 {user.customer_name} 执行止盈，组合：{sub_account_name}，基金数：{len(fund_list)}")

        from src.service.自定义组合算法.自定义组合止盈 import redeem_funds as redeem_service
        success = redeem_service(user, sub_account_name, fund_list)

        if success:
            logger.info(f"[自定义组合-止盈] 用户 {user.customer_name} 止盈完成")
        else:
            logger.error(f"[自定义组合-止盈] 用户 {user.customer_name} 止盈失败")
    except Exception as e:
        logger.error(f"[自定义组合-止盈] 入口异常：{e}")

if __name__ == "__main__":
    # 自定义组合入口的本地测试 payload（与服务层示例一致）
    payload = {
        "account": "13918199137",
        "password": "sWX15706",
        "sub_account_name": "海外基金组合",
        "fund_list": [
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
    }
    # parse_fc_event 支持 dict 或 {"payload": "..."}；此处用 JSON 字符串更贴近 FC 触发
    event = {"payload": json.dumps(payload)}

    # 选择调用新增/加仓/止盈中的一个（示例调用新增）
    # add_new_custom(event, None)
    # increase_custom(event, None)
    # redeem_custom(event, None)
    # 根据需要调用 redeem 或 increase 函数
    # sync_fund_investment_indicators(None, None)
    increase_all_fund_plans(None, None)
    # redeem_all_fund_plans(None, None)
    # increase(None, None)
    # redeem(None, None)
    # create_period_smart_investment(None, None)
    # dissolve_period_smart_investment(None, None)
    # create_period_smart_investment(None, None)
    pass
