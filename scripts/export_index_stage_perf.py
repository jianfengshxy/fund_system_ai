"""
遍历 market_index_static 所有指数，输出阶段涨幅（正收益概率 & 平均收益率）到 CSV。
只输出宽基指数、行业指数、主题指数、海外指数。
"""
import csv
import os
import sys
import time
from datetime import date

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ExportIndexStagePerf")

from src.db.database_connection import DatabaseConnection
from src.common.constant import DEFAULT_USER
from src.API.登录接口.login import ensure_user_fresh
from src.API.市场指数.指数阶段指标 import get_fund_index_stage_performance

# CSV 输出路径（带日期后缀）
REPORT_DIR = os.path.join(root_dir, "reports")
os.makedirs(REPORT_DIR, exist_ok=True)
today_str = date.today().strftime("%Y%m%d")
CSV_PATH = os.path.join(REPORT_DIR, f"指数阶段涨幅_{today_str}.csv")

# 只导出这四类指数（DB 中存储为简称）
TARGET_TYPES = ["宽基", "行业", "主题", "海外"]

# 目标周期：字段后缀 & CSV 列名
PERIODS = [
    ("持有3个月", "Q"),
    ("持有6个月", "HY"),
    ("持有1年", "Y"),
    ("持有3年", "TRY"),
]


def _is_valid(val) -> bool:
    """判断 API 返回的值是否有效（排除 None / 空 / "--"）"""
    if val is None:
        return False
    s = str(val).strip()
    return s not in ("", "--", "None")


def _to_float(val) -> float:
    """安全转浮点，无效值返回 -inf（排在末尾）"""
    try:
        return float(val)
    except (ValueError, TypeError):
        return float("-inf")


def has_valid_data(data: dict) -> bool:
    """所有周期的正收益概率和平均收益率都必须有有效值"""
    for _, suffix in PERIODS:
        if not _is_valid(data.get(f"PROFIT_RATE_{suffix}")):
            return False
        if not _is_valid(data.get(f"AVGSYL_{suffix}")):
            return False
    return True


def main():
    # 1. 登录
    logger.info("登录刷新用户 token...")
    user = ensure_user_fresh(DEFAULT_USER)

    # 2. 查询目标类型指数（含跟踪基金信息）
    placeholders = ",".join(["%s"] * len(TARGET_TYPES))
    db = DatabaseConnection()
    rows = db.execute_query(
        f"SELECT index_code, index_name, track_fund_code, track_fund_name "
        f"FROM market_index_static "
        f"WHERE type_name IN ({placeholders}) ORDER BY type_name, index_code",
        TARGET_TYPES,
    )
    logger.info(f"共读取 {len(rows)} 个指数（类型: {TARGET_TYPES}）")

    # 3. 遍历获取阶段指标
    results = []
    skipped_no_data = 0
    for i, r in enumerate(rows, 1):
        code = r["index_code"]
        name = r["index_name"]

        logger.info(f"[{i}/{len(rows)}] {code} {name}")
        try:
            data = get_fund_index_stage_performance(user, index_code=code)
            if not data or not has_valid_data(data):
                skipped_no_data += 1
                continue

            row = {
                "index_code": code,
                "index_name": name,
                "跟踪基金代码": r["track_fund_code"] or "",
                "跟踪基金名称": r["track_fund_name"] or "",
            }
            for label, suffix in PERIODS:
                profit_key = f"PROFIT_RATE_{suffix}"
                avgsyl_key = f"AVGSYL_{suffix}"
                row[f"{label}正收益概率"] = data.get(profit_key, "")
                row[f"{label}平均收益率"] = data.get(avgsyl_key, "")
            results.append(row)
        except Exception as e:
            logger.error(f"  -> 异常: {e}")
            skipped_no_data += 1

        time.sleep(0.3)

    # 4. 按持有3个月平均收益率降序排序
    results.sort(key=lambda x: _to_float(x.get("持有3个月平均收益率", "")), reverse=True)

    # 5. 写入 CSV
    fieldnames = ["index_code", "index_name", "跟踪基金代码", "跟踪基金名称"]
    for label, _ in PERIODS:
        fieldnames.append(f"{label}正收益概率")
        fieldnames.append(f"{label}平均收益率")

    with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(results)

    logger.info(f"写入完成: {CSV_PATH} ({len(results)} 条, 跳过 {skipped_no_data} 条无数据指数)")


if __name__ == "__main__":
    main()
