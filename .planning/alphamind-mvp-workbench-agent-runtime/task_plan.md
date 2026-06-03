# Task Plan: AlphaMind MVP Workbench Agent Runtime

## Goal

Use the approved superpowers implementation plan to build the Phase 1 AlphaMind MVP workbench: Vite + React frontend, FastAPI backend, SQLite task/report/session storage, SSE deep research progress, report browsing, current page context, and Agent Runtime foundations.

## Source Of Truth

- Design spec: `docs/superpowers/specs/2026-06-03-alphamind-mvp-workbench-agent-runtime-design.md`
- Implementation plan: `docs/superpowers/plans/2026-06-03-alphamind-mvp-workbench-agent-runtime.md`
- Design commit: `2d3283c docs: 添加MVP工作台与Agent Runtime设计`
- Implementation plan commit: `b54bb28 docs: 添加MVP工作台实施计划`

## Current Phase

Phase 2: SQLite Persistence Layer (next)

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

- [ ] Execute implementation plan Task 2
- [ ] Verify `pytest tests/server/test_db_repositories.py -v`
- [ ] Commit `feat: 添加SQLite持久化层`
- **Status:** pending

### Phase 3: Report And Research Services

- [ ] Execute implementation plan Task 3
- [ ] Execute implementation plan Task 4
- [ ] Verify report service and research service tests
- [ ] Commit service-layer changes
- **Status:** pending

### Phase 4: FastAPI Routes

- [ ] Execute implementation plan Task 5
- [ ] Verify API tests and app factory tests
- [ ] Commit `feat: 添加工作台API路由`
- **Status:** pending

### Phase 5: Agent Runtime And Tools

- [ ] Execute implementation plan Task 6
- [ ] Execute implementation plan Task 7
- [ ] Verify Agent Runtime and tool tests
- [ ] Commit Agent Runtime changes
- **Status:** pending

### Phase 6: Vite Workbench Frontend

- [ ] Execute implementation plan Task 8
- [ ] Execute implementation plan Task 9
- [ ] Execute implementation plan Task 10
- [ ] Verify `npm run build` from `frontend/`
- [ ] Commit frontend changes
- **Status:** pending

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

## Handoff Checklist

Every agent handoff must include:

- Completed phase/task/steps.
- Files created or modified.
- Tests run and exact results.
- Commit hash, if committed.
- Open issues or blockers.
- Recommended next phase/task/step.
