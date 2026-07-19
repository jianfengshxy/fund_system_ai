import logging
import sys
from pathlib import Path
from typing import Optional

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[3]
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

from src.common.constant import DEFAULT_USER
from src.common.logger import get_logger
from src.domain.user.User import User
from src.service.用户管理.用户信息 import get_user_all_info
from src.service.定投管理.定投查询.定投查询 import get_portfolio_plan_details
from src.service.见龙在田算法.见龙在田加仓 import increase_funds as jianlong_increase_funds

logger = get_logger(__name__)

#第一列：手机号 account
# 第二列：密码 password
# 第三列：支付密码
# 第四列：姓名
# 第五列：sub_account_name组合名称
# 第六列：预算 预算
user_list = [
    ("13918797997","Zj951103","Zj951103","仇晓钰","最优止盈",300000.0),
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



def increase_all_users():
    # 遍历用户列表  
    for user_info in user_list:
        account = user_info[0]
        password = user_info[1]
        pay_password = user_info[2]
        name = user_info[3]
        sub_account_name = user_info[4]
        budget = user_info[5]
        
        try:
            user = get_user_all_info(account, password)
            if not user:
                logger.error(f"获取用户 {name} 信息失败")
                continue
            user.budget = budget
            logger.info(f"开始加仓用户：{user.customer_name}")
            # 执行加仓操作
            increase(user, sub_account_name)
            logger.info(f"用户：{user.customer_name} 加仓完成")
            logger.info(f"用户：{user.customer_name} 开始对定投处理")
            # 调整：获取指定组合下的所有定投计划详情并执行全局 increase
            from src.bussiness.全局智能定投处理.increase import increase as global_increase  # 导入全局 increase 函数并起别名
            
            all_plan_details = get_portfolio_plan_details(user)  # 获取所有组合定投计划详情
            plan_details = []
            for detail in all_plan_details:
                if detail.rationPlan and detail.rationPlan.subAccountName == sub_account_name:
                    plan_details.append(detail)
            if plan_details:
                for plan_detail in plan_details:
                    global_increase(user, plan_detail)  # 调用全局的 increase 函数
                logger.info(f"用户：{user.customer_name} 全局智能定投加仓处理完成")
            else:
                logger.warning(f"用户：{user.customer_name} 无定投计划详情")
            logger.info(f"用户：{user.customer_name} 定投处理完成")
        except Exception as e:
            logger.error(f"处理用户 {name} 失败，错误信息：{str(e)}")

# 加仓算法实现

def increase(user: User, sub_account_name: str, total_budget: Optional[float] = None, amount: Optional[float] = None, fund_type: str = 'all', fund_num: int = 5, spread_days: int = 20) -> bool:
    """
    加仓（最小集成落地）：
    - fund_num: 本次最多下单次数（默认5）
    - spread_days: 预算摊薄天数（默认20）；仅未传入amount时生效
    """
    if total_budget is None:
        try:
            total_budget = float(getattr(user, 'budget', 0.0)) if getattr(user, 'budget', None) is not None else 0.0
        except Exception:
            total_budget = 0.0
        if not total_budget or total_budget <= 0:
            total_budget = 100000.0

    logger.info(f"开始为用户 {user.customer_name} 执行加仓（最小落地），组合: {sub_account_name}，预算: {total_budget}，amount: {amount}，fund_type: {fund_type}，fund_num={fund_num}，spread_days={spread_days}")
    # 改为调用 见龙在田算法 的加仓实现（服务层支持 fund_num 和 spread_days）
    success = jianlong_increase_funds(user, sub_account_name, total_budget, amount, fund_type, fund_num, spread_days)
    if success:
        logger.info(f"用户 {user.customer_name} 委托加仓成功")
    else:
        logger.error(f"用户 {user.customer_name} 委托加仓失败")
    return success

if __name__ == "__main__":
    # 测试 amount 不传的情况
    try:
        success = increase(DEFAULT_USER, "见龙在田", 1000000.0, fund_type='non_index')  # amount 不传，使用 None
        if success:
            logging.info("测试成功（amount 未传）")
        else:
            logging.info("测试失败（amount 未传）")
    except Exception as e:
        logging.error(f"测试用户处理失败：{str(e)}")
