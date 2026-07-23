-- ============================================================
-- 市场指数每日数据表
-- 存储指数每个交易日的行情、估值、热度数据
-- 数据来源:
--   价格/涨跌幅/热度 → FundIndexPrice 接口
--   PE-TTM/PB       → 指数估值走势 接口
--   PE分位/PB分位    → 指数阶段涨幅 接口
-- ============================================================

CREATE TABLE IF NOT EXISTS market_index_daily (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    index_code      VARCHAR(20)   NOT NULL COMMENT '指数代码',
    trade_date      DATE          NOT NULL COMMENT '交易日',
    price           DECIMAL(12,4) DEFAULT NULL COMMENT '收盘点位',
    change_pct      DECIMAL(10,4) DEFAULT NULL COMMENT '日涨跌幅(%)',
    pe_ttm          DECIMAL(12,4) DEFAULT NULL COMMENT '滚动市盈率 PE-TTM',
    pe_pct          DECIMAL(10,4) DEFAULT NULL COMMENT 'PE 历史分位(%)',
    pb              DECIMAL(12,4) DEFAULT NULL COMMENT '市净率 PB',
    pb_pct          DECIMAL(10,4) DEFAULT NULL COMMENT 'PB 历史分位(%)',
    heat_score      DECIMAL(5,2)  DEFAULT NULL COMMENT '资金热度评分(0-100)',
    created_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_index_date (index_code, trade_date),
    KEY idx_index_code (index_code),
    KEY idx_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='市场指数每日数据';
