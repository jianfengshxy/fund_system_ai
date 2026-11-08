# -*- coding: utf-8 -*-
"""
市场主题数据服务
  - 静态属性   → market_theme_static 表
  - 每日动态数据 → market_theme_daily 表

设计目标：
  1. 以 BK 主题代码为主键语义，承接主动基金关联主题口径
  2. 初始化时完成静态表和动态历史表的全量补齐
  3. 日常快照任务按字段真实归属日期落库：行情归 DEALTIME，评分归 SCOREDATE
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List


root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.domain.user.User import User
from src.db.database_connection import DatabaseConnection


logger = get_logger(__name__)


class MarketThemeService:
    """市场主题数据服务。"""

    def __init__(self):
        self._db = DatabaseConnection()
        self._ensure_tables_exist()

    def _ensure_tables_exist(self) -> None:
        """确保主题静态表和日频表存在。"""
        sql_dir = Path(root_dir) / "src" / "sql"
        for file_name in ("market_theme_static.sql", "market_theme_daily.sql"):
            sql_path = sql_dir / file_name
            if not sql_path.exists():
                logger.warning(f"主题建表 SQL 不存在，跳过: {sql_path}")
                continue
            sql = sql_path.read_text(encoding="utf-8")
            self._db.execute_query(sql)

    @staticmethod
    def _split_csv(raw: str) -> List[str]:
        return [part.strip() for part in (raw or "").split(",") if part.strip()]

    @staticmethod
    def _normalize_date(raw) -> Optional[str]:
        if raw is None:
            return None
        if isinstance(raw, datetime):
            return raw.date().isoformat()
        text = str(raw).strip()
        if not text:
            return None
        if len(text) >= 10:
            return text[:10]
        return text

    def _resolve_deal_date(self, deal_time=None, fallback_trade_date=None) -> Optional[str]:
        """解析行情所属交易日。"""
        return self._normalize_date(deal_time) or self._normalize_date(fallback_trade_date)

    def _resolve_score_date(self, score_date=None, fallback_trade_date=None) -> Optional[str]:
        """解析评分所属交易日。"""
        return self._normalize_date(score_date) or self._normalize_date(fallback_trade_date)

    def _upsert_theme_market_row(self, params: tuple) -> int:
        """按行情交易日写入主题最新行情/资金字段。"""
        sql = (
            "INSERT INTO market_theme_daily ("
            "theme_code, trade_date, price, change_pct, change_w, change_m, change_q, change_y, "
            "pe_ttm, pb, flow, flow_w, flow_m, flow_q, sumflow_w, sumflow_m, sumflow_q, mflow_w, "
            "main_flow_in, main_flow_out, retail_flow_in, retail_flow_out, "
            "main_flow_in_pct, main_flow_out_pct, retail_flow_in_pct, retail_flow_out_pct, "
            "inflow_days, outflow_days, up_days, down_days, avg_20d, max_60d, "
            "index_value, self_about_count, deal_time, score_date"
            ") VALUES ("
            "%s, %s, %s, %s, %s, %s, %s, %s, "
            "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
            "%s, %s, %s, %s, %s, %s, %s, %s, "
            "%s, %s, %s, %s, %s, %s, "
            "%s, %s, %s, %s"
            ") ON DUPLICATE KEY UPDATE "
            "price = COALESCE(VALUES(price), price), "
            "change_pct = COALESCE(VALUES(change_pct), change_pct), "
            "change_w = COALESCE(VALUES(change_w), change_w), "
            "change_m = COALESCE(VALUES(change_m), change_m), "
            "change_q = COALESCE(VALUES(change_q), change_q), "
            "change_y = COALESCE(VALUES(change_y), change_y), "
            "pe_ttm = COALESCE(VALUES(pe_ttm), pe_ttm), "
            "pb = COALESCE(VALUES(pb), pb), "
            "flow = COALESCE(VALUES(flow), flow), "
            "flow_w = COALESCE(VALUES(flow_w), flow_w), "
            "flow_m = COALESCE(VALUES(flow_m), flow_m), "
            "flow_q = COALESCE(VALUES(flow_q), flow_q), "
            "sumflow_w = COALESCE(VALUES(sumflow_w), sumflow_w), "
            "sumflow_m = COALESCE(VALUES(sumflow_m), sumflow_m), "
            "sumflow_q = COALESCE(VALUES(sumflow_q), sumflow_q), "
            "mflow_w = COALESCE(VALUES(mflow_w), mflow_w), "
            "main_flow_in = COALESCE(VALUES(main_flow_in), main_flow_in), "
            "main_flow_out = COALESCE(VALUES(main_flow_out), main_flow_out), "
            "retail_flow_in = COALESCE(VALUES(retail_flow_in), retail_flow_in), "
            "retail_flow_out = COALESCE(VALUES(retail_flow_out), retail_flow_out), "
            "main_flow_in_pct = COALESCE(VALUES(main_flow_in_pct), main_flow_in_pct), "
            "main_flow_out_pct = COALESCE(VALUES(main_flow_out_pct), main_flow_out_pct), "
            "retail_flow_in_pct = COALESCE(VALUES(retail_flow_in_pct), retail_flow_in_pct), "
            "retail_flow_out_pct = COALESCE(VALUES(retail_flow_out_pct), retail_flow_out_pct), "
            "inflow_days = COALESCE(VALUES(inflow_days), inflow_days), "
            "outflow_days = COALESCE(VALUES(outflow_days), outflow_days), "
            "up_days = COALESCE(VALUES(up_days), up_days), "
            "down_days = COALESCE(VALUES(down_days), down_days), "
            "avg_20d = COALESCE(VALUES(avg_20d), avg_20d), "
            "max_60d = COALESCE(VALUES(max_60d), max_60d), "
            "index_value = COALESCE(VALUES(index_value), index_value), "
            "self_about_count = COALESCE(VALUES(self_about_count), self_about_count), "
            "deal_time = COALESCE(VALUES(deal_time), deal_time), "
            "score_date = COALESCE(VALUES(score_date), score_date)"
        )
        return self._db.insert_many(sql, [params])

    def _upsert_theme_score_row(self, params: tuple) -> int:
        """按评分交易日回填主题评分字段。"""
        sql = (
            "INSERT INTO market_theme_daily ("
            "theme_code, trade_date, heat_score, chance_all, chance_jqd, chance_szqs, "
            "risk_all, risk_gll, risk_jzd, risk_yjd, pep100, pbp100, "
            "main_net_inflow, main_net_inflow_pct, fct_xlflow, score_date"
            ") VALUES ("
            "%s, %s, %s, %s, %s, %s, "
            "%s, %s, %s, %s, %s, %s, "
            "%s, %s, %s, %s"
            ") ON DUPLICATE KEY UPDATE "
            "heat_score = COALESCE(VALUES(heat_score), heat_score), "
            "chance_all = COALESCE(VALUES(chance_all), chance_all), "
            "chance_jqd = COALESCE(VALUES(chance_jqd), chance_jqd), "
            "chance_szqs = COALESCE(VALUES(chance_szqs), chance_szqs), "
            "risk_all = COALESCE(VALUES(risk_all), risk_all), "
            "risk_gll = COALESCE(VALUES(risk_gll), risk_gll), "
            "risk_jzd = COALESCE(VALUES(risk_jzd), risk_jzd), "
            "risk_yjd = COALESCE(VALUES(risk_yjd), risk_yjd), "
            "pep100 = COALESCE(VALUES(pep100), pep100), "
            "pbp100 = COALESCE(VALUES(pbp100), pbp100), "
            "main_net_inflow = COALESCE(VALUES(main_net_inflow), main_net_inflow), "
            "main_net_inflow_pct = COALESCE(VALUES(main_net_inflow_pct), main_net_inflow_pct), "
            "fct_xlflow = COALESCE(VALUES(fct_xlflow), fct_xlflow), "
            "score_date = COALESCE(VALUES(score_date), score_date)"
        )
        return self._db.insert_many(sql, [params])

    def get_theme_count(self) -> int:
        rows = self._db.execute_query("SELECT COUNT(*) AS cnt FROM market_theme_static")
        return int(rows[0]["cnt"]) if rows else 0

    def get_daily_count(self) -> int:
        rows = self._db.execute_query("SELECT COUNT(*) AS cnt FROM market_theme_daily")
        return int(rows[0]["cnt"]) if rows else 0

    def get_all_themes(self) -> List[Dict]:
        return self._db.execute_query(
            "SELECT theme_code, theme_name, type_code, type_name, linked_index_code, linked_index_name "
            "FROM market_theme_static ORDER BY theme_code"
        )

    def _collect_theme_candidates(self, user: User) -> Dict[str, Dict]:
        """从 FundRSBKRealTime 列表中抽取 BK 板块候选。"""
        from src.API.市场指数.获取所有主题 import get_all_market_themes

        resp = get_all_market_themes(user)
        if not resp.success or not resp.items:
            logger.warning(f"BK板块候选获取失败: {resp.first_error}")
            return {}

        themes: Dict[str, Dict] = {}
        for item in resp.items:
            theme_code = (item.INDEXCODE or "").strip()
            if not theme_code.upper().startswith("BK"):
                continue

            themes[theme_code] = {
                "theme_code": theme_code,
                "theme_name": item.INDEXNAME or theme_code,
                "full_theme_name": item.INDEXNAME or theme_code,
                "type_name": item.TYPE_NAME or "",
                "type_code": item.TYPE_CODE or "",
                "linked_index_code": "",
                "linked_index_name": "",
                "maker_name": "",
                "index_type": "",
                "index_desc": item.INDEXDESC or "",
                "relative_ind_name": "",
                "background_pic": "",
                "is_use_pbp": str(item.ISUSEPBP or 0),
                "is_fund_link": str(item.ISFUNDLINK or 0),
                "is_show_score": str(item.ISSHOWSCORE or 0),
                "rea_profile": item.REAPROFILE or "",
            }

        logger.info(f"BK板块候选获取完成: {len(themes)} 个")
        return themes

    def sync_all_themes(self, user: User, *, enrich_detail: bool = True) -> Dict[str, int]:
        """同步全部主题静态属性。"""
        from src.API.市场指数.基金主题详情 import get_fund_theme_detail

        candidates = self._collect_theme_candidates(user)
        if not candidates:
            return {"total": 0, "synced": 0, "failed": 0}

        rows = []
        failed = 0

        for theme_code, item in candidates.items():
            if enrich_detail:
                try:
                    detail = get_fund_theme_detail(user, theme_code)
                    if detail.success and detail.data:
                        rt = detail.data.realTimeList[0] if detail.data.realTimeList else None
                        bi = detail.data.themeBaseInfo[0] if detail.data.themeBaseInfo else None
                        if bi:
                            item["relative_ind_name"] = getattr(bi, "RELATIVEINDNAME", "") or item["relative_ind_name"]
                            item["background_pic"] = getattr(bi, "BACKGROUNDPIC", "") or item["background_pic"]
                            item["type_code"] = getattr(bi, "TYPE_CODE", "") or item["type_code"]
                        if rt:
                            item["is_use_pbp"] = str(getattr(rt, "ISUSEPBP", item["is_use_pbp"]))
                            item["is_fund_link"] = str(getattr(rt, "ISFUNDLINK", item["is_fund_link"]))
                            item["rea_profile"] = getattr(rt, "REAPROFILE", "") or item["rea_profile"]
                            item["type_code"] = getattr(rt, "TYPE_CODE", "") or item["type_code"]
                    else:
                        failed += 1
                except Exception as exc:
                    failed += 1
                    logger.warning(f"[{theme_code}] 主题静态详情补充失败: {exc}")
                time.sleep(0.05)

            rows.append(
                (
                    item["theme_code"],
                    item["theme_name"],
                    item["full_theme_name"],
                    item["type_name"],
                    item["type_code"],
                    item["linked_index_code"],
                    item["linked_index_name"],
                    item["maker_name"],
                    item["index_type"],
                    item["index_desc"],
                    item["relative_ind_name"],
                    item["background_pic"],
                    item["is_use_pbp"],
                    item["is_fund_link"],
                    item["is_show_score"],
                    item["rea_profile"],
                )
            )

        sql = (
            "REPLACE INTO market_theme_static ("
            "theme_code, theme_name, full_theme_name, type_name, type_code, "
            "linked_index_code, linked_index_name, maker_name, index_type, "
            "index_desc, relative_ind_name, background_pic, is_use_pbp, is_fund_link, is_show_score, rea_profile"
            ") VALUES ("
            "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s"
            ")"
        )
        synced = self._db.insert_many(sql, rows) if rows else 0
        logger.info(f"主题静态属性同步完成: 主题 {len(rows)} 个, 入库影响 {synced} 条, 详情失败 {failed}")
        return {"total": len(rows), "synced": synced, "failed": failed}

    def sync_all_themes_realtime_daily(self, user: User, type_code: str = "") -> Dict[str, int]:
        """用 FundRSBKRealTime 批量写入最新 BK 板块行情快照。"""
        from src.API.市场指数.获取所有主题 import get_all_market_themes

        resp = get_all_market_themes(user, type_code=type_code)
        if not resp.success or not resp.items:
            return {"total": 0, "synced": 0, "failed": 0}
        failed = 0
        rows = 0
        for item in resp.items:
            trade_date = self._resolve_deal_date(item.DEALTIME)
            if not item.INDEXCODE or not trade_date:
                failed += 1
                continue
            rows += self._upsert_theme_market_row(
                (
                    item.INDEXCODE,
                    trade_date,
                    item.PERCENTPRICE,
                    item.CHGRT,
                    item.W,
                    item.M,
                    item.Q,
                    item.Y,
                    item.PETTM,
                    item.PB,
                    item.FLOW,
                    item.FLOW_W,
                    item.FLOW_M,
                    item.FLOW_Q,
                    item.SUMFLOW_W,
                    item.SUMFLOW_M,
                    item.SUMFLOW_Q,
                    item.MFLOW_W,
                    item.MAIN_FLOW_IN,
                    item.MAIN_FLOW_OUT,
                    item.RETAIL_FLOW_IN,
                    item.RETAIL_FLOW_OUT,
                    item.MAIN_FLOW_IN_PERCENT,
                    item.MAIN_FLOW_OUT_PERCENT,
                    item.RETAIL_FLOW_IN_PERCENT,
                    item.RETAIL_FLOW_OUT_PERCENT,
                    item.INFLOWDAYS,
                    item.OUTFLOWDAYS,
                    item.UPDAYS,
                    item.DOWNDAYS,
                    item.AVG_20D,
                    item.MAX_60D,
                    item.INDEXVALUE,
                    item.SELFABOUTCOUNT,
                    item.DEALTIME or None,
                    self._normalize_date(item.SCOREDATE),
                )
            )
        logger.info(
            f"BK板块实时行情入库完成: 成功 {len(resp.items) - failed}/{len(resp.items)}, "
            f"失败 {failed}, 入库影响 {rows} 条"
        )
        return {"total": len(resp.items), "synced": len(resp.items) - failed, "failed": failed, "rows": rows}

    def _sync_theme_price_flow_batch(self, user: User, theme_code: str, range_type: str) -> int:
        from src.API.市场指数.指数资金热度与价格走势 import get_index_price_flow

        resp = get_index_price_flow(user, theme_code, range_type)
        if not resp.success or not resp.items:
            return 0

        sql = (
            "INSERT INTO market_theme_daily ("
            "theme_code, trade_date, price, change_pct, heat_score"
            ") VALUES (%s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE "
            "price = COALESCE(VALUES(price), price), "
            "change_pct = COALESCE(VALUES(change_pct), change_pct), "
            "heat_score = COALESCE(VALUES(heat_score), heat_score)"
        )
        params = [
            (
                theme_code,
                item.PDATE,
                item.PERCENTPRICE,
                item.CHGRT,
                item.XLFLOW_SCORE,
            )
            for item in resp.items
            if item.PDATE
        ]
        rows = self._db.insert_many(sql, params) if params else 0
        logger.info(f"[{theme_code}] 主题价格/热度序列入库: {rows} 条, 序列 {len(params)} 条")
        return rows

    def _sync_theme_detail_snapshot(self, user: User, theme_code: str, fallback_trade_date: Optional[str] = None) -> int:
        from src.API.市场指数.基金主题详情 import get_fund_theme_detail

        detail = get_fund_theme_detail(user, theme_code)
        if not detail.success or not detail.data:
            return 0

        rt = detail.data.realTimeList[0] if detail.data.realTimeList else None
        bi = detail.data.themeBaseInfo[0] if detail.data.themeBaseInfo else None
        if not rt and not bi:
            return 0

        score_date = self._resolve_score_date(
            (getattr(rt, "SCOREDATE", None) if rt else None)
            or (getattr(bi, "SCOREDATE", None) if bi else None),
            fallback_trade_date,
        )
        if not score_date:
            return 0

        rows = self._upsert_theme_score_row(
            (
                theme_code,
                score_date,
                getattr(rt, "CHANCE_ZJRD", None) if rt else (getattr(bi, "CHANCE_ZJRD", None) if bi else None),
                getattr(rt, "CHANCE_ALL", None) if rt else (getattr(bi, "CHANCE_ALL", None) if bi else None),
                getattr(rt, "CHANCE_JQD", None) if rt else (getattr(bi, "CHANCE_JQD", None) if bi else None),
                getattr(rt, "CHANCE_SZQS", None) if rt else None,
                getattr(rt, "RISK_ALL", None) if rt else None,
                getattr(rt, "RISK_GLL", None) if rt else (getattr(bi, "RISK_GLL", None) if bi else None),
                getattr(rt, "RISK_JZD", None) if rt else (getattr(bi, "RISK_JZD", None) if bi else None),
                getattr(rt, "RISK_YJD", None) if rt else (getattr(bi, "RISK_YJD", None) if bi else None),
                getattr(rt, "PEP100", None) if rt else (getattr(bi, "PEP100", None) if bi else None),
                getattr(rt, "PBP100", None) if rt else (getattr(bi, "PBP100", None) if bi else None),
                getattr(bi, "RM_NETFLOWXL", None) if bi else None,
                getattr(bi, "RM_NETFLOWXL_PCT", None) if bi else None,
                getattr(bi, "FCT_XLFLOW", None) if bi else None,
                score_date,
            )
        )
        logger.info(f"[{theme_code}] 主题评分回填入库: {rows} 条, score_date={score_date}")
        return rows

    def sync_all_themes_full_daily(self, user: User, *, range_type: str = "3n") -> Dict[str, int]:
        """
        为所有主题做动态表全量初始化：
          1. 回补近 3 年价格/涨跌幅/热度序列
          2. 写入当前 BK 板块实时快照
          3. 补充主题详情快照中的扩展字段
          4. 计算周期涨跌幅
        """
        themes = self.get_all_themes()
        result = {"total": len(themes), "synced": 0, "failed": 0, "rows": 0}
        realtime_result = self.sync_all_themes_realtime_daily(user)
        result["rows"] += realtime_result.get("rows", 0)
        result["realtime"] = realtime_result
        for item in themes:
            theme_code = item["theme_code"]
            try:
                price_rows = self._sync_theme_price_flow_batch(user, theme_code, range_type)
                detail_rows = self._sync_theme_detail_snapshot(user, theme_code)
                result["rows"] += price_rows + detail_rows
                if price_rows or detail_rows:
                    result["synced"] += 1
                else:
                    result["failed"] += 1
                    logger.warning(f"[{theme_code}] 主题动态全量初始化无返回")
            except Exception as exc:
                result["failed"] += 1
                logger.error(f"[{theme_code}] 主题动态全量初始化失败: {exc}")
            time.sleep(0.05)

        change_rows = self.fill_period_changes()
        result["period_changes"] = change_rows
        logger.info(
            f"主题动态全量初始化完成: 成功 {result['synced']}/{result['total']}, "
            f"失败 {result['failed']}, 入库影响 {result['rows']} 条, 周期涨跌幅 {change_rows} 行"
        )
        return result

    def sync_all_themes_latest_snapshot(self, user: User) -> Dict[str, int]:
        """
        同步所有主题的最新快照：
          1. 用 FundRSBKRealTime 刷新全量 BK 板块实时快照
          2. 刷新当前主题详情快照中的补充字段
          3. 重算周期涨跌幅
        """
        themes = self.get_all_themes()
        result = {"total": len(themes), "synced": 0, "failed": 0, "rows": 0}
        realtime_result = self.sync_all_themes_realtime_daily(user)
        result["rows"] += realtime_result.get("rows", 0)
        result["realtime"] = realtime_result
        for item in themes:
            theme_code = item["theme_code"]
            try:
                detail_rows = self._sync_theme_detail_snapshot(user, theme_code)
                result["rows"] += detail_rows
                result["synced"] += 1
            except Exception as exc:
                result["failed"] += 1
                logger.error(f"[{theme_code}] 主题最新快照同步失败: {exc}")
            time.sleep(0.05)

        change_rows = self.fill_period_changes()
        result["period_changes"] = change_rows
        logger.info(
            f"主题最新快照同步完成: 成功 {result['synced']}/{result['total']}, "
            f"失败 {result['failed']}, 入库影响 {result['rows']} 条, 周期涨跌幅 {change_rows} 行"
        )
        return result

    def fill_period_changes(self, theme_code: Optional[str] = None) -> int:
        """基于已有 price 数据回填主题周期涨跌幅。"""
        where_clause = "WHERE theme_code = %s" if theme_code else ""
        params = (theme_code,) if theme_code else ()
        sql = f"""
            UPDATE market_theme_daily d
            JOIN (
                SELECT id,
                    ROUND((price - LAG(price,   5) OVER w) / NULLIF(LAG(price,   5) OVER w, 0) * 100, 4) AS w_chg,
                    ROUND((price - LAG(price,  22) OVER w) / NULLIF(LAG(price,  22) OVER w, 0) * 100, 4) AS m_chg,
                    ROUND((price - LAG(price,  66) OVER w) / NULLIF(LAG(price,  66) OVER w, 0) * 100, 4) AS q_chg,
                    ROUND((price - LAG(price, 132) OVER w) / NULLIF(LAG(price, 132) OVER w, 0) * 100, 4) AS hy_chg,
                    ROUND((price - LAG(price, 252) OVER w) / NULLIF(LAG(price, 252) OVER w, 0) * 100, 4) AS y_chg
                FROM market_theme_daily
                {where_clause}
                WINDOW w AS (PARTITION BY theme_code ORDER BY trade_date)
            ) c ON d.id = c.id
            SET d.change_w = c.w_chg,
                d.change_m = c.m_chg,
                d.change_q = c.q_chg,
                d.change_hy = c.hy_chg,
                d.change_y = c.y_chg
        """
        rows = self._db.update(sql, params)
        label = theme_code or "全量主题"
        logger.info(f"[{label}] 主题周期涨跌幅填入: {rows} 行")
        return rows


if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    from src.API.登录接口.login import ensure_user_fresh

    user = ensure_user_fresh(DEFAULT_USER)
    svc = MarketThemeService()
    if svc.get_theme_count() == 0:
        svc.sync_all_themes(user, enrich_detail=True)
    if svc.get_daily_count() == 0:
        svc.sync_all_themes_full_daily(user, range_type="3n")
    svc.sync_all_themes_latest_snapshot(user)
