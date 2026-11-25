-- ============================================================
-- 市场主题静态属性表
-- 存储 BK 板块的基础元数据（主题/行业代码、名称、描述等）
--
-- 设计原则：
-- 1. 以 BK 板块代码作为主键语义，因为主动基金关联主题返回的是 BK 代码。
-- 2. 静态表只放“初始化后基本不变”的属性，避免与日频快照混放。
-- 3. 如 BK 板块已能映射到现有主题指数，则保留 linked_index_code / linked_index_name，
--    方便与 market_index_static / market_index_daily 做桥接分析。
-- ============================================================

CREATE TABLE IF NOT EXISTS market_theme_static (
    id                BIGINT AUTO_INCREMENT PRIMARY KEY,
    theme_code        VARCHAR(20)  NOT NULL COMMENT 'BK板块代码（BKxxxxxx）',
    theme_name        VARCHAR(100) NOT NULL DEFAULT '' COMMENT 'BK板块简称',
    full_theme_name   VARCHAR(200) NOT NULL DEFAULT '' COMMENT 'BK板块全称，暂无则与简称相同',
    type_name         VARCHAR(50)  NOT NULL DEFAULT '' COMMENT '分类名称，对应 TYPE_NAME（主题/行业）',
    type_code         VARCHAR(20)  NOT NULL DEFAULT '' COMMENT '分类代码，对应 TYPE_CODE（001003=主题，001002=行业）',
    linked_index_code VARCHAR(20)  NOT NULL DEFAULT '' COMMENT '若可映射到主题指数，则记录对应指数代码',
    linked_index_name VARCHAR(100) NOT NULL DEFAULT '' COMMENT '若可映射到主题指数，则记录对应指数名称',
    maker_name        VARCHAR(100) NOT NULL DEFAULT '' COMMENT '主题指数编制方，若可获取则写入',
    index_type        VARCHAR(20)  NOT NULL DEFAULT '' COMMENT '关联指数类型码，若可获取则写入',
    index_desc        TEXT         COMMENT '板块简介，对应 INDEXDESC',
    relative_ind_name VARCHAR(200) NOT NULL DEFAULT '' COMMENT '关联行业名称',
    background_pic    VARCHAR(500) NOT NULL DEFAULT '' COMMENT '主题背景图地址',
    is_use_pbp        VARCHAR(5)   NOT NULL DEFAULT '0' COMMENT '是否优先使用 PB 百分位(1=是,0=否)',
    is_fund_link      VARCHAR(5)   NOT NULL DEFAULT '0' COMMENT '是否存在基金联动入口(1=是,0=否)',
    is_show_score     VARCHAR(5)   NOT NULL DEFAULT '0' COMMENT '是否展示评分(1=是,0=否)，对应 ISSHOWSCORE',
    rea_profile       TEXT         COMMENT '主题描述文本',
    created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_theme_code (theme_code),
    KEY idx_linked_index_code (linked_index_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='市场主题静态属性';
