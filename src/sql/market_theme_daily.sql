-- ============================================================
-- 市场主题每日数据表
-- 存储主题每个交易日的行情、资金、估值、评分与风险数据
--
-- 设计原则：
-- 1. 与 market_index_daily 保持同名同义字段：
--    price / trade_amount / main_net_inflow / change_pct / pe_ttm / pb / heat_score ...
-- 2. 对主题接口独有字段单独扩展，避免拿“近端快照字段”硬塞进指数同名字段导致混淆。
-- 3. 当前接口拿不到的字段先预留，与指数表口径保持一致，后续补数时无需改表。
--
-- 主题字段口径说明：
--   heat_score          ← CHANCE_ZJRD，主题“资金热度评分”，是 0-100 分值，不是金额
--   main_net_inflow     ← RM_NETFLOWXL，主题“主力资金净流入金额”，不是当日总净流入
--   main_net_inflow_pct ← RM_NETFLOWXL_PCT，主力净流入占比(%)
--   flow                ← FLOW，当日总净流入金额
--   flow_w / flow_m / flow_q   ← 近 1 周 / 近 1 月 / 近 1 季净流入金额
--   sumflow_w / sumflow_m / sumflow_q
--                        ← 周 / 月 / 季累计净流入金额，和 flow_w/m/q 同为区间口径，保留原字段避免误读
--   fct_xlflow          ← 资金流因子值，是强弱/方向特征值，不是金额
-- ============================================================

