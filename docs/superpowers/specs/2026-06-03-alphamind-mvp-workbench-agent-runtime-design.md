# AlphaMind MVP 工作台与 Agent Runtime 设计

日期：2026-06-03

## 目标

将 AlphaMind 从当前 Streamlit 投研 Demo 改造成可扩展的 MVP 工作台。第一阶段重点不是自动交易，而是建立新的前后端架构、Agent Runtime 基座、深度投研任务闭环和报告查看能力，为后续因子挖掘、回测、模拟交易、订单管理接入留下稳定接口。

## 核心决策

- 前端使用 Vite + React，新建 `frontend/`。
- 后端使用 FastAPI，新建 `server/`。
- 存储第一版使用 SQLite。
- 用户第一版使用默认用户模式，但所有核心数据预留 `user_id`、`workspace_id`、`session_id`。
- 深度投研进度使用 SSE 推送。
- Agent UI 使用右下角小球，点击展开右侧抽屉。
- 当前 `web/` Streamlit 作为 legacy 入口保留，等新前端覆盖后再移除。
- 第一版只接入深度投研和报告总结；因子、回测、订单、复盘模块只做导航灰态和后续接口预留。

## 总体架构

```text
frontend/           Vite + React 工作台
server/             FastAPI API 服务
alphamind/          现有核心能力 + 新增 Agent Runtime
web/                legacy Streamlit，暂时保留
```

职责划分：

- `frontend/` 负责模块导航、深度投研页面、报告页面、Agent 小球/抽屉、SSE 进度展示和灰态未来模块入口。
- `server/` 负责 HTTP API、深度投研任务管理、报告索引、Agent 会话、SSE 事件流和 SQLite 持久化。
- `alphamind/` 保留现有 LangGraph 深度投研能力，新增 `agent_runtime`，后续扩展 `factor`、`backtest`、`trading`。
- `web/` 不再作为主前端，但暂时保留现有可用入口。

关键边界：

```text
Agent 是编排层。
业务模块是能力层。
API 是访问层。
前端是展示层。
```

Agent 不直接拥有因子、回测、订单或投研逻辑，而是通过工具调用对应服务。

## 第一版功能范围

第一版实现：

- Vite 工作台基础布局。
- FastAPI 服务。
- SQLite 任务、报告、Agent 会话索引。
- 深度投研任务创建、状态查询、SSE 进度推送。
- 历史报告列表和报告详情。
- 报告详情按流程 Tab 查看各阶段内容。
- Agent 小球和右侧抽屉。
- Agent 读取当前页面上下文。
- Agent 总结当前报告、当前 Tab 和历史报告。
- Agent 启动深度投研任务。
- 默认用户和默认工作区。

第一版不实现：

- 完整登录注册。
- 完整多租户。
- 因子挖掘。
- 策略回测。
- 订单、持仓、模拟盘。
- 自动交易。
- 复杂长期记忆。
- 复杂任务队列。
- 深度投研任务取消。
- 删除 Streamlit。

## 前端布局

左侧导航：

```text
Deep Research       可用
Reports             可用
Factor Lab          灰态
Strategy Lab        灰态
Paper Trading       灰态
Orders & Positions  灰态
Review & Analytics  灰态
Settings            可用
```

页面：

- `/deep-research`：股票代码/名称输入、分析日期、模型配置入口、启动深度投研、SSE 进度展示、完成后打开报告。
- `/reports`：历史报告列表、筛选、报告详情。
- `/settings`：LLM provider/model 配置、默认用户/工作区信息、数据目录信息。

灰态模块点击后展示 Coming Soon 或规划说明，不接 API，不进入真实业务流。

## 报告详情

报告详情页采用流程化 Tab 展示，不做一页式长报告。

顶部摘要区：

- 股票代码和名称。
- 分析日期。
- 最终信号。
- 任务状态。
- 生成时间。
- Agent 总结入口。

流程 Tabs：

```text
市场分析
舆情分析
新闻分析
基本面分析
政策分析
游资/资金流
解禁/减持
多空辩论
交易计划
风控辩论
最终决策
```

每个 Tab 展示摘要、关键结论和可展开原文。最终决策 Tab 要重点展示结构化摘要，并提供 `final_trade_decision` 原文查看。

报告详情页需要向 Agent 上报当前页面上下文：

