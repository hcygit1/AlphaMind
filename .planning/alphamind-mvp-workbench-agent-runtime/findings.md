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
| None yet | No implementation work has started |

## Resources

- Design spec: `docs/superpowers/specs/2026-06-03-alphamind-mvp-workbench-agent-runtime-design.md`
- Implementation plan: `docs/superpowers/plans/2026-06-03-alphamind-mvp-workbench-agent-runtime.md`
- Active tracking plan: `.planning/alphamind-mvp-workbench-agent-runtime/task_plan.md`
- Progress log: `.planning/alphamind-mvp-workbench-agent-runtime/progress.md`

## Visual/Browser Findings

- A preview architecture image was generated for review. The conceptual structure was correct, but the rendered text had a small typo around `full_states_log_*.json`, so it should not be treated as a final project artifact yet.

---

Update this file whenever implementation uncovers constraints, failures, dependency conflicts, or changed assumptions.