CREATE TABLE IF NOT EXISTS market_theme_daily (
    id                    BIGINT AUTO_INCREMENT PRIMARY KEY,
    theme_code            VARCHAR(20)   NOT NULL COMMENT '主题代码（BKxxxxxx）',
    trade_date            DATE          NOT NULL COMMENT '交易日',

    -- 与 market_index_daily 同名同义字段
    price                 DECIMAL(12,4) DEFAULT NULL COMMENT '收盘点位/主题点位',
    trade_amount          DECIMAL(20,2) DEFAULT NULL COMMENT '成交额，当前主题接口通常取不到，预留与指数表一致口径',
    main_net_inflow       DECIMAL(20,2) DEFAULT NULL COMMENT '主力净流入金额，对应 RM_NETFLOWXL；正数=净流入，负数=净流出；不是当日总净流入',
    change_pct            DECIMAL(10,4) DEFAULT NULL COMMENT '日涨跌幅(%)',
    change_w              DECIMAL(10,4) DEFAULT NULL COMMENT '近5个交易日涨跌幅(%)',
    change_m              DECIMAL(10,4) DEFAULT NULL COMMENT '近22个交易日涨跌幅(%)',
    change_q              DECIMAL(10,4) DEFAULT NULL COMMENT '近66个交易日涨跌幅(%)',
    change_hy             DECIMAL(10,4) DEFAULT NULL COMMENT '近132个交易日涨跌幅(%)',
    change_y              DECIMAL(10,4) DEFAULT NULL COMMENT '近252个交易日涨跌幅(%)',
    pe_ttm                DECIMAL(12,4) DEFAULT NULL COMMENT '滚动市盈率 PE-TTM',
    pe_pct                DECIMAL(10,4) DEFAULT NULL COMMENT 'PE 历史扩展分位(%)，后续可按主题自身历史回填',
    pb                    DECIMAL(12,4) DEFAULT NULL COMMENT '市净率 PB',
    pb_pct                DECIMAL(10,4) DEFAULT NULL COMMENT 'PB 历史扩展分位(%)，后续可按主题自身历史回填',
    heat_score            DECIMAL(5,2)  DEFAULT NULL COMMENT '资金热度评分(0-100)，对应 CHANCE_ZJRD；是评分，不是金额',
    profit_rate_q         DECIMAL(10,4) DEFAULT NULL COMMENT '持有3个月正收益概率(%)，预留与指数表一致',
    profit_rate_hy        DECIMAL(10,4) DEFAULT NULL COMMENT '持有6个月正收益概率(%)，预留与指数表一致',
    profit_rate_y         DECIMAL(10,4) DEFAULT NULL COMMENT '持有1年正收益概率(%)，预留与指数表一致',
    profit_rate_try       DECIMAL(10,4) DEFAULT NULL COMMENT '持有3年正收益概率(%)，预留与指数表一致',
    avg_return_q          DECIMAL(10,4) DEFAULT NULL COMMENT '持有3个月平均收益率(%)，预留与指数表一致',
    avg_return_hy         DECIMAL(10,4) DEFAULT NULL COMMENT '持有6个月平均收益率(%)，预留与指数表一致',
    avg_return_y          DECIMAL(10,4) DEFAULT NULL COMMENT '持有1年平均收益率(%)，预留与指数表一致',
    avg_return_try        DECIMAL(10,4) DEFAULT NULL COMMENT '持有3年平均收益率(%)，预留与指数表一致',
    pe_percentile_y       DECIMAL(10,4) DEFAULT NULL COMMENT 'PE 近1年分位(%)，预留与指数表一致',
    pe_percentile_try     DECIMAL(10,4) DEFAULT NULL COMMENT 'PE 近3年分位(%)，预留与指数表一致',
    pe_percentile_fy      DECIMAL(10,4) DEFAULT NULL COMMENT 'PE 近5年分位(%)，预留与指数表一致',
    pe_percentile_ty      DECIMAL(10,4) DEFAULT NULL COMMENT 'PE 近10年分位(%)，预留与指数表一致',
    pb_percentile_y       DECIMAL(10,4) DEFAULT NULL COMMENT 'PB 近1年分位(%)，预留与指数表一致',
    pb_percentile_try     DECIMAL(10,4) DEFAULT NULL COMMENT 'PB 近3年分位(%)，预留与指数表一致',
    pb_percentile_fy      DECIMAL(10,4) DEFAULT NULL COMMENT 'PB 近5年分位(%)，预留与指数表一致',
    pb_percentile_ty      DECIMAL(10,4) DEFAULT NULL COMMENT 'PB 近10年分位(%)，预留与指数表一致',

    -- 主题接口特有扩展字段
    chance_all            DECIMAL(10,4) DEFAULT NULL COMMENT '机会综合评分，对应 CHANCE_ALL',
    chance_jqd            DECIMAL(10,4) DEFAULT NULL COMMENT '景气度评分，对应 CHANCE_JQD',
    risk_all              DECIMAL(10,4) DEFAULT NULL COMMENT '风险综合评分，对应 RISK_ALL',
    risk_gll              DECIMAL(10,4) DEFAULT NULL COMMENT '概率风险评分，对应 RISK_GLL',
    risk_jzd              DECIMAL(10,4) DEFAULT NULL COMMENT '阶段风险评分，对应 RISK_JZD',
    risk_yjd              DECIMAL(10,4) DEFAULT NULL COMMENT '预警风险评分，对应 RISK_YJD',
    flow                  DECIMAL(20,2) DEFAULT NULL COMMENT '当日总净流入金额，对应 FLOW；不是主力口径',
    flow_w                DECIMAL(20,2) DEFAULT NULL COMMENT '近1周净流入金额，对应 FLOW_W',
    flow_m                DECIMAL(20,2) DEFAULT NULL COMMENT '近1月净流入金额，对应 FLOW_M',
    flow_q                DECIMAL(20,2) DEFAULT NULL COMMENT '近1季净流入金额，对应 FLOW_Q',
    sumflow_w             DECIMAL(20,2) DEFAULT NULL COMMENT '近1周累计净流入金额，对应 SUMFLOW_W；保留上游原字段口径',
    sumflow_m             DECIMAL(20,2) DEFAULT NULL COMMENT '近1月累计净流入金额，对应 SUMFLOW_M；保留上游原字段口径',
    sumflow_q             DECIMAL(20,2) DEFAULT NULL COMMENT '近1季累计净流入金额，对应 SUMFLOW_Q；保留上游原字段口径',
    main_net_inflow_pct   DECIMAL(10,4) DEFAULT NULL COMMENT '主力净流入占比(%)，对应 RM_NETFLOWXL_PCT',
    fct_xlflow            DECIMAL(12,6) DEFAULT NULL COMMENT '资金流因子值，对应 FCT_XLFLOW；是特征值，不是金额',
    main_flow_in          DECIMAL(20,2) DEFAULT NULL COMMENT '主力流入金额，对应 MAIN_FLOW_IN',
    main_flow_out         DECIMAL(20,2) DEFAULT NULL COMMENT '主力流出金额，对应 MAIN_FLOW_OUT',
    retail_flow_in        DECIMAL(20,2) DEFAULT NULL COMMENT '散户流入金额，对应 RETAIL_FLOW_IN',
    retail_flow_out       DECIMAL(20,2) DEFAULT NULL COMMENT '散户流出金额，对应 RETAIL_FLOW_OUT',
    main_flow_in_pct      VARCHAR(20)   DEFAULT NULL COMMENT '主力流入占比(%)，对应 MAIN_FLOW_IN_PERCENT',
    main_flow_out_pct     VARCHAR(20)   DEFAULT NULL COMMENT '主力流出占比(%)，对应 MAIN_FLOW_OUT_PERCENT',
    retail_flow_in_pct    VARCHAR(20)   DEFAULT NULL COMMENT '散户流入占比(%)，对应 RETAIL_FLOW_IN_PERCENT',
    retail_flow_out_pct   VARCHAR(20)   DEFAULT NULL COMMENT '散户流出占比(%)，对应 RETAIL_FLOW_OUT_PERCENT',
    inflow_days           INT           DEFAULT NULL COMMENT '连续流入天数，对应 INFLOWDAYS',
    outflow_days          INT           DEFAULT NULL COMMENT '连续流出天数，对应 OUTFLOWDAYS',
    up_days               INT           DEFAULT NULL COMMENT '连续上涨天数，对应 UPDAYS',
    down_days             INT           DEFAULT NULL COMMENT '连续下跌天数，对应 DOWNDAYS',
    avg_20d               DECIMAL(12,4) DEFAULT NULL COMMENT '20日均线点位',
    max_60d               DECIMAL(12,4) DEFAULT NULL COMMENT '60日最高点位',
    pep100                DECIMAL(10,4) DEFAULT NULL COMMENT 'PE 历史百分位（上游原始口径）',
    pbp100                DECIMAL(10,4) DEFAULT NULL COMMENT 'PB 历史百分位（上游原始口径）',
    chance_szqs           DECIMAL(10,4) DEFAULT NULL COMMENT '市场走势趋势评分，对应 CHANCE_SZQS',
    index_value           DECIMAL(20,4) DEFAULT NULL COMMENT '指数原始值，对应 INDEXVALUE',
    mflow_w               DECIMAL(20,2) DEFAULT NULL COMMENT '近1周主力净流入金额，对应 MFLOW_W',
    self_about_count      INT           DEFAULT NULL COMMENT '自选/关联数量，对应 SELFABOUTCOUNT',
    deal_time             DATETIME      DEFAULT NULL COMMENT '行情时间，对应 DEALTIME；行情类字段按该日期对应的交易日落库',
    score_date            DATE          DEFAULT NULL COMMENT '评分对应交易日；评分字段延迟产生时，回填到该交易日对应记录',

    created_at            DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_theme_date (theme_code, trade_date),
    KEY idx_theme_code (theme_code),
    KEY idx_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='市场主题每日数据';
