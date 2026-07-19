# 基金系统整体架构说明

## 1. 系统定位

`fund_system_ai` 是一个基于天天基金开放接口能力构建的基金交易与策略执行系统，当前重点能力包括：

- 基金信息查询、估值与行情拉取
- 组合管理、定投计划管理、交易下单与撤单
- 策略化业务编排，例如最优止盈、见龙在田、自定义组合、组合定投
- 基于阿里云函数计算（FC）的定时任务调度与远程执行
- MySQL 持久化，保存任务配置、执行状态、部分业务数据和分析指标

系统目标不是单一的“接口调用脚本”，而是一个可持续演进的基金策略平台。后续还将扩展为“在线交易系统 + 历史数据分析平台”的双轨架构。

## 2. 当前分层

项目核心代码位于 `src/`，按职责划分为以下层次。

### 2.1 API 层

目录：`src/API`

职责：

- 直接对接第三方平台接口，当前主要是天天基金相关接口
- 负责请求参数构造、HTTP 调用、响应解析、异常转换
- 返回项目内部统一对象，供上层复用

设计原则：

- API 层只关心“如何调用外部接口”
- 不承载跨接口业务编排
- 不直接依赖 `bussiness`
- 原则上不反向依赖 `service`

典型模块：

- `src/API/交易管理`
- `src/API/基金信息`
- `src/API/定投计划管理`
- `src/API/资产管理`
- `src/API/组合管理`

### 2.2 Service 层

目录：`src/service`

职责：

- 将 API 层的原子接口按业务能力进行封装
- 封装风控、交易时间判断、定投管理、用户管理、数据同步等可复用能力
- 作为业务层的主依赖，屏蔽底层接口细节

设计原则：

- Service 层关注“能力复用”和“领域动作”
- 尽量保持无状态、可复用、可测试
- 可调用 `API`、`db`、`domain`、`common`
- 不反向依赖 `bussiness`

典型模块：

- `src/service/交易管理`
- `src/service/公共服务`
- `src/service/用户管理`
- `src/service/定投管理`
- `src/service/大数据`
- `src/service/数据同步`

### 2.3 Bussiness 层

目录：`src/bussiness`

职责：

- 实现具体交易策略和业务流程编排
- 组合多个 service 能力完成“新增、加仓、止盈、解散、撤回”等业务动作
- 保存策略层的参数约束和决策顺序

设计原则：

- Bussiness 层关注“策略”，而不是底层接口细节
- 优先依赖 `service`，避免直接跨到 `API`
- 脚本化调试代码与正式策略代码要分离
- 不在业务文件中保留明文账号、密码、预算配置

典型模块：

- `src/bussiness/最优止盈组合`
- `src/bussiness/见龙在田`
- `src/bussiness/组合定投`
- `src/bussiness/全局智能定投处理`
- `src/bussiness/自定义组合`

### 2.4 DB 层

目录：`src/db`

职责：

- 封装 MySQL 连接池与存储访问
- 实现 repository
- 为 service / task 管理提供持久化能力

设计原则：

- 统一从环境变量和 `s.yaml` 读取配置
- 不在代码中保留默认明文数据库凭据
- 尽量保持“数据访问实现”单一职责

当前关键模块：

- `src/db/database_connection.py`
- `src/db/fund_repository_impl.py`
- `src/db/fund_investment_indicator_repository_impl.py`

### 2.5 Domain 层

目录：`src/domain`

职责：

- 定义系统内部的数据对象、响应对象、仓储接口
- 作为各层之间的数据契约

设计原则：

- Domain 层应稳定、可复用、尽量少依赖外部实现
- 逐步向“领域对象 + 仓储接口”演进

典型对象：

- `User`
- `FundInfo`
- `FundPlan`
- `AssetDetails`
- `TradeResult`

### 2.6 定时任务层

目录：

- `src/scheduled_tasks`
- `src/task`
- `src/scheduled_task_manager.py`

职责：

- 管理任务配置、任务同步、执行状态回写
- 承接 FC 事件和本地调度事件
- 将定时任务入口统一适配到具体策略

分工说明：

- `src/task`：策略任务入口，按交易策略拆分 handler
- `src/scheduled_tasks/executor.py`：本地执行器，解析 handler/policy 并执行
- `src/scheduled_task_manager.py`：任务配置、执行日志、FC 同步、立即执行

### 2.7 Web API 层

目录：`src/web_api`

职责：

- 提供 HTTP 入口
- 对外暴露任务管理等后台管理能力
- 承接 FC HTTP 触发请求

当前重点：

- `src/web_api/fc_http_handler.py`

## 3. 推荐依赖方向

建议保持以下依赖链路：

`web_api/task -> bussiness -> service -> API/db -> domain/common`

约束如下：

- `API` 不直接依赖 `service`
- `db` 不依赖 `service` 或 `bussiness`
- `domain` 不依赖具体实现层
- `bussiness` 尽量只做策略编排，不做底层 HTTP 与 SQL 细节

## 4. 核心运行链路

### 4.1 交易业务链路

