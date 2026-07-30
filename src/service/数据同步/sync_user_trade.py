"""
用户交易记录同步服务

每日将用户最近 1 年的交易记录同步到 user_trade_record 表。
使用 get_one_fund_tran_infos (GetOneFundTranInfos API)，因为该 API 返回的
Colour 字段可以用于精确区分撤单交易（已撤单交易的 StatuIcon 也是 "3"）。

与旧版的主要差异：
  - 旧版使用 get_trades_list (GetQueryInfosQuickUse API)，Colour 始终为 None
  - 新版使用 get_one_fund_tran_infos，配合 trade_classifier 精确分类
  - 新增 trade_status 字段，记录每条交易是"已确认"还是"已撤单"
  - 新增 buy_sell 字段，标明交易方向（买入/卖出/未知）
  - 函数重命名为 sync_user_trades_daily（原 sync_user_weekly_trades）
"""

import sys
import os
import datetime
import logging
from decimal import Decimal

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.API.交易管理.trade import get_one_fund_tran_infos, get_trade_order_result
from src.service.交易管理.trade_classifier import classify_trades
from src.service.定投管理.定投查询.定投查询 import get_all_fund_plan_details
from src.API.组合管理.SubAccountMrg import getSubAccountList
from src.API.资产管理.getAssetListOfSub import get_asset_list_of_sub
from src.db.database_connection import DatabaseConnection
from src.common.logger import get_logger
from src.domain.user.User import User
from src.common.constant import DEFAULT_USER

logger = get_logger("SyncUserTrade")


def create_table_if_not_exists():
    """
    创建 user_trade_record 表（如不存在），并自动补充新增列。
    """
    db = DatabaseConnection()
    sql = """
    CREATE TABLE IF NOT EXISTS user_trade_record (
        customer_no VARCHAR(64) NOT NULL COMMENT '用户客户号',
        busin_serial_no VARCHAR(64) NOT NULL COMMENT '交易流水号',
        product_code VARCHAR(20) COMMENT '基金/产品代码',
        product_name VARCHAR(128) COMMENT '产品名称',
        business_type VARCHAR(64) COMMENT '业务类型',
        business_code VARCHAR(64) COMMENT '业务代码',
        apply_amount DECIMAL(20, 4) COMMENT '申请金额/份额',
        apply_count DECIMAL(20, 4) COMMENT '申请数量',
        confirm_count DECIMAL(20, 4) COMMENT '确认份额',
        status VARCHAR(32) COMMENT '状态(StatuIcon)',
        strike_start_date DATETIME COMMENT '交易发生时间',
        app_state_text VARCHAR(64) COMMENT 'APP状态文案',
        trade_status VARCHAR(16) COMMENT '交易状态: 已确认 | 已撤单',
        buy_sell VARCHAR(8) COMMENT '交易方向: 买入 | 卖出',
        remark TEXT COMMENT '备注',
        sub_account_no VARCHAR(64) NULL COMMENT '子账户编号',
        sub_account_name VARCHAR(128) NULL COMMENT '子账户名称',
        update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
        PRIMARY KEY (customer_no, busin_serial_no),
        INDEX idx_customer_date (customer_no, strike_start_date),
        INDEX idx_trade_status (trade_status),
        INDEX idx_buy_sell (buy_sell)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户交易记录表';
    """
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(sql)

        # 自动补充可能缺失的列（兼容旧表结构）
        new_columns = {
            "trade_status": "VARCHAR(16) COMMENT '交易状态: 已确认 | 已撤单'",
            "buy_sell": "VARCHAR(8) COMMENT '交易方向: 买入 | 卖出'",
            "sub_account_no": "VARCHAR(64) NULL COMMENT '子账户编号'",
            "sub_account_name": "VARCHAR(128) NULL COMMENT '子账户名称'",
        }
        for col_name, col_def in new_columns.items():
            try:
                cursor.execute(
                    f"ALTER TABLE user_trade_record ADD COLUMN {col_name} {col_def}"
                )
                logger.info(f"Added column {col_name} to user_trade_record")
            except Exception:
                pass  # 列已存在

        conn.commit()
        cursor.close()
        db.disconnect(conn)
        logger.info("Table user_trade_record check/creation completed.")
    except Exception as e:
        logger.error(f"Failed to create table: {e}")
        raise


