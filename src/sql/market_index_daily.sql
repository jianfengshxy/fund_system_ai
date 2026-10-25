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
    change_w        DECIMAL(10,4) DEFAULT NULL COMMENT '近5个交易日涨跌幅(%)',
    change_m        DECIMAL(10,4) DEFAULT NULL COMMENT '近22个交易日涨跌幅(%)',
    change_q        DECIMAL(10,4) DEFAULT NULL COMMENT '近66个交易日涨跌幅(%)',
    change_hy       DECIMAL(10,4) DEFAULT NULL COMMENT '近132个交易日涨跌幅(%)',
    change_y        DECIMAL(10,4) DEFAULT NULL COMMENT '近252个交易日涨跌幅(%)',
    pe_ttm          DECIMAL(12,4) DEFAULT NULL COMMENT '滚动市盈率 PE-TTM',
    pe_pct          DECIMAL(10,4) DEFAULT NULL COMMENT 'PE 历史分位(%)',
    pb              DECIMAL(12,4) DEFAULT NULL COMMENT '市净率 PB',
    pb_pct          DECIMAL(10,4) DEFAULT NULL COMMENT 'PB 历史分位(%)',
    heat_score      DECIMAL(5,2)  DEFAULT NULL COMMENT '资金热度评分(0-100)',
    profit_rate_q   DECIMAL(10,4) DEFAULT NULL COMMENT '持有3个月正收益概率(%)',
    profit_rate_hy  DECIMAL(10,4) DEFAULT NULL COMMENT '持有6个月正收益概率(%)',
    profit_rate_y   DECIMAL(10,4) DEFAULT NULL COMMENT '持有1年正收益概率(%)',
    profit_rate_try DECIMAL(10,4) DEFAULT NULL COMMENT '持有3年正收益概率(%)',
    avg_return_q    DECIMAL(10,4) DEFAULT NULL COMMENT '持有3个月平均收益率(%)',
    avg_return_hy   DECIMAL(10,4) DEFAULT NULL COMMENT '持有6个月平均收益率(%)',
    avg_return_y    DECIMAL(10,4) DEFAULT NULL COMMENT '持有1年平均收益率(%)',
    avg_return_try  DECIMAL(10,4) DEFAULT NULL COMMENT '持有3年平均收益率(%)',
    pe_percentile_y   DECIMAL(10,4) DEFAULT NULL COMMENT 'PE 近1年分位(%)',
    pe_percentile_try DECIMAL(10,4) DEFAULT NULL COMMENT 'PE 近3年分位(%)',
    pe_percentile_fy  DECIMAL(10,4) DEFAULT NULL COMMENT 'PE 近5年分位(%)',
    pe_percentile_ty  DECIMAL(10,4) DEFAULT NULL COMMENT 'PE 近10年分位(%)',
    pb_percentile_y   DECIMAL(10,4) DEFAULT NULL COMMENT 'PB 近1年分位(%)',
    pb_percentile_try DECIMAL(10,4) DEFAULT NULL COMMENT 'PB 近3年分位(%)',
    pb_percentile_fy  DECIMAL(10,4) DEFAULT NULL COMMENT 'PB 近5年分位(%)',
    pb_percentile_ty  DECIMAL(10,4) DEFAULT NULL COMMENT 'PB 近10年分位(%)',
    created_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_index_date (index_code, trade_date),
    KEY idx_index_code (index_code),
    KEY idx_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='市场指数每日数据';