1. 任务入口或手工调用进入 `task` / `web_api`
2. `bussiness` 根据策略编排执行
3. `service` 执行交易保护、用户信息装配、参数校验
4. `API` 调用天天基金接口完成下单、赎回、撤单、查询
5. `db` 记录执行结果、配置和分析数据

### 4.2 定时任务链路

1. 页面维护 `scheduled_tasks` 表中的任务配置
2. 后端将配置同步到阿里云 FC timer trigger
3. FC 到点触发函数
4. `src/task/*` 统一解析事件
5. 业务执行后回写 `scheduled_tasks.last_executed_*`

### 4.3 立即执行链路

1. 前端触发“立即执行”
2. 后端调用 FC OpenAPI `InvokeFunction`
3. 云端函数按当前部署 handler 执行
4. 执行结果回写数据库日志

## 5. 当前重构方向

本轮优化聚焦“稳定性优先”。

### 5.1 已优化的重点

- 提取统一配置加载能力到 `src/common/app_config.py`
- 数据库连接层改为环境变量优先、`s.yaml` 兜底，不再保留默认明文凭据
- 强化定时任务运行时识别逻辑，支持通过 `task_name`、`fc_trigger_name`、`fc_function_name` 回写执行状态
- 优化本地任务执行器的 handler 解析逻辑，提升日志可观测性
- 修正 `SmartPlan` 中 API 层反向依赖 service 的问题
- 增加覆盖配置加载、数据库封装、任务运行时、任务执行器的 unit tests

### 5.2 仍建议继续推进的事项

- 清理 `bussiness` 层中遗留的明文账号/密码和批处理脚本配置
- 去除大面积 `sys.path` 注入，统一使用包导入
- 将超大业务文件进一步拆分为“策略入口 + 策略服务 + 调试脚本”
- 逐步让 `bussiness` 只依赖 `service`
- 将任务执行入口彻底统一到 `src.task.*`

## 6. 部署架构

当前部署架构：

- 前端：Vue 3，部署在阿里云 OSS
- 后端：Python 3.10，部署在阿里云 FC 3.0
- 在线数据库：MySQL（RDS）

建议继续保持：

- 配置通过环境变量注入
- `s.yaml` 只做本地部署辅助，不纳入版本控制
- FC 任务执行与任务管理后台解耦

## 7. 数据分析扩展架构

你后续计划增加的数据分析模块，建议按以下链路设计。

### 7.1 在线数据采集层

位置建议：

- `src/service/数据同步`
- 新增 `src/service/数据分析`
- 新增 `src/domain/analysis`
- 新增 `src/db/analysis_*_repository.py`

职责：

- 从天天基金及相关接口同步历史净值、估值、交易、账户资产快照
- 将原始明细和清洗结果写入 MySQL 在线库

### 7.2 离线数仓层

建议链路：

1. 在线 MySQL 存放最新和业务实时数据
2. 阿里云 DataWorks 定时同步到离线分析库
3. 离线库按主题建宽表、汇总表、特征表

建议主题：

- 基金净值主题
- 指标主题
- 用户交易主题
- 策略执行主题
- 收益归因主题

### 7.3 机器学习分析层

建议职责：

- 从离线库读取特征数据
- 训练风格识别、择时评分、波动预警、回撤风险模型
- 输出结构化分析结果，回写分析库或 MySQL 分析表

建议模块位置：

- `src/analysis` 或独立仓库
- 训练任务与在线交易逻辑物理隔离

### 7.4 BI 展示层

建议输出到 Quick BI 的数据主题：

- 策略收益趋势
- 基金筛选指标排行
- 用户组合分布
- 定投计划表现
- 风险预警结果
- 机器学习评分结果

## 8. 推荐目录演进方案

为了兼容现有结构并平滑演进，建议目录继续保持以下原则：

- `API`：只放第三方接口访问
- `service`：只放复用能力和领域服务
- `bussiness`：只放策略编排
- `task`：只放定时入口
- `db`：只放数据库访问实现
- `domain`：只放模型和接口
- `analysis`：后续独立承接离线分析和机器学习

可逐步演进为：

```text
src/
  API/
  service/
  bussiness/
  task/
  scheduled_tasks/
  db/
  domain/
  analysis/              # 新增，承接特征计算与模型调用
  common/
  web_api/
```

## 9. 稳定性治理建议

为保证系统长期稳定，建议持续执行以下规则：

- 所有外部接口异常统一转换为项目内部异常类型
- 定时任务入口必须有 unit test 覆盖
- 配置、凭据、账号信息全部移到环境变量或本地忽略文件
- 新增业务策略时，先补 `task -> bussiness -> service` 的调用关系说明
- 重要任务执行结果必须落库并可追踪
- 分析链路与交易链路隔离，避免分析任务影响交易稳定性

## 10. 测试策略

建议测试分三层：

- unit tests：默认执行，覆盖配置加载、事件解析、策略入口、执行器、核心纯逻辑
- integration tests：显式开启，覆盖真实基金 API、数据库、FC 调用
- manual verification：只保留少量真实账号验证场景，不写入正式业务代码

当前项目已经采用 `test/unit` 作为默认快速回归入口，后续新增重构应优先补这层测试。
