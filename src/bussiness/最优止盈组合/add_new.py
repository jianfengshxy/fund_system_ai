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
from src.service.加仓风向标组合算法.加仓风向标新增 import add_new_funds as service_add_new_funds
# 配置日志
logger = get_logger(__name__)

#第一列：手机号 account
# 第二列：密码 password
# 第三列：支付密码
# 第四列：姓名
# 第五列：sub_account_name组合名称
# 第六列：budget 预算
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

def add_new_funds(user: User, sub_account_name: str = "最优止盈", total_budget: float = 10000.0, amount: Optional[float] = None, fund_type: str = 'all', fund_num: int = 1, spread_days: int = 5) -> bool:
    """
    新增基金（最小集成落地版）：
    - fund_num: 本次最多买入的基金只数（默认1）
    - spread_days: 将total_budget按交易天数摊薄（默认20），仅在未显式传入amount时生效
    """
    extra = {"account": getattr(user,'mobile_phone',None) or getattr(user,'account',None), "sub_account_name": sub_account_name, "action": "optimal_add_new", "fund_num": fund_num, "spread_days": spread_days}
    logger.info(f"开始为用户 {user.customer_name} 执行新增基金操作，总预算：{total_budget}元，fund_num={fund_num}, spread_days={spread_days}", extra=extra)

    # 透传参数到服务层
    success = service_add_new_funds(user, sub_account_name, total_budget, amount, fund_type, fund_num, spread_days)

    if success:
        logger.info(f"用户 {user.customer_name} 新增基金操作成功", extra=extra)
    else:
        logger.error(f"用户 {user.customer_name} 新增基金操作失败", extra=extra)
    return success

if __name__ == "__main__":
    # 测试 amount 不传的情况
    try:
        success = add_new_funds(DEFAULT_USER, "飞龙在天", 1000000.0,fund_type='non_index')  # amount 不传，使用 None
        if success:
            logging.info("测试成功（amount 未传）")
        else:
            logging.info("测试失败（amount 未传）")
    except Exception as e:
        logging.error(f"测试用户处理失败：{str(e)}")
