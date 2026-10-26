ALTER TABLE market_index_daily
    ADD COLUMN main_net_inflow DECIMAL(20,2) DEFAULT NULL COMMENT '主力净流入金额' AFTER trade_amount;
