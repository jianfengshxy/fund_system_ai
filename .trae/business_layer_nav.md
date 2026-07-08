# Business业务层 - 导航指南

## 概述
`src/bussiness/` 这一层是系统的策略实现层，包含各种基金投资策略的新增、加仓、止盈等核心逻辑。

## 目录结构
```
src/bussiness/
├── 全局智能定投处理/            # 全局定投处理
│   ├── add_plan.py             # 添加定投计划
│   ├── dissolve_plan.py        # 解散定投计划
│   ├── increase.py             # 定投加仓
│   └── redeem.py               # 定投止盈
├── 最优止盈组合/                # 最优止盈组合策略
│   ├── add_new.py              # 新增策略
│   ├── increase.py             # 加仓策略
│   ├── redeem.py               # 止盈策略
│   └── revoke.py               # 撤销策略
├── 见龙在田/                    # 见龙在田策略
│   ├── add_new.py              # 新增策略
│   ├── increase.py             # 加仓策略
│   └── redeem.py               # 止盈策略
├── 自定义组合/                  # 自定义组合策略
│   ├── add_new.py              # 新增策略
│   ├── increase.py             # 加仓策略
│   └── redeem.py               # 止盈策略
├── 黄金多利组合/                # 黄金多利策略
│   ├── increase.py             # 加仓策略
│   └── redeem.py               # 止盈策略
├── 黄金异次元/                  # 黄金异次元策略
│   ├── increase.py             # 加仓策略
│   └── redeem.py               # 止盈策略
├── 组合定投/                    # 组合定投策略
│   ├── increase.py             # 组合定投加仓
│   ├── 主动型组合定投管理.py   # 主动型组合管理
│   └── 指数型组合定投管理.py   # 指数型组合管理
└── 特殊止盈/                    # 特殊止盈策略
    └── 定投固定比率止盈.py     # 固定比率止盈
```

## 策略模块详解

### 最优止盈组合
路径：[src/bussiness/最优止盈组合/](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/src/bussiness/最优止盈组合/)
- 核心低风险策略
- 子账户：飞龙在天、马丁格尔plus
- 在 [s.yaml](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/s.yaml) 中有对应的云函数配置

### 见龙在田
路径：[src/bussiness/见龙在田/](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/src/bussiness/见龙在田/)
- 中高风险策略
- 对应Service层：[见龙在田算法](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/src/service/见龙在田算法/)

### 自定义组合
路径：[src/bussiness/自定义组合/](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/src/bussiness/自定义组合/)
- 用户自定义策略
- 支持多个子账户配置
- 对应Service层：[自定义组合算法](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/src/service/自定义组合算法/)

### 黄金相关策略
- [黄金多利组合](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/src/bussiness/黄金多利组合/)
- [黄金异次元](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/src/bussiness/黄金异次元/)
- 均为黄金相关投资策略

## 业务层特点
- 每个策略通常包含三个核心操作：`add_new`、`increase`、`redeem`
- 函数接收 `event` 和 `context` 参数（阿里云FC格式）
- 负责调用Service层实现业务逻辑
- 包含异常处理和错误重试机制

## 入口文件集成
所有Business层函数在 [index.py](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/index.py) 中统一导入和导出，供阿里云FC调用。
