# -*- coding: utf-8 -*-
"""
市场指数数据服务
  - 负责从天天基金 API 获取指数数据并写入 MySQL
  - 静态属性 → market_index_static 表
  - 每日动态数据 → market_index_daily 表

使用方法:
  service = MarketIndexService()
  service.sync_all_indices(user)          # 拉取列表+手动注册重点指数
  service.sync_all_history_for_index(user, code)  # 拉取 PE/PB/价格/热度历史
  service.get_index_history(code, start, end)     # 查询历史数据供 AI 分析用
"""

import sys
import os

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import time
import logging
from typing import Optional, List, Dict

from src.common.logger import get_logger
from src.domain.user.User import User
from src.db.database_connection import DatabaseConnection

logger = get_logger(__name__)

# 重点关注的指数：即使不在市场指数列表 API 中也要手动注册
PRIORITY_INDICES: List[Dict] = [
    {
        "index_code": "399971", "index_name": "中证传媒",
        "full_index_name": "中证传媒指数",
        "type_name": "行业", "type_code": "001002",
        "sec_name": "传媒,通信", "sec_code": "BK000450",
        "maker_name": "中证指数", "index_type": "",
        "is_quot": "1", "is_use_pbp": "1", "rea_profile": "",
    },
    {
        "index_code": "970070", "index_name": "创业板人工智能",
        "full_index_name": "创业板人工智能指数",
        "type_name": "主题", "type_code": "001003",
        "sec_name": "人工智能", "sec_code": "BK000292",
        "maker_name": "深交所", "index_type": "",
        "is_quot": "1", "is_use_pbp": "1", "rea_profile": "",
    },
]


