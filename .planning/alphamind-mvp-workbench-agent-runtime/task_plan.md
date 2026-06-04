# Task Plan: AlphaMind MVP Workbench Agent Runtime

## Goal

Use the approved superpowers implementation plan to build the Phase 1 AlphaMind MVP workbench: Vite + React frontend, FastAPI backend, SQLite task/report/session storage, SSE deep research progress, report browsing, current page context, and Agent Runtime foundations.

## Source Of Truth

- Design spec: `docs/superpowers/specs/2026-06-03-alphamind-mvp-workbench-agent-runtime-design.md`
- Implementation plan: `docs/superpowers/plans/2026-06-03-alphamind-mvp-workbench-agent-runtime.md`
- Design commit: `2d3283c docs: 添加MVP工作台与Agent Runtime设计`
- Implementation plan commit: `b54bb28 docs: 添加MVP工作台实施计划`

## Current Phase

Phase 6 Task 8 Vite workbench frontend shell complete; next Phase 6 Task 9 frontend API wiring

## Execution Rule

Each agent must read this file, `findings.md`, `progress.md`, the implementation plan, and `git status --short` before starting work. Each agent must update `progress.md` before handing off. When a task phase completes, update the status below and record the commit hash.

## Phases

### Phase 0: Execution Tracking Setup

- [x] Create `.planning/alphamind-mvp-workbench-agent-runtime/`
- [x] Create `task_plan.md`
- [x] Create `findings.md`
- [x] Create `progress.md`
- [x] Set `.planning/.active_plan`
- **Status:** complete

### Phase 1: Backend Dependencies And Server Skeleton

- [x] Execute implementation plan Task 1
- [x] Verify `/Users/hcy/Desktop/file/AlphaMind/.venv/bin/python -m pytest tests/server/test_app_factory.py -v`
- [x] Commit `feat: 添加FastAPI服务骨架` (`0c15777`)
- **Status:** complete

### Phase 2: SQLite Persistence Layer

- [x] Execute implementation plan Task 2
- [x] Verify `/Users/hcy/Desktop/file/AlphaMind/.venv/bin/python -m pytest tests/server/test_db_repositories.py -v`
- [x] Verify `/Users/hcy/Desktop/file/AlphaMind/.venv/bin/python -m pytest tests/server/test_app_factory.py tests/server/test_db_repositories.py -v`
- [x] Commit `feat: 添加SQLite持久化层` (`4192a37`)
- [x] Address Task 2 quality review: enable SQLite foreign keys, add stable repository ordering, and expand repository regression coverage
- **Status:** complete

### Phase 3: Report And Research Services

- [x] Execute implementation plan Task 3
- [x] Execute implementation plan Task 4
- [x] Verify report service and research service tests
- [x] Commit service-layer changes (`3524a8e feat: 添加投研服务层`)
- [x] Address Phase 3 quality review: reuse shared rating parsing, move active task gate into an atomic repository transaction, and reuse report summary extraction in `default_runner`
- **Status:** complete

### Phase 4: FastAPI Routes

- [x] Execute implementation plan Task 5
- [x] Verify API tests and app factory tests
- [x] Commit `feat: 添加工作台API路由` (`aedcf1c`)
- [x] Address Task 5 quality review: unknown research SSE tasks and invalid agent/runtime sessions return 404, and AgentService is shared through app state with the injected research service
- [x] Address Task 5 quality re-review: missing Agent session message reads now return 404 instead of an empty 200 response (`d42cae4`)
- **Status:** complete

### Phase 5: Agent Runtime And Tools

- [x] Execute implementation plan Task 6
- [x] Address Task 6 code quality review: deep research intent now takes precedence over generic report summary keywords
- [x] Execute implementation plan Task 7
- [x] Verify Agent Runtime core tests
- [x] Verify Agent Runtime tool tests
- [x] Commit Agent Runtime core changes
- [x] Commit Agent Runtime tool wiring changes
- [x] Address Task 7 code quality review: deep research service conflicts now return failed tool cards instead of Agent API 500s
- **Status:** complete

### Phase 6: Vite Workbench Frontend

- [x] Execute implementation plan Task 8
- [ ] Execute implementation plan Task 9
- [ ] Execute implementation plan Task 10
- [x] Verify `npm run build` from `frontend/`
- [x] Commit frontend shell changes
- **Status:** Task 8 complete; Task 9 and Task 10 pending

