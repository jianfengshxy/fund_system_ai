# 基金交易系统 - 项目架构导航

## 项目概述
这是一个基于天天基金App API的基金智能定投和组合管理系统，采用前后端分离架构，后端部署在阿里云函数计算(FC)。

## 分层架构
```
┌─────────────────────────────────────────────────────────┐
│  frontend/ - 前端展示层 (Vue 3 + TypeScript + Vite)      │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│  app.py - Flask Web管理界面                              │
│  index.py - 阿里云FC入口函数                              │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│  src/bussiness/ - 业务逻辑层 (策略实现)                   │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│  src/service/ - 服务层 (数据组织和业务服务)               │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│  src/API/ - API对接层 (天天基金App API封装)              │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│  src/domain/ - 领域模型层                                │
│  src/db/ - 数据访问层                                    │
│  src/common/ - 公共工具层                                │
└───────────────────────────────────────────────────────────┘
```

## 主要策略模块

| 策略名称 | 路径 | 说明 |
|---------|------|------|
| 最优止盈组合 | [src/bussiness/最优止盈组合/](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/src/bussiness/最优止盈组合/) | 核心低风险策略 |
| 见龙在田 | [src/bussiness/见龙在田/](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/src/bussiness/见龙在田/) | 中高风险策略 |
| 自定义组合 | [src/bussiness/自定义组合/](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/src/bussiness/自定义组合/) | 用户自定义策略 |
| 黄金多利 | [src/bussiness/黄金多利组合/](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/src/bussiness/黄金多利组合/) | 黄金相关策略 |
| 黄金异次元 | [src/bussiness/黄金异次元/](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/src/bussiness/黄金异次元/) | 黄金另一个策略 |
| 全局智能定投 | [src/bussiness/全局智能定投处理/](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/src/bussiness/全局智能定投处理/) | 定投处理 |
| 组合定投 | [src/bussiness/组合定投/](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/src/bussiness/组合定投/) | 组合定投管理 |

## 核心入口文件
- [app.py](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/app.py): Flask Web管理界面
- [index.py](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/index.py): 阿里云FC函数入口
- [s.yaml](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/s.yaml): Serverless Devs部署配置
