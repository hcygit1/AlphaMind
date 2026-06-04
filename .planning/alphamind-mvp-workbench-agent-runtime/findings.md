# Findings & Decisions: AlphaMind MVP Workbench Agent Runtime

## Requirements

- Build Phase 1 MVP only.
- Use Vite + React in `frontend/`.
- Use FastAPI in `server/`.
- Use SQLite for task/report/session/page-context indexes.
- Use default user mode while preserving `user_id`, `workspace_id`, and `session_id`.
- Use SSE for deep research progress.
- Use Agent small ball plus right-side drawer.
- Preserve `web/` Streamlit as legacy.
- First Agent tools are limited to deep research task creation and report summarization.
- Factor, backtest, trading, order, long-term memory, MCP, and full skill workflows are future phases.

## Research Findings

- Current repository already has the approved design spec and implementation plan committed.
- Current `.gitignore` does not ignore `.planning/`, so this execution tracking directory can be committed for multi-agent handoff.
- `requirements.txt` currently contains only `.`, while Python dependencies are managed in `pyproject.toml`.
- Existing report files are stored under `results_dir/{ticker}/AlphaMindStrategy_logs/full_states_log_{trade_date}.json`.
- Existing Streamlit code in `web/runner.py` is a reference only; new FastAPI service should not depend on Streamlit session state.
- Implementation is running in isolated worktree `.worktrees/mvp-workbench-agent-runtime` on branch `feat/mvp-workbench-agent-runtime`.
- The isolated worktree does not have `pytest` on PATH. Use `/Users/hcy/Desktop/file/AlphaMind/.venv/bin/python -m pytest ...` for Python test commands unless a local worktree environment is created later.
- Task 1 installed `fastapi==0.136.3`, upgraded `httpx` to `0.28.1`, and added uvicorn extras dependencies into the shared venv via `uv pip install --python /Users/hcy/Desktop/file/AlphaMind/.venv/bin/python ...`.
- FastAPI TestClient currently emits a `StarletteDeprecationWarning` about `httpx` during `tests/server/test_app_factory.py`; the test passes.

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| Use scoped `.planning/alphamind-mvp-workbench-agent-runtime/` instead of root `task_plan.md` | Keeps this project tracking isolated and compatible with multiple active plans |
| Set `.planning/.active_plan` to `alphamind-mvp-workbench-agent-runtime` | Lets future agents discover the active tracking directory automatically |
| Track execution by implementation plan tasks, grouped into phases | Keeps tracking concise while preserving a direct mapping to the detailed plan |
| Commit `.planning` files | Multi-agent handoff is more reliable when the process state is versioned with the repo |

## Issues Encountered

| Issue | Resolution |
|-------|------------|
| `pytest` command not found in isolated worktree | Use `/Users/hcy/Desktop/file/AlphaMind/.venv/bin/python -m pytest ...` from the worktree |
| Shared venv has no `pip` module | Use `/Users/hcy/.local/bin/uv pip install --python /Users/hcy/Desktop/file/AlphaMind/.venv/bin/python ...` for dependency installation |
| SQLite foreign key checks are connection-local and disabled by default | `server.db.connection.connect()` must execute `PRAGMA foreign_keys = ON` on every new connection |
| Repository rows can share second-level `created_at` timestamps | List queries need explicit tie-breakers: reports by `id DESC`, active tasks by `id ASC`, and agent messages by `rowid ASC` to preserve insertion order |
| Report signal extraction can conflict with final decision prose | `server.services.report_service.extract_signal()` must delegate to `alphamind.agents.utils.rating.parse_rating()` so explicit `Rating: X` labels win over earlier rating words in prose |
| Service-level active task checks are not atomic | `ResearchService.create_task()` must call repository-level `create_research_task_if_none_active()`, which uses `BEGIN IMMEDIATE` to check pending/running tasks and insert in one SQLite transaction |
| Runner-created report summaries must match indexed report summaries | `default_runner()` should reuse `extract_summary(final_state)` instead of slicing `final_trade_decision` directly |
| Unknown research SSE task IDs must not enter an empty streaming loop | `GET /api/research/tasks/{task_id}/events` now checks `ResearchService.get_task()` before creating the `StreamingResponse` and returns HTTP 404 when absent |
| Agent message and page-context writes must validate session existence before SQLite writes | Added `get_agent_session()` and `AgentService.get_session()` so routes return HTTP 404 instead of surfacing SQLite foreign key failures as 500 |
| Agent routes need the same shared research service that the app exposes for SSE | `create_app()` now builds `app.state.agent_service` with the injected/shared `app.state.research_service`; agent routes read service instances from request app state |
| Agent session read routes must match write-route session semantics | `GET /api/agent/sessions/{session_id}` now checks session existence and returns HTTP 404 for missing sessions instead of returning an empty message list |
| Agent Runtime intent routing must prioritize explicit deep research requests | Messages containing deep-analysis intent such as `分析一下` or `深度分析` should route to `deep_research` even when they also mention `报告`, so Task 7 does not dispatch mixed report-analysis prompts to `report_summary` |
| Runtime page context from SQLite is stored as `context_json` | `AgentService.handle_message()` normalizes saved page context to also expose `context`, while tools accept either `context` or `context_json`, so direct tool tests and API-sourced context use the same code path |
| Agent tool service conflicts must stay inside tool results | `DeepResearchTool.run()` should catch `RuntimeError` from `ResearchService.create_task()` / `start_task()` and return a failed tool card; otherwise `AgentService.handle_message()` saves the user message but fails before saving the assistant message |
| Task 8 frontend dependency install creates a `package-lock.json` | Commit `frontend/package-lock.json` with the Vite scaffold for reproducible frontend installs; keep `frontend/node_modules/` ignored |
| Task 8 build writes `frontend/dist/` | Keep `frontend/dist/` ignored; production artifacts are generated by `npm run build`, not committed |
| `npm audit` reports 2 moderate frontend findings for Vite 5 via esbuild | `npm audit fix --force` would install Vite 8.0.16, a breaking major upgrade outside Task 8. Current Task 8 keeps the approved Vite 5 plan and passes production build; revisit during a dedicated dependency update |

## Resources

- Design spec: `docs/superpowers/specs/2026-06-03-alphamind-mvp-workbench-agent-runtime-design.md`
- Implementation plan: `docs/superpowers/plans/2026-06-03-alphamind-mvp-workbench-agent-runtime.md`
- Active tracking plan: `.planning/alphamind-mvp-workbench-agent-runtime/task_plan.md`
- Progress log: `.planning/alphamind-mvp-workbench-agent-runtime/progress.md`

## Visual/Browser Findings

- A preview architecture image was generated for review. The conceptual structure was correct, but the rendered text had a small typo around `full_states_log_*.json`, so it should not be treated as a final project artifact yet.

---

Update this file whenever implementation uncovers constraints, failures, dependency conflicts, or changed assumptions.
