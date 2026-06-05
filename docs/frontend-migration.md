# 前端迁移规划

AlphaMind 当前的 `web/` 是 Streamlit 实现，适合快速验证投研流程和报告展示。后续如果替换为 React 或 Vue，建议按分层迁移，不要直接在新前端复刻 Streamlit 的 session state。

## 当前边界

- `alphamind/`：核心能力，包含 Agent、LangGraph 编排、数据源、LLM client。
- `cli/`：命令行入口。
- `web/`：当前 Streamlit 外壳，包含页面、进度展示、历史记录、PDF 下载。

## 建议迁移顺序

1. 抽取后端服务层：把 `web/runner.py` 中的分析启动、状态更新、结果保存抽到独立模块，例如 `alphamind/services/analysis.py`。
2. 提供 API 层：新增 FastAPI 或类似服务，暴露任务创建、任务进度、历史报告、PDF 下载接口。
3. 保留 Streamlit 兼容入口：让 `web/` 调用同一套服务层，避免新旧前端逻辑分叉。
4. 新建前端工程：React/Vue 只负责 UI、轮询或 SSE/WebSocket 进度、报告展示。
5. 移除 Streamlit：等新前端覆盖输入、进度、历史、报告、PDF 后，再删除 `web/` 和 `streamlit` 依赖。

## 不建议现在删除

- `web/`：仍是当前可用 UI。
- `web/pdf_export.py`：即使换前端，PDF 生成仍可作为后端下载能力复用。
- `web/history.py`：可以迁移为后端历史记录服务。

## 可以优先抽取

- 分析任务服务：`run_analysis(ticker, trade_date, config)`
- 进度模型：阶段、状态、统计信息
- 报告 DTO：最终状态、信号、耗时、下载文件名
- 历史记录读取：按 ticker/date 查询本地日志

## MVP 工作台落地路径

新的主前端从 `frontend/` 开始，使用 Vite + React。新的 API 服务从 `server/` 开始，使用 FastAPI + SQLite。当前 `web/` Streamlit 入口保留为 legacy，不在第一阶段删除。

第一阶段只迁移深度投研任务、报告列表/详情、Agent 小球/抽屉和当前页面上下文。Factor Lab、Strategy Lab、Paper Trading、Orders & Positions、Review & Analytics 先作为灰态入口展示。
