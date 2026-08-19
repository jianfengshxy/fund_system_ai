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

    def sync_all_indices_latest_daily_price_flow(
        self,
        user: User,
        *,
        range_type: str = "y",
        limit: Optional[int] = None,
    ) -> dict:
        static_indices = self._db.execute_query(
            "SELECT index_code, index_name FROM market_index_static "
            "WHERE type_name IN ('宽基','行业','主题','海外') ORDER BY index_code"
        )
        result = {"total": len(static_indices), "synced": 0, "failed": 0}

        for idx in static_indices:
            if limit and result["synced"] + result["failed"] >= limit:
                break
            code = idx["index_code"]
            name = idx["index_name"]
            try:
                changed = self.sync_daily_price_flow_batch(user, code, range_type)
                if changed:
                    result["synced"] += 1
                else:
                    result["failed"] += 1
                    logger.warning(f"[{code}] {name} 最新日数据同步无返回")
            except Exception as e:
                result["failed"] += 1
                logger.error(f"[{code}] {name} 最新日数据同步失败: {e}")
            time.sleep(0.1)

        logger.info(
            f"最新日数据同步完成: 成功 {result['synced']}/{result['total']}, 失败 {result['failed']}"
        )
        return result

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

    def fill_period_changes(self, index_code: Optional[str] = None) -> int:
        """
        基于已有 price 数据计算周期涨跌幅 (W/M/Q/HY/Y)，填入 change_w/m/q/hy/y。

        使用 MySQL LAG 窗口函数，以最近交易日收盘价为基准：
          - W:  向前 5 个交易日
          - M:  向前 22 个交易日（约一个月）
          - Q:  向前 66 个交易日（约一个季度）
          - HY: 向前 132 个交易日（约半年）
          - Y:  向前 252 个交易日（约一年）

        Args:
            index_code: 指定指数代码，为 None 时处理全部指数

        Returns:
            更新的行数
        """
        where_clause = "WHERE index_code = %s" if index_code else ""
        params = (index_code,) if index_code else ()
        sql = f"""
            UPDATE market_index_daily d
            JOIN (
                SELECT id,
                    ROUND((price - LAG(price,   5) OVER w) / NULLIF(LAG(price,   5) OVER w, 0) * 100, 4) AS w_chg,
                    ROUND((price - LAG(price,  22) OVER w) / NULLIF(LAG(price,  22) OVER w, 0) * 100, 4) AS m_chg,
                    ROUND((price - LAG(price,  66) OVER w) / NULLIF(LAG(price,  66) OVER w, 0) * 100, 4) AS q_chg,
                    ROUND((price - LAG(price, 132) OVER w) / NULLIF(LAG(price, 132) OVER w, 0) * 100, 4) AS hy_chg,
                    ROUND((price - LAG(price, 252) OVER w) / NULLIF(LAG(price, 252) OVER w, 0) * 100, 4) AS y_chg
                FROM market_index_daily
                {where_clause}
                WINDOW w AS (PARTITION BY index_code ORDER BY trade_date)
            ) c ON d.id = c.id
            SET d.change_w = c.w_chg,
                d.change_m = c.m_chg,
                d.change_q = c.q_chg,
                d.change_hy = c.hy_chg,
                d.change_y = c.y_chg
        """
        rows = self._db.update(sql, params)
        label = index_code or "全量"
        logger.info(f"[{label}] 周期涨跌幅填入: {rows} 行")
        return rows

    # ===================== 阶段指标（正收益概率/平均收益率/PE百分位/PB百分位） =====================

    def sync_stage_performance(self, user: User, index_code: str) -> bool:
        """
        获取并写入指数的阶段涨跌幅指标到最新交易日记录。

        API 返回字段 → DB 字段映射:
          PROFIT_RATE_Q/HY/Y/TRY  → profit_rate_q/hy/y/try   (正收益概率 %)
          AVGSYL_Q/HY/Y/TRY       → avg_return_q/hy/y/try    (平均收益率 %)
          PEP100_Y/TRY/FY/TY      → pe_percentile_y/try/fy/ty (PE 阶段百分位)
          PBP100_Y/TRY/FY/TY      → pb_percentile_y/try/fy/ty (PB 阶段百分位)

        Returns:
            是否更新成功
        """
        from src.API.市场指数.指数阶段指标 import get_fund_index_stage_performance

        data = get_fund_index_stage_performance(user, index_code)
        if not data:
            logger.warning(f"[{index_code}] 阶段指标无返回数据")
            return False

        # 找到该指数最新的一条日频记录
        latest = self._db.execute_query(
            "SELECT id FROM market_index_daily WHERE index_code = %s "
            "ORDER BY trade_date DESC LIMIT 1",
            (index_code,),
        )
        if not latest:
            logger.warning(f"[{index_code}] market_index_daily 中无历史数据，先同步日数据")
            return False

        record_id = latest[0]["id"]

        def _val(key):
            """将 API 返回值转为可存 DECIMAL 的类型（'--' / '' → None）"""
            v = data.get(key)
            if v is None:
                return None
            s = str(v).strip()
            return float(s) if s and s != "--" else None

        rows = self._db.update(
            "UPDATE market_index_daily SET "
            "profit_rate_q = %s, profit_rate_hy = %s, profit_rate_y = %s, profit_rate_try = %s, "
            "avg_return_q = %s, avg_return_hy = %s, avg_return_y = %s, avg_return_try = %s, "
            "pe_percentile_y = %s, pe_percentile_try = %s, pe_percentile_fy = %s, pe_percentile_ty = %s, "
            "pb_percentile_y = %s, pb_percentile_try = %s, pb_percentile_fy = %s, pb_percentile_ty = %s "
            "WHERE id = %s",
            (
                _val("PROFIT_RATE_Q"), _val("PROFIT_RATE_HY"),
                _val("PROFIT_RATE_Y"), _val("PROFIT_RATE_TRY"),
                _val("AVGSYL_Q"), _val("AVGSYL_HY"),
                _val("AVGSYL_Y"), _val("AVGSYL_TRY"),
                _val("PEP100_Y"), _val("PEP100_TRY"),
                _val("PEP100_FY"), _val("PEP100_TY"),
                _val("PBP100_Y"), _val("PBP100_TRY"),
                _val("PBP100_FY"), _val("PBP100_TY"),
                record_id,
            ),
        )
        logger.info(f"[{index_code}] 阶段指标入库: {rows} 行")
        return rows > 0

    def sync_all_indices_stage_performance(self, user: User, limit: Optional[int] = None) -> dict:
        """
        为 static 表中所有指数同步阶段指标。

        只处理 market_index_daily 中有日数据且在 target_types 中的指数。

        Returns:
            {"total": int, "synced": int, "failed": int, "no_daily_data": int}
        """
        static_indices = self._db.execute_query(
            "SELECT index_code, index_name FROM market_index_static "
            "WHERE type_name IN ('宽基','行业','主题','海外') ORDER BY index_code"
        )
        result = {"total": len(static_indices), "synced": 0,
                  "failed": 0, "no_daily_data": 0}

        for idx in static_indices:
            if limit and result["synced"] + result["failed"] + result["no_daily_data"] >= limit:
                break
            code = idx["index_code"]
            name = idx["index_name"]
            try:
                ok = self.sync_stage_performance(user, code)
                if ok:
                    result["synced"] += 1
                else:
                    result["no_daily_data"] += 1
            except Exception as e:
                result["failed"] += 1
                logger.error(f"[{code}] {name} 阶段指标同步失败: {e}")
            time.sleep(0.1)

        logger.info(
            f"阶段指标同步完成: 成功 {result['synced']}, "
            f"无日数据 {result['no_daily_data']}, 失败 {result['failed']}"
        )
        return result

    def sync_all_history_for_index(self, user: User, index_code: str) -> dict:
        """
        对单个指数执行全部历史数据同步（估值 → 价格/热度 → 阶段指标）。
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

    # ===================== 跟踪基金同步 =====================

    def get_best_tracking_c_fund(self, user: User, index_code: str) -> Optional[Dict]:
        """
        获取指数的最佳 C 类跟踪基金。

        调用 getTrackingFundV3 接口，从返回的基金列表中筛选：
          - 场外基金 (ISEXCHG="0")
          - 被动指数型 (DTZT="1")
          - 可申购 (ISBUY="1")
          - C 类份额 (ISCLASSC==1.0)
        
        选择优先级：
          1. 在满足上述条件的 C 类中，优先选择 7 天后赎回费为 0 的份额（SHRATE7 == 0）
          2. 在候选池内按基金规模 (ENDNAV) 取最大
          3. 若无 SHRATE7==0 的候选，则回退到“全部 C 类候选”里按 ENDNAV 取最大

        Args:
            user:       User 对象
            index_code: 指数代码

        Returns:
            {"fund_code": str, "fund_name": str} 或 None（无匹配基金时）
        """
        from src.API.市场指数.获取追踪指数的基金 import get_tracking_funds

        resp = get_tracking_funds(user, [index_code], page_size=50)
        if not resp.success:
            logger.warning(f"[{index_code}] 获取跟踪基金失败: {resp.first_error}")
            return None

        fund_list = resp.items.get(index_code, [])
        if not fund_list:
            logger.info(f"[{index_code}] 无跟踪基金数据")
            return None

        def _as_float(v, default: float = 0.0) -> float:
            try:
                if v is None or v == "":
                    return default
                return float(v)
            except Exception:
                return default

        def _is_class_c(v) -> bool:
            try:
                return float(v) == 1.0
            except Exception:
                return str(v) == "1"

        def _is_zero_fee_after_7(v) -> bool:
            try:
                return float(v) == 0.0
            except Exception:
                return False

        candidates = [
            f
            for f in fund_list
            if f.ISEXCHG == "0"
            and f.DTZT == "1"
            and f.ISBUY == "1"
            and _is_class_c(getattr(f, "ISCLASSC", None))
        ]
        if not candidates:
            logger.info(f"[{index_code}] 无符合条件的 C 类跟踪基金")
            return None

        zero_fee_candidates = [
            f for f in candidates if _is_zero_fee_after_7(getattr(f, "SHRATE7", None))
        ]
        best_pool = zero_fee_candidates if zero_fee_candidates else candidates
        best = max(best_pool, key=lambda f: _as_float(getattr(f, "ENDNAV", None), 0.0))
        best_endnav = _as_float(getattr(best, "ENDNAV", None), 0.0)
        logger.info(
            f"[{index_code}] 最佳 C 类跟踪基金: "
            f"{best.FCODE} {best.SHORTNAME} (规模={best_endnav:.1f}万)"
        )
        return {"fund_code": best.FCODE, "fund_name": best.SHORTNAME}

    def update_index_tracking_fund(self, index_code: str,
                                   fund_code: str, fund_name: str) -> bool:
        """
        更新 market_index_static 表中指数的关联跟踪基金信息。

        Args:
            index_code: 指数代码
            fund_code:  基金代码
            fund_name:  基金简称

        Returns:
            是否更新成功
        """
        rows = self._db.update(
            "UPDATE market_index_static "
            "SET track_fund_code = %s, track_fund_name = %s "
            "WHERE index_code = %s",
            (fund_code, fund_name, index_code),
        )
        if rows:
            logger.info(f"[{index_code}] 跟踪基金已更新: {fund_code} {fund_name}")
        else:
            logger.warning(f"[{index_code}] 未找到对应记录，更新失败")
        return rows > 0

    def sync_all_tracking_funds(self, user: User) -> dict:
        """
        为 static 表中所有指数同步最佳 C 类跟踪基金。

        逐指数调用 get_best_tracking_c_fund + update_index_tracking_fund，
        将结果写入 market_index_static.track_fund_code / track_fund_name。

        已有关联基金的指数会跳过（track_fund_code 非空）。
        
        为了避免历史落库的跟踪基金不满足“7天后0费率”条件导致后续运算不准确，
        这里会重新计算 best 并对比当前 track_fund_code：
          - 一致则计入 skipped
          - 不一致则执行 update（支持纠偏更新）

        Returns:
            {"total": int, "updated": int, "skipped": int, "no_match": int, "failed": int}
        """
        indices = self._db.execute_query(
            "SELECT index_code, index_name, track_fund_code "
            "FROM market_index_static "
            "ORDER BY index_code"
        )
        result = {"total": len(indices), "updated": 0, "skipped": 0,
                  "no_match": 0, "failed": 0}

        for idx in indices:
            code = idx["index_code"]
            name = idx["index_name"]

            try:
                best = self.get_best_tracking_c_fund(user, code)
                if best:
                    if idx.get("track_fund_code") == best["fund_code"]:
                        result["skipped"] += 1
                    else:
                        self.update_index_tracking_fund(
                            code, best["fund_code"], best["fund_name"]
                        )
                        result["updated"] += 1
                else:
                    result["no_match"] += 1
                time.sleep(0.3)
            except Exception as e:
                result["failed"] += 1
                logger.error(f"[{code}] {name} 同步失败: {e}")

        logger.info(
            f"跟踪基金同步完成: 总计 {result['total']}, "
            f"更新 {result['updated']}, 跳过 {result['skipped']}, "
            f"无匹配 {result['no_match']}, 失败 {result['failed']}"
        )
        return result
