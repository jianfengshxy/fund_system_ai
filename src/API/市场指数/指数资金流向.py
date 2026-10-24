"""
兼容旧版"指数资金流向"接口名。

历史上业务层通过 `get_index_money_flow` 获取指数资金热度序列，
后来底层实现迁移到 `指数资金热度与价格走势.py`，返回结构改成了
`IndexPriceFlowResponse`。为避免老脚本批量失效，这里提供一个薄包装：

- 继续暴露 `get_index_money_flow(user, index_code, range_type)`
- 返回旧代码可直接消费的 `list[dict]`
"""

from __future__ import annotations

import os
import sys
from typing import Any


if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.domain.user.User import User
from src.API.市场指数.指数资金热度与价格走势 import get_index_price_flow


logger = get_logger("IndexMoneyFlowCompat")


def get_index_money_flow(user: User, index_code: str, range_type: str = "n") -> list[dict[str, Any]]:
    """
    兼容旧版接口：返回资金热度/价格序列的字典列表。

    Args:
        user: User 对象
        index_code: 指数代码
        range_type: 时间范围，默认近 1 年

    Returns:
        list[dict]: 每条包含 PDATE / PERCENTPRICE / CHGRT / XLFLOW_SCORE
    """
    resp = get_index_price_flow(user, index_code=index_code, range_type=range_type)
    if not resp.success or not resp.items:
        logger.warning(f"获取指数资金流向兼容数据失败: index_code={index_code}, error={resp.first_error}")
        return []

    return [
        {
            "PDATE": item.PDATE,
            "PERCENTPRICE": item.PERCENTPRICE,
            "CHGRT": item.CHGRT,
            "XLFLOW_SCORE": item.XLFLOW_SCORE,
        }
        for item in resp.items
    ]