```json
{
  "page": "report_detail",
  "context": {
    "active_report_id": "r_123",
    "active_tab": "final_decision",
    "ticker": "300750",
    "trade_date": "2026-06-03",
    "signal": "Hold"
  }
}
```

## Agent Runtime

目录建议：

```text
alphamind/agent_runtime/
├── runtime.py
├── session.py
├── router.py
├── planner.py
├── context/
│   ├── manager.py
│   ├── types.py
│   └── providers/
│       ├── page.py
│       ├── session.py
│       ├── user.py
│       ├── report.py
│       ├── task.py
│       └── memory.py
├── memory.py
├── tools/
│   ├── base.py
│   ├── registry.py
│   ├── deep_research.py
│   └── report_summary.py
├── skills/
│   ├── base.py
│   └── registry.py
└── mcp/
    └── adapter.py
```

`AgentContextManager` 管理 Agent 推理所需的完整上下文，不等同于当前页面内容。当前页面只是上下文来源之一。

上下文来源：

- `PageContextProvider`：当前页面、选中股票、报告 ID、任务 ID、当前 Tab。
- `SessionContextProvider`：当前会话、最近消息。
- `UserContextProvider`：默认 `user_id`、`workspace_id`。
- `ReportContextProvider`：当前报告和报告索引。
- `TaskContextProvider`：正在运行或最近完成的任务。
- `MemoryContextProvider`：短期记忆；长期记忆后续扩展。

第一版真正实现：

- `AgentRuntime`。
- `AgentContextManager`。
- `ShortTermMemory`。
- `ToolRegistry`。
- `DeepResearchTool`。
- `ReportSummaryTool`。

第一版仅预留：

- `Planner` 的复杂多步规划。
- `SkillRegistry`。
- `MCPAdapter`。
- 长期记忆。

工具输出统一结构：

```json
{
  "tool_name": "deep_research",
  "status": "accepted",
  "task_id": "task_xxx",
  "message": "已创建深度投研任务"
}
```

## Agent 抽屉

收起态：

- 右下角小球。
- 如果有深度投研任务运行，显示轻量进度标识。

展开态：

- 消息列表。
- 当前上下文提示，例如 `正在查看 300750 / 最终决策`。
- 工具调用卡片。
- 输入框。

第一版 Agent 能做：

- 普通问答。
- 总结当前报告。
- 总结当前 Tab。
- 解释最终决策和风控观点。
- 查询并总结历史报告。
- 启动深度投研任务。

第一版 Agent 不能做：

- 因子挖掘。
- 回测。
- 订单查询。
- 模拟下单。
- 自动交易。
- 自动修改配置。
- 自动执行复杂多步任务。

Agent 工具权限：

- 自动允许读取当前页面上下文、读取报告、总结报告、创建深度投研任务。
- 未来运行批量回测、创建模拟交易、修改策略、下单类动作必须增加用户确认。

## API 设计

第一版 API 分组：

```text
Research API
Reports API
Agent API
Runtime Context API
```

接口草案：

```text
POST /api/research/tasks
GET  /api/research/tasks/{task_id}
GET  /api/research/tasks/{task_id}/events

GET  /api/reports
GET  /api/reports/{report_id}

POST /api/agent/sessions
GET  /api/agent/sessions/{session_id}
POST /api/agent/sessions/{session_id}/messages

PUT  /api/runtime/page-context
GET  /api/runtime/page-context
```

`PUT /api/runtime/page-context` 只保存当前页面最新状态，不保存页面切换历史。第一版不做累计 activity history。

## SQLite 数据模型

第一版表：

```text
users
- id
- display_name
- created_at

workspaces
- id
- user_id
- name
- created_at

research_tasks
- id
- user_id
- workspace_id
- ticker
- trade_date
- status
- progress_stage
- error_message
- failed_stage
- report_id
- created_at
- updated_at

research_reports
- id
- user_id
- workspace_id
- ticker
- trade_date
- signal
- summary
- state_path
- created_at

agent_sessions
- id
- user_id
- workspace_id
- title
- created_at
- updated_at

agent_messages
- id
- session_id
- role
- content
- tool_calls_json
- created_at

page_contexts
- id
- session_id
- user_id
- workspace_id
- page
- context_json
- updated_at
```

默认身份：

