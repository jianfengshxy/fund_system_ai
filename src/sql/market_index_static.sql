-- ============================================================
-- 市场指数静态属性表
-- 存储指数的基础元数据（名称、分类、编制公司等）
-- ============================================================

CREATE TABLE IF NOT EXISTS market_index_static (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    index_code      VARCHAR(20)  NOT NULL COMMENT '指数代码',
    index_name      VARCHAR(100) NOT NULL DEFAULT '' COMMENT '指数简称',
    full_index_name VARCHAR(200) NOT NULL DEFAULT '' COMMENT '指数全称',
    type_name       VARCHAR(50)  NOT NULL DEFAULT '' COMMENT '指数分类名称（宽基/行业/主题/策略/海外）',
    type_code       VARCHAR(20)  NOT NULL DEFAULT '' COMMENT '指数分类代码',
    sec_name        VARCHAR(200) NOT NULL DEFAULT '' COMMENT '关联主题/行业名称',
    sec_code        VARCHAR(100) NOT NULL DEFAULT '' COMMENT '关联主题/行业代码',
    maker_name      VARCHAR(100) NOT NULL DEFAULT '' COMMENT '指数编制公司',
    index_type      VARCHAR(20)  NOT NULL DEFAULT '' COMMENT '指数类型码',
    is_quot         VARCHAR(5)   NOT NULL DEFAULT '0' COMMENT '是否有实时行情(1=有,0=无)',
    is_use_pbp      VARCHAR(5)   NOT NULL DEFAULT '0' COMMENT '是否有PBP(1=有,0=无)',
    rea_profile     TEXT         COMMENT '指数描述文本',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_index_code (index_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='市场指数静态属性';