### Phase 7: Documentation And Final Verification

- [ ] Execute implementation plan Task 11
- [ ] Verify backend tests
- [ ] Verify frontend build
- [ ] Smoke run FastAPI app
- [ ] Smoke run Vite app
- [ ] Commit docs update
- **Status:** pending

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Treat `docs/superpowers/plans/...` as the implementation source of truth | Avoid duplicating or drifting from the approved plan |
| Use `.planning/...` only for execution tracking and handoff | Keeps status, findings, failures, test results, and commits visible across agents |
| Keep Streamlit as legacy during Phase 1 | Approved MVP scope says not to delete `web/` yet |
| Require commit hashes in handoff records | Prevents agents from claiming completion without durable git evidence |

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|
| Expected RED failure: `ModuleNotFoundError: No module named 'fastapi'` | 1 | Added backend dependencies and installed them into the shared venv with `uv pip install --python /Users/hcy/Desktop/file/AlphaMind/.venv/bin/python ...` |
| `/Users/hcy/Desktop/file/AlphaMind/.venv/bin/python -m pip` unavailable because the venv has no `pip` module | 1 | Used `/Users/hcy/.local/bin/uv pip install --python /Users/hcy/Desktop/file/AlphaMind/.venv/bin/python ...` |
| Expected RED failure: `ModuleNotFoundError: No module named 'server.db'` | 1 | Added Task 2 SQLite connection, schema, repositories, and shared Pydantic schemas |
| Expected RED failures: SQLite foreign key not enforced and same-second repository ordering unstable | 1 | Enabled `PRAGMA foreign_keys = ON` per connection and added deterministic order tie-breakers for reports, active tasks, and agent messages |
| Task 3 first RED attempt could not find `tests/server/test_report_service.py` because the patch was initially applied outside the isolated worktree | 1 | Removed the mistaken file from the main checkout and re-applied the test file using an absolute path inside `.worktrees/mvp-workbench-agent-runtime` |
| Expected RED failure: `ModuleNotFoundError: No module named 'server.services'` | 1 | Added `server/services/__init__.py` and `server/services/report_service.py` |
| Expected RED failure: `ModuleNotFoundError: No module named 'server.services.research_service'` | 1 | Added `server/services/research_service.py` |
| Expected Phase 3 quality RED failures: signal extraction, atomic task creation helper, service helper usage, and default-runner summary consistency | 1 | Reused `parse_rating`, added `create_research_task_if_none_active` with `BEGIN IMMEDIATE`, updated `ResearchService.create_task`, and reused `extract_summary` |
| Task 5 quality RED exposed an unknown task SSE loop and missing shared AgentService app state | 1 | Added route-level existence checks, repository/session service lookup, and `app.state.agent_service` initialized with shared `research_service` |
| Expected Task 6 RED failure: `ModuleNotFoundError: No module named 'alphamind.agent_runtime'` | 1 | Added the minimal `alphamind.agent_runtime` package with runtime orchestration, intent routing, context types, tool registry, and Phase 1 extension-point stubs |
| Task 6 review RED failure: mixed report-analysis prompt routed to `report_summary` before `deep_research` | 1 | Added branch coverage and prioritized explicit deep research keywords before generic report summary keywords |
| Task 7 review RED failure: `DeepResearchTool.run()` surfaced `RuntimeError` from `create_task()` / `start_task()` as an Agent API 500 | 1 | Added Agent API regression coverage and returned a failed `deep_research` tool card so the assistant message is persisted |
| First Task 8 `npm install` was manually terminated after a long silent wait while npm was in `reify` cleanup | 1 | Re-ran `npm install`; dependencies completed successfully and `npm run build` passed |
| Task 8 `npm audit` reports 2 moderate findings through Vite 5 / esbuild, with npm's suggested fix requiring a breaking Vite 8 upgrade | 1 | Left versions aligned with the approved Task 8 plan and recorded the constraint in `findings.md` for later dependency-upgrade work |

## Handoff Checklist

Every agent handoff must include:

- Completed phase/task/steps.
- Files created or modified.
- Tests run and exact results.
- Commit hash, if committed.
- Open issues or blockers.
- Recommended next phase/task/step.
