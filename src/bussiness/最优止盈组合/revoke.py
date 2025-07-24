import logging
import os
import sys

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.domain.user.User import User
from src.common.constant import DEFAULT_USER
from src.service.用户管理.用户信息 import get_user_all_info
from src.service.交易管理.交易查询 import get_withdrawable_trades
from src.API.交易管理.revokMrg import revoke_order
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 用户列表，与参考文件相同
user_list = [
    ("13918797997","Zj951103","Zj951103","仇晓钰","最优止盈",1000000.0),
    ("13820198186", "tang8186","tang8186","唐祖华","最优止盈",450000.0),
    ("17782571152", "s00127479","s00127479","邵科","最优止盈",150000.0),
    ("13851562586", "muyi0628","muyi0628","铁宏安","最优止盈",30000.0),
    ("13910680799", "fuliang223147","fuliang223147","梁红兵","最优止盈",40000.0),
    ("13974549306", "huigengsi937367","huigengsi937367","朱沅罗尘","最优止盈",50000.0),
    ("13977796363", "tang6363","tang6363","唐显扬","最优止盈",400000.0),
    ("15373193078", "sy811123","sy811123","张莹莹","最优止盈",50000.0),
    ("15936530625", "wch601249697","wch601249697","王长海","最优止盈",50000.0),
    ("18648900788", "ldw88888","ldw88888","李代文","最优止盈",50000.0),
    ("13426206037", "fuyj223147","fuyj223147","付一军","最优止盈",50000.0),
    ("13500819290", "guojing1985","guojing1985","郭婧","最优止盈",200000.0),
    ("13562500306", "lilin926","lilin926","刘文杰","最优止盈",60000.0),
    ("13571973393", "wj121109","wj121109","安城","最优止盈",500000.0),
    ("13584903800", "hu123321","hu123321","胡春红","最优止盈",300000.0),
    ("13817533699", "demone40","demone40","东岳亮","最优止盈",150000.0)
]

def revoke_all_users():
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
            logger.info(f"开始撤回用户：{user.customer_name} 的交易")
            # 执行撤回操作
            revoke(user, sub_account_name)
            logger.info(f"用户：{user.customer_name} 撤回完成")
        except Exception as e:
            logger.error(f"处理用户 {name} 失败，错误信息：{str(e)}")
            continue

def revoke(user: User, sub_account_name: str = "最优止盈") -> bool:
    """撤回算法实现：
    1. 获取组合账号
    2. 查询可撤回交易
    3. 遍历每个可撤回交易并执行撤回
    Args:
        user: 用户对象
        sub_account_name: 组合名称
    Returns:
        bool: 是否成功
    """
    customer_name = user.customer_name
    # 根据组合名称获取组合账号
    sub_account_no = getSubAccountNoByName(user, sub_account_name)
    if not sub_account_no:
        logger.error(f"未找到组合 {sub_account_name} 的账号")
        return False
    
    # 查询可撤回交易
    trades = get_withdrawable_trades(user, sub_account_no=sub_account_no)
    if not trades:
        logger.info(f"{customer_name} 在组合 {sub_account_name} 中没有可撤回交易")
        return True
    
    logger.info(f"{customer_name} 在组合 {sub_account_name} 中找到 {len(trades)} 个可撤回交易")
    
    success = True
    for trade in trades:
        try:
            result = revoke_order(
                user,
                trade.busin_serial_no,
                trade.business_type,
                trade.fund_code,
                trade.amount,
                sub_account_no=sub_account_no
            )
            if result['Success']:
                logger.info(f"成功撤回交易: {trade.busin_serial_no} (基金: {trade.fund_code})")
            else:
                logger.error(f"撤回交易 {trade.busin_serial_no} 失败: {result['Message']}")
                success = False
        except Exception as e:
            logger.error(f"撤回交易 {trade.busin_serial_no} 时异常: {str(e)}")
            success = False
    
    return success

if __name__ == "__main__":
    # 直接运行测试
    revoke_all_users()