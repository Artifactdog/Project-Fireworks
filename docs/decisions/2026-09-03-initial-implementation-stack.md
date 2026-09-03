# Initial Implementation Stack

Status: accepted

Decision date: 2026-09-03

## Decision

The first real Project Fireworks implementation uses:

- Python as the server/runtime language;
- FastAPI as the initial HTTP/WebSocket application framework;
- SQLite as the initial runtime persistence engine.

## Why

This stack is intentionally small, inexpensive, portable, and friendly to rapid AI-assisted development. It gives Fireworks a conventional server boundary without making the game depend on a large game engine or hosted platform.

SQLite is an implementation detail rather than the canonical definition of the universe. Fireworks must preserve a storage boundary so another persistence engine can replace it later without redefining game semantics.

FastAPI is likewise infrastructure, not the game model. World state, game operations, AI contracts, and modules must remain project-owned concepts rather than framework-owned concepts.

## Explicitly not decided by this decision

This decision does not define:

- the Entity / Component / Relation / Event / Perspective storage schema;
- the migration framework;
- the exact Python minor-version support policy;
- the final deployment/hosting environment;
- the runtime AI provider;
- authentication/account semantics;
- final frontend behavior.

Those remain separate decisions where applicable.
