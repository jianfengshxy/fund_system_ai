# API对接层 - 导航指南

## 概述
`src/API/` 这一层是对天天基金App API的封装，负责与天天基金服务端通信。

## 目录结构
```
src/API/
├── _core/                   # API核心工具
│   ├── auth.py              # 用户认证和token管理
│   ├── client.py            # HTTP请求客户端
│   ├── headers.py           # 请求头构造
│   └── normalize.py         # 响应标准化处理
├── 交易管理/                # 交易相关API
│   ├── buyMrg.py            # 购买基金
│   ├── sellMrg.py           # 赎回基金
│   ├── revokMrg.py          # 撤单
│   ├── feeMrg.py            # 费率查询
│   └── trade.py             # 交易状态
├── 基金信息/                # 基金信息API
│   ├── FundInfo.py          # 基金基本信息
│   ├── FundRank.py          # 基金排名
│   ├── FundRankDiagram.py   # 基金排名图
│   └── 基金估值信息.py      # 基金估值
├── 大数据/                  # 大数据相关API
│   ├── 加仓风向标.py        # 加仓风向标
│   ├── 减仓风向标.py        # 减仓风向标
│   └── ...
├── 定投计划管理/            # 定投计划API
│   └── SmartPlan.py         # 智能定投计划
├── 组合管理/                # 组合管理API
│   └── SubAccountMrg.py     # 子账户管理
├── 资产管理/                # 资产相关API
│   ├── AssetManager.py      # 资产管理
│   └── getAssetListOfSub.py # 获取子账户资产
├── 登录接口/                # 登录相关API
│   └── login.py             # 用户登录
├── 自选基金/                # 自选基金API
│   └── FavorFund.py         # 自选基金
├── 银行卡信息/              # 银行卡相关API
│   └── CashBag.py           # 活期宝管理
└── 市场指数/                # 市场指数API
    └── ...
```

## API核心工具
- [auth.py](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/src/API/_core/auth.py): 用户认证和token管理
- [client.py](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/src/API/_core/client.py): HTTP请求客户端封装
- [headers.py](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/src/API/_core/headers.py): 请求头构造
- [normalize.py](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/src/API/_core/normalize.py): 响应数据标准化处理

## 使用指南
### 认证用户
所有API调用都需要先获得用户token，通过 `ensure_user_fresh` 函数保证用户状态有效：
```python
from src.API.登录接口.login import ensure_user_fresh
from src.common.constant import DEFAULT_USER
user = ensure_user_fresh(DEFAULT_USER, 600)  # 600秒内token有效
```

### 常用API调用模式
所有API函数通常接收 `user` 参数和业务参数，返回标准的API响应对象。
