# 基金交易系统 - 项目Skills目录

## 概述
这是项目专属的Skills导航文档，帮助快速了解项目结构和找到相关代码。

## 导航索引
| 文档 | 说明 |
|------|------|
| [project_architecture.md](project_architecture.md) | 项目整体架构和策略模块导航 |
| [api_layer_nav.md](api_layer_nav.md) | API对接层（天天基金API）导航 |
| [service_layer_nav.md](service_layer_nav.md) | Service服务层导航 |
| [business_layer_nav.md](business_layer_nav.md) | Business业务层（策略实现）导航 |
| [frontend_nav.md](frontend_nav.md) | 前端开发导航 |
| [deployment_nav.md](deployment_nav.md) | 部署指南导航 |

## 项目技术栈
- **后端**: Python 3.10 + Flask + 阿里云函数计算
- **前端**: Vue 3 + TypeScript + Vite + Element Plus
- **数据库**: MySQL 8.0 (阿里云RDS)
- **部署工具**: Serverless Devs

## 目录结构说明
项目采用清晰的分层架构：
1. API层 - 对接天天基金API
2. Service层 - 数据组织和业务服务
3. Business层 - 策略实现和业务逻辑
4. Domain层 - 领域模型
5. DB层 - 数据访问
6. 前端 - 展示层

## 快速开始
- 开发后端：查看 [app.py](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/app.py) 或 [index.py](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/index.py)
- 开发前端：查看 [frontend/src/App.vue](file:///Users/shixiaoyu/Documents/trae_projects/fund_system_ai/frontend/src/App.vue)
- 查看策略：从 [project_architecture.md](project_architecture.md) 的策略模块开始
