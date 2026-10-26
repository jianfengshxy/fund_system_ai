ALTER TABLE market_index_daily
    ADD COLUMN trade_amount DECIMAL(20,2) DEFAULT NULL COMMENT '成交额' AFTER price;
