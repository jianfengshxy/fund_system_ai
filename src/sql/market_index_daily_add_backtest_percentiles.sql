ALTER TABLE market_index_daily
    ADD COLUMN pe_pct DECIMAL(10,4) DEFAULT NULL COMMENT 'PE 历史扩展分位(%)' AFTER pe_ttm,
    ADD COLUMN pb_pct DECIMAL(10,4) DEFAULT NULL COMMENT 'PB 历史扩展分位(%)' AFTER pb;
