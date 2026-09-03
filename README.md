# Project Fireworks

Project Fireworks is a long-lived, modular, text-first persistent game/universe.

This repository is the canonical source for its code, project-owned AI instructions, design decisions, contracts, and durable documentation.

## Development

The initial server stack is Python + FastAPI + SQLite. The accepted decision is documented in `docs/decisions/2026-09-03-initial-implementation-stack.md`.

Create a virtual environment and install the development dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

On Windows, activate the environment with `.venv\Scripts\activate` instead.

Run the server:

```bash
uvicorn fireworks.app:app --app-dir src --reload
```

By default, local runtime data is stored under `data/`. Override the SQLite path with the `FIREWORKS_DB_PATH` environment variable.

Run tests:

```bash
pytest
```

## Versioning

When Project Fireworks needs an explicit version identifier, it uses `YYYY.M.D.N` without zero-padding the month or day. The first release on a date uses iteration `0`; subsequent releases that day increment the final number.

This matches the versioning convention used by Artifactdog's Rubies project. Semantic versions such as `v0.1` or `v1.0` are not used.
