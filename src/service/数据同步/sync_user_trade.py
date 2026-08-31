"""
用户交易记录同步服务

每日将用户最近 1 年的交易记录同步到 user_trade_record 表。
使用 get_one_fund_tran_infos (GetOneFundTranInfos API)，因为该 API 返回的
Colour 字段可以用于精确区分撤单交易（已撤单交易的 StatuIcon 也是 "3")。

设计要点：
  - 正常按 1 周增量同步，降低接口与数据库压力
  - 若检测到漏跑（超过 7 天）或首次初始化，则自动扩大窗口补齐历史
  - 分类使用 trade_classifier.get_trade_direction 统一入口，覆盖所有
    交易类型（买入/定投/转入投资账户/转出投资账户/现金分红/强行赎回等）

与旧版的主要差异：
  - 旧版使用 get_trades_list (GetQueryInfosQuickUse API)，Colour 始终为 None
  - 新版使用 get_one_fund_tran_infos，配合 trade_classifier 精确分类
  - 新增 trade_status 字段，记录每条交易是"已确认"还是"已撤单"
  - 新增 buy_sell 字段，标明交易方向（买入/卖出/分红/未知）
  - 新增 fund_code 字段，从 product_code 或 API 回退
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

from src.API.交易管理.trade import get_one_fund_tran_infos, get_trades_list
from src.service.交易管理.trade_classifier import classify_trades, get_trade_direction
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
            "buy_sell": "VARCHAR(8) COMMENT '交易方向: 买入 | 卖出 | 分红'",
            "fund_code": "VARCHAR(20) COMMENT '基金代码(从 product_code 回退提取)'",
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


def _build_serial_sub_map(user: User, date_type: str):
    """
    逐子账户调用 GetOneFundTranInfos（传 SubAccountNo 精确过滤，已探针验证），
    建立 流水号 → (sub_account_no, sub_account_name) 的**精确归属映射**。

    这是交易归属的权威来源：
      - 全量拉取（SubAccountNo=""）只保证交易完整性，返回的交易不带子账户归属；
      - 资产扫描兜底对"一基金被多组合持有"会随机错贴（遍历顺序决定，不可靠）；
      - 逐子账户拉取的每条交易，其归属由 API 按子账户过滤直接保证，100% 精确。

    遍历范围 = getSubAccountList 全部子账户 + 定投计划涉及的子账户。
    """
    serial_map = {}
    subs = []

    # 1) 真实子账户列表
    try:
        sub_res = getSubAccountList(user)
        if sub_res and sub_res.Data:
            for sub in sub_res.Data:
                no = getattr(sub, "sub_account_no", None)
                nm = getattr(sub, "sub_account_name", None)
                if no:
                    subs.append((no, nm))
        logger.info(f"获取到 {len(subs)} 个子账户，开始逐子账户拉取交易建立精确映射")
    except Exception as e:
        logger.warning(f"获取子账户列表失败: {e}")

    # 2) 定投计划涉及的子账户（可能不在普通子账户列表里）
    try:
        plan_details = get_all_fund_plan_details(user)
        if plan_details:
            for detail in plan_details:
                plan = detail.rationPlan
                if plan and plan.subAccountNo:
                    no = plan.subAccountNo
                    if not any(s[0] == no for s in subs):
                        subs.append((no, plan.subAccountName))
    except Exception as e:
        logger.warning(f"获取定投计划子账户失败: {e}")

    # 3) 逐子账户拉取，建映射
    for no, nm in subs:
        try:
            trades = get_one_fund_tran_infos(
                user, fund_code="", date_type=date_type, sub_account_no=no
            )
            cnt = 0
            for t in trades:
                serial = (
                    getattr(t, "busin_serial_no", None)
                    or getattr(t, "ID", None)
                    or getattr(t, "id", None)
                )
                if serial:
                    serial_map[serial] = (no, nm)
                    cnt += 1
            logger.info(f"子账户 {nm}({no}) 精确映射 {cnt} 条流水")
        except Exception as e:
            logger.warning(f"子账户 {nm}({no}) 拉取失败: {e}")

    logger.info(f"精确归属映射构建完成: {len(serial_map)} 条流水 → {len(subs)} 个子账户")
    return serial_map


def _enrich_sub_account_info(trades, user: User, serial_map=None):
    """
    为交易记录补充 sub_account_no / sub_account_name。

    归属优先级（2026-09-01 重写，根治错贴）：
      1. **精确映射**（serial_map，逐子账户拉取 API 直接返回）—— 权威，命中即定
      2. 定投计划映射（fund_plan_map，基金代码 → 定投计划子账户）
      3. 资产扫描兜底 —— **仅当基金在全账户中只有唯一持有人**时才填充；
         一基金被多个组合持有时**不填充**（宁缺勿错，避免历史"遍历覆盖"式随机错贴）

    历史教训：08-28 曾发生智投平台 7 笔买入被资产扫描错贴成"大数定律/定投计划"，
    且每次重新同步都会覆盖人工修正（ON DUPLICATE 全量覆盖）。故写库 SQL 已同步改为
    条件更新——本次同步拿不到确切归属时，保留库中已有归属，绝不覆盖为空/错误值。
    """
    serial_map = serial_map or {}

    # Step 1: 精确映射（最高优先级）
    hit = 0
    for trade in trades:
        if getattr(trade, "sub_account_no", None):
            continue
        serial = (
            getattr(trade, "busin_serial_no", None)
            or getattr(trade, "ID", None)
            or getattr(trade, "id", None)
        )
        if serial and serial in serial_map:
            trade.sub_account_no, trade.sub_account_name = serial_map[serial]
            hit += 1
    logger.info(f"精确映射命中 {hit} 条交易归属")

    # Step 2: 加载定投计划映射
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

    # Step 3: 定投计划映射回退
    for trade in trades:
        if getattr(trade, "sub_account_no", None):
            continue
        fund_code = getattr(trade, "fund_code", None) or getattr(trade, "product_code", None)
        if fund_code and fund_code in fund_plan_map:
            trade.sub_account_no = fund_plan_map[fund_code]["sub_account_no"]
            trade.sub_account_name = fund_plan_map[fund_code]["sub_account_name"]

    # Step 4: 仍缺失的，通过资产扫描匹配 —— 仅唯一持有人时填充（歧义保护）
    still_missing = [t for t in trades if not getattr(t, "sub_account_no", None)]
    if still_missing:
        logger.info(f"仍有 {len(still_missing)} 条无子账户信息，启动资产扫描（歧义保护：多持有人不填充）...")
        fund_owners = {}  # fund_code -> set of sub_account_no
        sub_meta = {}
        try:
            sub_res = getSubAccountList(user)
            if sub_res and sub_res.Data:
                for sub in sub_res.Data:
                    sub_no = getattr(sub, "sub_account_no", None)
                    sub_name = getattr(sub, "sub_account_name", None)
                    if not sub_no:
                        continue
                    sub_meta[sub_no] = sub_name
                    try:
                        assets = get_asset_list_of_sub(user, sub_no, with_meta=False)
                        if assets:
                            for a in assets:
                                if a.fund_code:
                                    fund_owners.setdefault(a.fund_code, set()).add(sub_no)
                    except Exception:
                        pass
            # 仅唯一持有人基金可回填；多持有人基金保持缺失（宁缺勿错）
            asset_sub_map = {
                fc: next(iter(owners))
                for fc, owners in fund_owners.items()
                if len(owners) == 1
            }
            logger.info(f"资产扫描完成: {len(fund_owners)} 个基金，其中唯一持有人 {len(asset_sub_map)} 个可安全回填")

            updated = 0
            for trade in still_missing:
                fc = getattr(trade, "fund_code", None) or getattr(trade, "product_code", None)
                if fc and fc in asset_sub_map:
                    trade.sub_account_no = asset_sub_map[fc]
                    trade.sub_account_name = sub_meta.get(asset_sub_map[fc])
                    updated += 1
            logger.info(f"资产扫描安全回填了 {updated} 条子账户信息"
                        f"（其余 {len(still_missing)-updated} 条因多持有人歧义而留空）")
        except Exception as e:
            logger.error(f"资产扫描失败: {e}")


def _enrich_product_info(trades, user: User, date_type: str):
    """
    补充 product_code / product_name。

    get_one_fund_tran_infos API 返回的每条交易中 ProductCode/ProductName 为空。
    get_trades_list API 则返回完整的产品信息。
    这里通过 get_trades_list 获取同一时间窗口的数据，按 ID 匹配补充。
    """
    # 检查有多少条无 product_code
    missing = [t for t in trades if not getattr(t, "product_code", None)]
    if not missing:
        return

    logger.info(f"有 {len(missing)} 条交易缺少 product_code，从 get_trades_list 补充...")
    try:
        enriched = get_trades_list(user, date_type=date_type)
        if not enriched:
            logger.warning("get_trades_list 返回空，无法补充 product_code")
            return

        # 按 ID 建立映射（ID 在两个 API 中一致）
        id_map = {}
        for t in enriched:
            tid = getattr(t, "id", None) or getattr(t, "ID", None)
            if tid:
                pc = getattr(t, "product_code", None) or getattr(t, "fund_code", None)
                pn = getattr(t, "product_name", None)
                if pc:
                    id_map[tid] = (pc, pn)

        updated = 0
        for t in trades:
            if getattr(t, "product_code", None):
                continue
            tid = getattr(t, "id", None) or getattr(t, "ID", None)
            if tid and tid in id_map:
                pc, pn = id_map[tid]
                t.product_code = pc
                if pn:
                    t.product_name = pn
                # 同步更新 fund_code
                if not getattr(t, "fund_code", None) or getattr(t, "fund_code", None) == "":
                    t.fund_code = pc
                updated += 1

        logger.info(f"成功补充 {updated}/{len(missing)} 条交易的 product_code")
    except Exception as e:
        logger.error(f"补充 product_code 失败: {e}")


def sync_user_trades_daily(user: User):
    """
    每日同步用户交易记录（默认近 1 周增量）。

    使用 get_one_fund_tran_infos (GetOneFundTranInfos) 获取交易，
    通过 trade_classifier 精准区分 买入/卖出/撤单/分红。

    设计说明：
      - 正常拉取近 1 周增量；若检测到漏跑或首次运行，则扩大窗口补齐
      - get_trade_direction 统一分类入口，覆盖所有 business_type / business_code
    """
    try:
        create_table_if_not_exists()

        db = DatabaseConnection()
        last_rows = db.execute_query(
            "SELECT MAX(strike_start_date) AS last_dt FROM user_trade_record WHERE customer_no=%s",
            (user.customer_no,),
        )
        last_dt = last_rows[0]["last_dt"] if last_rows and last_rows[0].get("last_dt") else None

        today = datetime.date.today()
        date_type = "5"
        product_date_type = "5"

        if last_dt:
            if isinstance(last_dt, str):
                try:
                    last_dt = datetime.datetime.fromisoformat(last_dt)
                except Exception:
                    last_dt = None
        if last_dt:
            last_day = last_dt.date()
            gap_days = (today - last_day).days
            if gap_days > 6:
                date_type = "3"
                product_date_type = "3"
        else:
            date_type = "3"
            product_date_type = "3"

        trades = get_one_fund_tran_infos(user, fund_code="", date_type=date_type)

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

        # 补充 product_code（get_one_fund_tran_infos 不返回此字段，需从 get_trades_list 获取）
        _enrich_product_info(trades, user, product_date_type)

        # 构建精确归属映射（逐子账户拉取，权威来源），再补充子账户信息
        serial_map = _build_serial_sub_map(user, date_type)
        _enrich_sub_account_info(trades, user, serial_map=serial_map)

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
            sub_account_no, sub_account_name, fund_code
        ) VALUES (
            %(customer_no)s, %(busin_serial_no)s, %(product_code)s, %(product_name)s,
            %(business_type)s, %(business_code)s, %(apply_amount)s, %(apply_count)s,
            %(confirm_count)s, %(status)s, %(strike_start_date)s, %(app_state_text)s,
            %(trade_status)s, %(buy_sell)s, %(remark)s,
            %(sub_account_no)s, %(sub_account_name)s, %(fund_code)s
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
            fund_code = IF(VALUES(fund_code) IS NULL OR VALUES(fund_code)='', fund_code, VALUES(fund_code)),
            sub_account_no = IF(VALUES(sub_account_no) IS NULL OR VALUES(sub_account_no)='', sub_account_no, VALUES(sub_account_no)),
            sub_account_name = IF(VALUES(sub_account_no) IS NULL OR VALUES(sub_account_no)='', sub_account_name, VALUES(sub_account_name));
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

            # 使用统一分类器判定交易方向
            bt = trade.business_type or ""
            bc = getattr(trade, "business_code", None)
            direction = get_trade_direction(bt, bc)

            if direction == "buy":
                buy_sell = "买入"
            elif direction == "sell":
                buy_sell = "卖出"
            elif direction == "dividend":
                buy_sell = "分红"
            else:
                buy_sell = ""

            # 提取 fund_code：优先用 fund_code 字段，其次从 product_code
            fund_code = getattr(trade, "fund_code", None)
            product_code = getattr(trade, "product_code", "") or ""
            if not fund_code or fund_code == "":
                # product_code 可能是纯数字基金代码，也可能为空
                if product_code and product_code.isdigit() and len(product_code) == 6:
                    fund_code = product_code
                else:
                    fund_code = product_code if product_code else ""

            record = {
                "customer_no": user.customer_no,
                "busin_serial_no": serial_no,
                "product_code": product_code or fund_code,
                "product_name": getattr(trade, "product_name", ""),
                "business_type": bt,
                "business_code": bc,
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
                "fund_code": fund_code,
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
