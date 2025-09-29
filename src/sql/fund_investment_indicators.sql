CREATE TABLE fund_investment_indicators (
    update_date DATE NOT NULL COMMENT '数据更新日期，作为主键的一部分',
    fund_code VARCHAR(20) NOT NULL COMMENT '基金代码，作为主键的一部分',
    fund_name VARCHAR(255) COMMENT '基金名称',
    fund_type VARCHAR(50) COMMENT '基金类型',
    fund_sub_type VARCHAR(50) COMMENT '基金子类型',
    one_year_return DECIMAL(10,4) COMMENT '一年回报率',
    since_launch_return DECIMAL(10,4) COMMENT '自成立以来回报率',
    product_rank DECIMAL(10,4) COMMENT '产品排名',
    update_time VARCHAR(50) COMMENT '更新时间',
    tracking_index VARCHAR(50) COMMENT '追踪指数（可选）',
    PRIMARY KEY (update_date, fund_code)
);

-- 创建事件以自动删除过期数据（保留最近180天）
DELIMITER //
CREATE EVENT IF NOT EXISTS delete_old_fund_indicators
ON SCHEDULE EVERY 1 DAY
DO
BEGIN
    DELETE FROM fund_investment_indicators
    WHERE update_date < DATE_SUB(CURDATE(), INTERVAL 180 DAY);
END //
DELIMITER ;


-- 启用事件调度器
SET GLOBAL event_scheduler = ON;

-- 创建事件
DELIMITER //
CREATE EVENT IF NOT EXISTS delete_old_fund_indicators
ON SCHEDULE EVERY 1 DAY
DO
BEGIN
    DELETE FROM fund_investment_indicators
    WHERE update_date < DATE_SUB(CURDATE(), INTERVAL 180 DAY);
END //
DELIMITER ;

-- 验证事件
SHOW EVENTS LIKE 'delete_old_fund_indicators';
SHOW CREATE EVENT delete_old_fund_indicators;

ALTER TABLE fund_investment_indicators
  ADD COLUMN rank_100day INT NULL COMMENT '近100日排名',
  ADD COLUMN rank_30day INT NULL COMMENT '近30日排名',
  ADD COLUMN volatility DECIMAL(10,4) NULL COMMENT '波动率',
  ADD COLUMN nav_5day_avg DECIMAL(10,4) NULL COMMENT '近5日平均净值',
  ADD COLUMN season_item_rank INT NULL COMMENT '3个月排名值',
  ADD COLUMN season_item_sc INT NULL COMMENT '3个月排名总数',
  ADD COLUMN month_item_rank INT NULL COMMENT '月排名值',
  ADD COLUMN month_item_sc INT NULL COMMENT '月排名总数';