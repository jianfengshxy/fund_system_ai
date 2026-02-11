import logging
import os
import sys
from typing import Optional, List

# 路径注入
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.domain.user.User import User

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def add_new(user: User, sub_account_name: str, fund_list: Optional[List[dict]] = None, total_budget: float = 0.0) -> bool:
    """
    业务层新增薄封装：委托到服务层自定义组合新增算法。
    - fund_list: 未持有的基金将直接按 amount 购买。
    """
    if not fund_list or not isinstance(fund_list, list):
        logger.info("[自定义组合·业务] 未提供 fund_list 或格式不正确，跳过新增")
        return False
    logger.info(f"[自定义组合·业务] 新增：用户={getattr(user, 'customer_name', 'unknown')}, 组合={sub_account_name}, 基金数={len(fund_list)}, 预算={total_budget}")
    try:
        # 注意：服务层函数名为 increase_funds（文件名为自定义组合新增.py）
        from src.service.自定义组合算法.自定义组合新增 import increase_funds as service_add_new_funds
        return service_add_new_funds(user, sub_account_name, fund_list, total_budget=total_budget)
    except Exception as e:
        logger.error(f"[自定义组合·业务] 新增委托失败: {e}")
        return False

if __name__ == "__main__":
    try:
        from src.common.constant import DEFAULT_USER
        add_new(
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
        logging.info(f"用户 {DEFAULT_USER.customer_name} 新增操作完成")
    except Exception as e:
        logging.error(f"测试用户处理失败：{str(e)}")