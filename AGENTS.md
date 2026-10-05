# Project guide

- Read `_docs/plan.md` and `backlog.md` before changing behavior.
- Follow `_docs/process.md`: one task, meaningful tests, then a small commit.
- Preserve the starter's web UI, API and SQLite storage. This homework adds observability, not new product features.
- Manage Python dependencies with uv and commit `uv.lock`.
- Run `uv run --frozen pytest -q` before committing code.
- Keep metric labels low-cardinality: route template and status, never order IDs.
- Keep secrets, databases, agent session streams and local runtime files out of Git.
- Review incident evidence before committing it. Preserve actual responses; never invent successful runs.
- Incident agents may change application code and regression tests. They must not commit, push, deploy, edit telemetry/alert rules or read credentials.

## Commands

- `uv sync --frozen` — install dependencies.
- `uv run --frozen pytest -q` — offline tests.
- `docker compose up --build -d --wait` — start the local stack.
- `docker compose down` — stop it while keeping data.

