# Persistent World State

Status: accepted

Decision date: 2026-09-03

## Environment isolation

Each running world/environment instance uses its own SQLite database file.

Live, Staging, and disposable Sandboxes therefore do not share tables distinguished by an environment column. Crossing an environment boundary requires deliberately opening, cloning, importing, or exporting another database.

This is a safety boundary: staging and sandbox operations cannot mutate Live unless code is explicitly given the Live database.

## Current-state storage

The initial canonical current-state store uses three generic world tables:

- `entities`: stable persistent identities;
- `components`: singleton typed/versioned Component payloads attached to Entities;
- `relations`: typed/versioned connections between Entities with optional payloads.

Component and Relation payloads are stored as JSON text inside SQLite and must validate against registered project/module-owned schemas before mutation.

Entity identifiers and Relation record identifiers are opaque UUIDs by default. Human-readable names are ordinary world data, not database identity.

## Mutation boundary

The world repository is a low-level engine boundary, not an AI tool surface and not the final player-action API.

It must:

- validate registered Component and Relation types before persistence;
- enforce singleton Component semantics;
- enforce Relation endpoint requirements and cardinality constraints;
- use SQLite transactions so validation and mutation are atomic;
- enable foreign-key integrity;
- reject contradictory state instead of relying on AI behavior to avoid it.

Higher-level game actions such as movement, transfer, calls, missions, or combat will eventually orchestrate these lower-level mutations and record Events.

## Schema evolution

The database records an internal storage-schema revision so incompatible stores can be detected. The complete migration framework and migration policy remain a separate decision.

## Deliberately not included yet

This decision does not define:

- Event persistence;
- Knowledge/belief persistence;
- Perspective construction;
- final migration tooling;
- authored module/content loading;
- player-facing or Director-facing action APIs.
