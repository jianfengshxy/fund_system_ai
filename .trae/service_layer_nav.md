# Service服务层 - 导航指南

## 概述
`src/service/` 这一层负责组织数据和提供业务服务，是API层和Business层之间的桥梁。

## 目录结构
```
src/service/
├── 交易管理/                    # 交易相关服务
│   ├── 购买基金.py             # 基金购买服务
│   ├── 赎回基金.py             # 基金赎回服务
│   ├── 费率查询.py             # 费率查询服务
│   └── 交易查询.py             # 交易查询服务
├── 公共服务/                    # 公共服务
│   ├── nav_gate_service.py    # 净值闸口服务
│   ├── risk_control_service.py # 风控服务
│   ├── trade_guard_service.py  # 交易保护服务
│   └── trade_time_service.py   # 交易时间服务
├── 基金信息/                    # 基金信息服务
│   └── 基金信息.py
├── 大数据/                      # 大数据相关服务
│   ├── 加仓风向标服务.py        # 加仓风向标服务
│   ├── 低位加仓风向标筛选.py    # 低位筛选
│   ├── 高频加仓基金查询.py      # 高频基金查询
│   ├── 增加高频加仓基金到自选组合.py
│   └── 删除高频加仓基金到自选组合.py
├── 定投管理/                    # 定投管理服务
│   ├── 定投查询/               # 定投查询子目录
│   ├── 定投状态/               # 定投状态子目录
│   ├── 智能定投/               # 智能定投子目录
│   └── 组合定投/               # 组合定投子目录
├── 数据同步/                    # 数据同步服务
│   ├── sync_user_asset.py     # 用户资产同步
│   ├── sync_user_trade.py     # 用户交易同步
│   ├── sync_sub_account_asset.py # 子账户资产同步
│   └── sync_sub_account_fund_asset.py # 子账户基金资产同步
├── 用户管理/                    # 用户管理服务
│   └── 用户信息.py
├── 自选基金/                    # 自选基金服务
│   └── 自选组合服务.py
├── 资产管理/                    # 资产管理服务
│   └── get_fund_asset_detail.py
├── 银行卡账户/                  # 银行卡账户服务
│   └── bankAccoutService.py
├── 加仓风向标组合算法/          # 加仓风向标组合算法
│   ├── 加仓风向标新增.py
│   ├── 加仓风向标加仓.py
│   └── 加仓风向标止盈.py
├── 自定义组合算法/              # 自定义组合算法
│   ├── 自定义组合新增.py
│   ├── 自定义组合加仓.py
│   └── 自定义组合止盈.py
├── 见龙在田算法/                # 见龙在田算法
│   ├── 见龙在田新增.py
│   ├── 见龙在田加仓.py
│   └── 见龙在田止盈.py
├── 黄金多利组合算法/            # 黄金多利组合算法
│   ├── 黄金多利加仓.py
│   └── 黄金多利止盈.py
└── 黄金异次元算法/              # 黄金异次元算法
    ├── 黄金异次元加仓.py
    └── 黄金异次元止盈.py
```

## Service层特点
- 每个Service通常接收 `user` 参数进行身份验证
- 负责调用API层获取数据
- 进行数据处理和业务逻辑
- 返回标准化结果给Business层

## 数据同步服务
数据同步是系统非常重要的部分，相关服务在 [src/service/数据同步/](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/src/service/数据同步/)：
- `sync_user_asset.py`: 用户资产同步
- `sync_user_trade.py`: 用户交易同步
- `sync_sub_account_asset.py`: 子账户资产同步
- `sync_sub_account_fund_asset.py`: 子账户基金资产同步
- `sync_total_account_fund_asset.py`: 总账户基金资产同步