class MarketIndexService:
    """市场指数数据服务"""

    def __init__(self):
        self._db = DatabaseConnection()

    # ===================== 静态属性 =====================

    def sync_all_indices(self, user: User) -> int:
        """
        同步所有市场指数的静态属性到 market_index_static 表。
        1) 翻页拉取全部指数列表（每页 30 条，循环直到返回为空）
        2) 合并手动注册的重点指数
        使用 REPLACE INTO 批量写入。
        """
        from src.API.市场指数.获取市场指数 import get_market_index

        all_items = []
        page = 1
        while True:
            resp = get_market_index(user, type_code="0", page_index=page, page_size=30)
            if not resp.success or not resp.items:
                break
            for it in resp.items:
                all_items.append({
                    "index_code": it.INDEXCODE or "",
                    "index_name": it.INDEXNAME or "",
                    "full_index_name": it.FULLINDEXNAME or "",
                    "type_name": it.TYPE_NAME or "",
                    "type_code": it.TYPE_CODE or "",
                    "sec_name": it.SEC_NAME or "",
                    "sec_code": it.SEC_CODE or "",
                    "maker_name": it.MAKERNAME or "",
                    "index_type": it.INDEXTYPE or "",
                    "is_quot": str(it.ISQUOT or 0),
                    "is_use_pbp": str(it.ISUSEPBP or 0),
                    "rea_profile": it.REAPROFILE or "",
                })
            logger.info(f"静态属性翻页: page={page}, 本页 {len(resp.items)} 条, 累计 {len(all_items)} 条")
            if len(resp.items) < 30:
                break
            page += 1
            time.sleep(0.3)

        # 合并手动注册的重点指数
        existing_codes = {it["index_code"] for it in all_items}
        for pi in PRIORITY_INDICES:
            if pi["index_code"] not in existing_codes:
                all_items.append(pi)

        if not all_items:
            return 0

        sql = (
            "REPLACE INTO market_index_static ("
            "index_code, index_name, full_index_name, type_name, type_code, "
            "sec_name, sec_code, maker_name, index_type, "
            "is_quot, is_use_pbp, rea_profile"
            ") VALUES ("
            "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s"
            ")"
        )
        params = [(
            it["index_code"], it["index_name"], it["full_index_name"],
            it["type_name"], it["type_code"],
            it["sec_name"], it["sec_code"],
            it["maker_name"], it["index_type"],
            it["is_quot"], it["is_use_pbp"], it["rea_profile"],
        ) for it in all_items]

        self._db.insert_many(sql, params)
        logger.info(f"静态属性同步完成: {len(all_items)} 条")
        return len(all_items)

    # ===================== 每日动态数据（批量写入） =====================

    def sync_daily_valuation_batch(self, user: User, index_code: str,
                                   period: str = "10n") -> int:
        """
        批量拉取 PE-TTM / PB 历史估值并写入 market_index_daily。
        """
        from src.API.市场指数.指数估值走势 import get_index_valuation_trend

        # 合并 PETTM + PB 到日期字典
        merged: Dict[str, dict] = {}
        for key, resp in [
            ("PETTM", get_index_valuation_trend(user, index_code, "PETTM", period)),
        ]:
            if resp.success and resp.items:
                for it in resp.items:
                    if it.PDATE:
                        merged.setdefault(it.PDATE, {})["pe_ttm"] = it.PETTM
        time.sleep(0.2)

        for key, resp in [
            ("PB", get_index_valuation_trend(user, index_code, "PB", period)),
        ]:
            if resp.success and resp.items:
                for it in resp.items:
                    if it.PDATE:
                        merged.setdefault(it.PDATE, {})["pb"] = it.PB

        if not merged:
            return 0

        sql = (
            "INSERT INTO market_index_daily (index_code, trade_date, pe_ttm, pb) "
            "VALUES (%s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE "
            "pe_ttm = VALUES(pe_ttm), pb = VALUES(pb)"
        )
        params = [
            (index_code, date, vals.get("pe_ttm"), vals.get("pb"))
            for date, vals in sorted(merged.items())
        ]
        count = self._db.insert_many(sql, params)
        logger.info(f"[{index_code}] PE/PB 估值入库: {count} 条")
        return count

    def sync_daily_price_flow_batch(self, user: User, index_code: str,
                                    period: str = "3n") -> int:
        """
        批量拉取价格+资金热度历史数据。

        FundIndexPrice 接口返回的字段:
          PDATE, PERCENTPRICE, CHGRT, XLFLOW_SCORE
        """
        from src.API.市场指数.指数资金热度与价格走势 import get_index_price_flow

        resp = get_index_price_flow(user, index_code, period)
        if not resp.success or not resp.items:
            return 0

        sql = (
            "INSERT INTO market_index_daily ("
            "index_code, trade_date, price, change_pct, heat_score"
            ") VALUES (%s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE "
            "price = VALUES(price), change_pct = VALUES(change_pct), "
            "heat_score = VALUES(heat_score)"
        )
        params = []
        for it in resp.items:
            if not it.PDATE:
                continue
            params.append((
                index_code,
                it.PDATE,
                it.PERCENTPRICE,
                it.CHGRT,
                it.XLFLOW_SCORE,
            ))
        count = self._db.insert_many(sql, params) if params else 0
        logger.info(f"[{index_code}] 价格+热度入库: {count} 条")
        return count

    def fill_all_pe_pb_percentiles(self) -> dict:
        """
        对所有指数，基于已有 PE-TTM / PB 数据计算经验分位数，填入 pe_pct / pb_pct。

        使用 MySQL PERCENT_RANK() 窗口函数直接在数据库内计算，无需 Python 端
        批量传输数据。

        Returns:
            dict: {pe_updated_rows, pb_updated_rows}
        """
        # PE 分位
        pe_result = self._db.update(
            "UPDATE market_index_daily d "
            "JOIN ("
            "  SELECT id, PERCENT_RANK() OVER (PARTITION BY index_code ORDER BY pe_ttm) * 100 AS pct "
            "  FROM market_index_daily WHERE pe_ttm IS NOT NULL"
            ") c ON d.id = c.id "
            "SET d.pe_pct = ROUND(c.pct, 2)"
        )
        logger.info(f"PE 分位填充: {pe_result} 行")

        # PB 分位
        pb_result = self._db.update(
            "UPDATE market_index_daily d "
            "JOIN ("
            "  SELECT id, PERCENT_RANK() OVER (PARTITION BY index_code ORDER BY pb) * 100 AS pct "
            "  FROM market_index_daily WHERE pb IS NOT NULL"
            ") c ON d.id = c.id "
            "SET d.pb_pct = ROUND(c.pct, 2)"
        )
        logger.info(f"PB 分位填充: {pb_result} 行")

        return {"pe_updated": pe_result, "pb_updated": pb_result}

    def sync_all_history_for_index(self, user: User, index_code: str) -> dict:
        """
        对单个指数执行全部历史数据同步（估值 → 价格/热度）。

        PE/PB 分位数据（pe_pct / pb_pct）通过 fill_all_pe_pb_percentiles() 统一计算。
        """
        logger.info(f"=== 开始同步 [{index_code}] 全部历史数据 ===")
        r = {}
        r["valuation"] = self.sync_daily_valuation_batch(user, index_code, "10n")
        time.sleep(0.3)
        r["price_flow"] = self.sync_daily_price_flow_batch(user, index_code, "3n")
        logger.info(f"=== [{index_code}] 同步完成: {r} ===")
        return r

    def sync_all_indices_daily(self, user: User, limit: Optional[int] = None) -> dict:
        """
        同步 static 表中所有指数的每日历史数据。

        Args:
            user:  认证用户
            limit: 最多同步 N 个指数（None = 全部）

        Returns:
            dict: {total, synced, failed, details: [{code, name, valuation, price_flow}]}
        """
        static_indices = self._db.execute_query(
            "SELECT index_code, index_name FROM market_index_static ORDER BY index_code"
        )
        result = {"total": len(static_indices), "synced": 0, "failed": 0, "details": []}

        for idx in static_indices:
            if limit and result["synced"] + result["failed"] >= limit:
                break
            code = idx["index_code"]
            name = idx["index_name"]
            try:
                r = self.sync_all_history_for_index(user, code)
                result["synced"] += 1
                result["details"].append({"code": code, "name": name, **r})
                logger.info(f"[{code}] {name} 同步完成 ({result['synced']}/{result['total']})")
            except Exception as e:
                result["failed"] += 1
                logger.error(f"[{code}] {name} 同步失败: {e}")

        logger.info(f"全量日数据同步完成: 成功 {result['synced']}, 失败 {result['failed']}")
        return result

    # ===================== 查询接口 =====================

    def get_all_indices(self) -> List[Dict]:
        """获取所有指数静态属性"""
        return self._db.execute_query(
            "SELECT index_code, index_name, type_name, sec_name "
            "FROM market_index_static ORDER BY type_name, index_name"
        )

    def get_index_history(self, index_code: str,
                          start_date: Optional[str] = None,
                          end_date: Optional[str] = None) -> List[Dict]:
        """
        查询指数的历史日频数据，供 AI 分析用。
        """
        sql = "SELECT * FROM market_index_daily WHERE index_code = %s"
        params = [index_code]
        if start_date:
            sql += " AND trade_date >= %s"
            params.append(start_date)
        if end_date:
            sql += " AND trade_date <= %s"
            params.append(end_date)
        sql += " ORDER BY trade_date"
        return self._db.execute_query(sql, tuple(params))

    def get_latest_snapshot(self, index_code: str) -> Optional[Dict]:
        """获取指数最新快照"""
        rows = self._db.execute_query(
            "SELECT * FROM market_index_daily WHERE index_code = %s "
            "ORDER BY trade_date DESC LIMIT 1",
            (index_code,),
        )
        return rows[0] if rows else None

    def get_index_count(self) -> int:
        """已入库指数数量"""
        r = self._db.execute_query("SELECT COUNT(*) as cnt FROM market_index_static")
        return r[0]["cnt"] if r else 0

    def get_daily_count(self, index_code: str) -> int:
        """某指数历史数据条数"""
        r = self._db.execute_query(
            "SELECT COUNT(*) as cnt FROM market_index_daily WHERE index_code = %s",
            (index_code,),
        )
        return r[0]["cnt"] if r else 0