```text
user_id = default_user
workspace_id = default_workspace
```

这些默认值只是 MVP 运行方式，数据模型仍为后续多用户扩展预留。

## 深度投研任务接入

第一版复用现有 `AlphaMindGraph` 和结果文件结构，不重写 LangGraph 流程。

推荐链路：

```text
server/api/research.py
→ server/services/research_service.py
→ AlphaMindGraph.propagate() 或 stream 执行
→ 现有 results_dir 保存 full_states_log_*.json
→ SQLite 保存任务索引和报告索引
```

报告正文仍保存在现有结果目录：

```text
results_dir/{ticker}/AlphaMindStrategy_logs/full_states_log_{trade_date}.json
```

SQLite 保存：

- `report_id`
- `ticker`
- `trade_date`
- `signal`
- `state_path`
- `summary`
- `user_id`
- `workspace_id`

注意事项：

- 不让 FastAPI 依赖 Streamlit session state。
- `web/runner.py` 只能作为参考，任务服务应迁到 `server/services/research_service.py`。
- 任务状态独立建模：`pending`、`running`、`completed`、`failed`。
- 每个阶段完成后写入 SSE 事件。
- 报告 ID 使用 UUID，不使用文件路径作为主键。
- 失败任务记录 `error_message` 和失败阶段。
- 第一版同一默认用户限制同时最多运行一个深度投研任务。
- 第一版不实现取消任务。

SSE 事件格式：

```json
{
  "event": "research_progress",
  "task_id": "task_xxx",
  "status": "running",
  "stage": "market",
  "message": "市场分析完成",
  "payload": {}
}
```

## 后续模块接入方式

后续因子、回测、订单都按同一模式扩展：

```text
独立业务模块
→ 服务层
→ API 层
→ Agent Tool 包装层
→ 前端模块展示
```

示例：

```text
alphamind/factor/
server/services/factor_service.py
server/api/factors.py
alphamind/agent_runtime/tools/factor_analysis.py
frontend/src/features/factors/
```

回测：

```text
alphamind/backtest/
server/services/backtest_service.py
server/api/backtests.py
alphamind/agent_runtime/tools/backtest.py
frontend/src/features/backtests/
```

交易和订单：

```text
alphamind/trading/
server/services/order_service.py
server/api/orders.py
alphamind/agent_runtime/tools/order.py
frontend/src/features/trading/
```

这样页面调用和 Agent 调用走同一套业务能力，避免逻辑分叉。

## 扩展路线

Phase 1：新工作台与 Agent 基座

- Vite + FastAPI + SQLite。
- 深度投研任务。
- 报告列表和详情。
- Agent 小球/抽屉。
- 当前页面上下文。
- `ReportSummaryTool` 和 `DeepResearchTool`。

Phase 2：因子研究模块

- `alphamind/factor`。
- 因子注册、计算、评估。
- Factor Lab 页面。
- `FactorAnalysisTool` 接入 Agent。

Phase 3：策略回测模块

- `alphamind/backtest`。
- 策略配置、回测任务、绩效指标。
- Strategy Lab 页面。
- `BacktestTool` 接入 Agent。

Phase 4：模拟交易与订单管理

- `alphamind/trading`。
- 模拟账户、订单、成交、持仓、权益。
- Orders & Positions 页面。
- `PostTradeReviewTool` 接入 Agent。

Phase 5：Agent 完整增强

- `SkillRegistry`。
- 多步 `Planner`。
- 长期记忆。
- MCP Adapter。
- 外部工具和数据源。
- 权限确认流。

## 验收标准

- 新前端可启动并访问 Deep Research、Reports、Settings。
- 灰态模块展示但不可进入真实业务。
- FastAPI 可创建深度投研任务。
- 前端可通过 SSE 查看深度投研进度。
- 深度投研完成后生成报告索引，并兼容现有 `results_dir` 文件。
- Reports 页面可按流程 Tab 查看报告内容，并能查看最终决策原文。
- Agent 小球可展开抽屉。
- Agent 能读取当前页面上下文。
- Agent 能总结当前报告或当前 Tab。
- Agent 能启动深度投研任务。
- SQLite 数据中包含默认用户、默认工作区、任务、报告、Agent 会话和页面上下文。
- Streamlit legacy 入口仍可保留使用。