def _enrich_sub_account_info(trades, user: User):
    """
    为缺少子账户信息的交易记录补充 sub_account_no / sub_account_name。

    三步回退策略（按优先级）:
      1. 通过 get_trade_order_result API 精确查询单笔交易的子账户
      2. 通过基金代码匹配定投计划（fund_plan_map）
      3. 通过资产扫描匹配（asset_sub_map: 遍历所有组合，看哪个组合持有该基金）
    """
    # Step 1: 加载定投计划映射
    fund_plan_map = {}
    try:
        plan_details = get_all_fund_plan_details(user)
        if plan_details:
            for detail in plan_details:
                plan = detail.rationPlan
                if plan and plan.fundCode and plan.subAccountNo:
                    fund_plan_map[plan.fundCode] = {
                        "sub_account_no": plan.subAccountNo,
                        "sub_account_name": plan.subAccountName,
                    }
            logger.info(f"Loaded {len(fund_plan_map)} fund plans for sub-account mapping.")
    except Exception as e:
        logger.warning(f"Failed to load fund plans: {e}")

    # Step 2: 逐条尝试精确查询
    for trade in trades:
        if getattr(trade, "sub_account_no", None):
            continue

        serial_no = (
            getattr(trade, "busin_serial_no", None)
            or getattr(trade, "id", None)
            or getattr(trade, "ID", None)
        )
        biz_code = getattr(trade, "business_code", None)

        if serial_no and biz_code and str(biz_code).isdigit():
            try:
                detail = get_trade_order_result(user, serial_no, str(biz_code))
                data = detail.get("Data") if isinstance(detail, dict) else None
                if data:
                    trade.sub_account_no = data.get("SubAccountNo")
                    trade.sub_account_name = data.get("SubAccountName")
            except Exception:
                pass  # 定投交易常返回"当前交易不存在"

        # 回退：定投计划映射
        if not getattr(trade, "sub_account_no", None):
            fund_code = getattr(trade, "fund_code", None) or getattr(trade, "product_code", None)
            if fund_code and fund_code in fund_plan_map:
                trade.sub_account_no = fund_plan_map[fund_code]["sub_account_no"]
                trade.sub_account_name = fund_plan_map[fund_code]["sub_account_name"]

    # Step 3: 仍缺失的，通过全量资产扫描匹配
    still_missing = [t for t in trades if not getattr(t, "sub_account_no", None)]
    if still_missing:
        logger.info(f"仍有 {len(still_missing)} 条无子账户信息，启动资产扫描...")
        asset_sub_map = {}
        try:
            sub_res = getSubAccountList(user)
            if sub_res and sub_res.Data:
                for sub in sub_res.Data:
                    sub_no = getattr(sub, "sub_account_no", None)
                    sub_name = getattr(sub, "sub_account_name", None)
                    if not sub_no:
                        continue
                    try:
                        assets = get_asset_list_of_sub(user, sub_no, with_meta=False)
                        if assets:
                            for a in assets:
                                if a.fund_code:
                                    asset_sub_map[a.fund_code] = {
                                        "sub_account_no": sub_no,
                                        "sub_account_name": sub_name,
                                    }
                    except Exception:
                        pass
            logger.info(f"资产扫描完成: {len(asset_sub_map)} 个基金-子账户映射")

            updated = 0
            for trade in still_missing:
                fc = getattr(trade, "fund_code", None) or getattr(trade, "product_code", None)
                if fc and fc in asset_sub_map:
                    trade.sub_account_no = asset_sub_map[fc]["sub_account_no"]
                    trade.sub_account_name = asset_sub_map[fc]["sub_account_name"]
                    updated += 1
            logger.info(f"资产扫描补充了 {updated} 条子账户信息")
        except Exception as e:
            logger.error(f"资产扫描失败: {e}")


