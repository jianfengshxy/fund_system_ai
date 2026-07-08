# 部署指南 - 导航

## 概述
项目后端部署在阿里云函数计算(FC)，前端部署在阿里云对象存储(OSS)，通过Serverless Devs工具管理部署。

## 核心部署文件
- [s.yaml](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/s.yaml): Serverless Devs部署配置文件
- [bootstrap](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/bootstrap): 自定义运行时启动脚本
- [env.yaml](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/env.yaml): 环境配置文件
- [function-template.yaml](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/function-template.yaml): 函数模板

## s.yaml 结构
s.yaml定义了所有阿里云FC函数，包括：
- `add_new` / `increase` / `redeem` (最优止盈组合)
- `add_new_custom` / `increase_custom` / `redeem_custom` (自定义组合)
- `add_new_jianlong` / `increase_jianlong` / `redeem_jianlong` (见龙在田)
- `increase_gold_portfolio` / `redeem_gold_portfolio` (黄金多利)
- `increase_gold_dimension_portfolio` / `redeem_gold_dimension_portfolio` (黄金异次元)
- `increase_all_fund_plans` / `redeem_all_fund_plans` (全局智能定投)
- `fixed_ratio_redeem` (特殊止盈)
- `fund_system_web` (Flask Web管理界面)
- `daily_task` (数据同步任务)

## 部署环境变量
所有环境变量在s.yaml中配置，包括：
- 数据库连接配置（MySQL）
- 策略参数配置
- 运行时配置

## 常用部署命令
| 命令 | 说明 |
|------|------|
| `s deploy` | 部署所有函数 |
| `s deploy <function-name>` | 部署特定函数 |
| `s info` | 查看部署信息 |
| `s logs` | 查看函数日志 |
| `s invoke` | 本地调用函数 |

## 前端部署
前端部署在OSS，构建输出在 `frontend/dist/` 目录，然后同步到OSS。