def sync_user_trades_daily(user: User):
    """
    每日同步用户交易记录（最近 1 周）。

    使用 get_one_fund_tran_infos (GetOneFundTranInfos) 获取交易，
    通过 trade_classifier 精准区分 买入/卖出/撤单。
    """
    try:
        create_table_if_not_exists()

        # 使用 get_one_fund_tran_infos，能获取完整的 APPStateText 和 Colour 字段
        # fund_code="" 获取所有基金的交易记录（不限定单只基金）
        trades = get_one_fund_tran_infos(user, fund_code="", date_type="5")

        if not trades:
            logger.info(f"无交易记录需要同步 (user={user.account})")
            return

        logger.info(f"获取到 {len(trades)} 条交易记录 (user={user.account})")

        # 使用共享分类器，区分买入/卖出/撤单
        buy_trades, sell_trades, cancelled_trades = classify_trades(trades)

        logger.info(
            f"交易分类: {len(buy_trades)} 买入 / {len(sell_trades)} 卖出 / "
            f"{len(cancelled_trades)} 撤单"
        )

        # 补充子账户信息
        _enrich_sub_account_info(trades, user)

        # 入库
        db = DatabaseConnection()
        conn = db.get_connection()
        cursor = conn.cursor()

        def to_decimal(val):
            if val is None or val == "" or val == "--":
                return Decimal("0.0000")
            try:
                cleaned = str(val).replace(",", "").replace("份", "").replace("元", "").strip()
                return Decimal(cleaned)
            except Exception:
                return Decimal("0.0000")

        sql = """
        INSERT INTO user_trade_record (
            customer_no, busin_serial_no, product_code, product_name,
            business_type, business_code, apply_amount, apply_count,
            confirm_count, status, strike_start_date, app_state_text,
            trade_status, buy_sell, remark,
            sub_account_no, sub_account_name
        ) VALUES (
            %(customer_no)s, %(busin_serial_no)s, %(product_code)s, %(product_name)s,
            %(business_type)s, %(business_code)s, %(apply_amount)s, %(apply_count)s,
            %(confirm_count)s, %(status)s, %(strike_start_date)s, %(app_state_text)s,
            %(trade_status)s, %(buy_sell)s, %(remark)s,
            %(sub_account_no)s, %(sub_account_name)s
        ) ON DUPLICATE KEY UPDATE
            product_code = VALUES(product_code),
            product_name = VALUES(product_name),
            business_type = VALUES(business_type),
            business_code = VALUES(business_code),
            apply_amount = VALUES(apply_amount),
            apply_count = VALUES(apply_count),
            confirm_count = VALUES(confirm_count),
            status = VALUES(status),
            strike_start_date = VALUES(strike_start_date),
            app_state_text = VALUES(app_state_text),
            trade_status = VALUES(trade_status),
            buy_sell = VALUES(buy_sell),
            remark = VALUES(remark),
            sub_account_no = VALUES(sub_account_no),
            sub_account_name = VALUES(sub_account_name);
        """

        inserted = 0
        for trade in trades:
            serial_no = (
                getattr(trade, "busin_serial_no", None)
                or getattr(trade, "ID", None)
                or getattr(trade, "id", None)
            )
            if not serial_no:
                logger.warning(f"跳过错失流水号的交易: {trade}")
                continue

            # 判断交易状态（撤单 vs 已确认）和方向
            raw = getattr(trade, "raw", {}) or {}
            app_state_text = (raw.get("APPStateText") or "").strip()
            is_cancelled = "撤单" in app_state_text or raw.get("Colour") == "4"

            trade_status = "已撤单" if is_cancelled else "已确认"

            bt = trade.business_type or ""
            if bt in ("买入", "定投"):
                buy_sell = "买入"
            elif "卖基金" in bt or "赎回" in bt or "卖出" in bt:
                buy_sell = "卖出"
            else:
                buy_sell = ""

            record = {
                "customer_no": user.customer_no,
                "busin_serial_no": serial_no,
                "product_code": getattr(trade, "product_code", "")
                or getattr(trade, "fund_code", ""),
                "product_name": getattr(trade, "product_name", ""),
                "business_type": bt,
                "business_code": getattr(trade, "business_code", ""),
                "apply_amount": to_decimal(
                    getattr(trade, "amount", 0) or getattr(trade, "apply_amount", 0)
                ),
                "apply_count": to_decimal(getattr(trade, "apply_count", 0)),
                "confirm_count": to_decimal(getattr(trade, "confirm_count", 0)),
                "status": getattr(trade, "status", ""),
                "strike_start_date": getattr(trade, "strike_start_date", None)
                or getattr(trade, "apply_work_day", None),
                "app_state_text": app_state_text,
                "trade_status": trade_status,
                "buy_sell": buy_sell,
                "remark": getattr(trade, "remark", ""),
                "sub_account_no": getattr(trade, "sub_account_no", None),
                "sub_account_name": getattr(trade, "sub_account_name", None),
            }
            cursor.execute(sql, record)
            inserted += 1

        conn.commit()
        cursor.close()
        db.disconnect(conn)
        logger.info(
            f"成功同步 {inserted} 条交易记录 (user={user.account}), "
            f"其中已撤单 {len(cancelled_trades)} 条"
        )

    except Exception as e:
        logger.error(f"交易记录同步失败: {e}")
        raise


# 保留旧函数名作为兼容别名
sync_user_weekly_trades = sync_user_trades_daily


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    try:
        logger.info(f"开始交易同步 (DEFAULT_USER: {DEFAULT_USER.account})")
        sync_user_trades_daily(DEFAULT_USER)
        logger.info("交易同步完成")
    except Exception as e:
        logger.error(f"测试失败: {e}")
