# Atomic Actions and Event History

Status: accepted

Decision date: 2026-09-03

## Atomic world changes

One logical game Action must commit all of its canonical state changes and Event records in one SQLite transaction.

`WorldTransaction` is the low-level all-or-nothing mutation boundary. It exposes validated Entity / Component / Relation operations plus Event append. If any operation or validator fails, the entire transaction rolls back.

The runtime Director must not receive arbitrary `WorldTransaction` access. The intended future flow is:

`intent -> project/module Action -> validation -> WorldTransaction -> state + Event commit`

## Action Engine

The initial `ActionEngine` is deliberately thin. It only guarantees that an already-resolved Action executes inside one `WorldTransaction`.

A state-changing Action must append at least one Event in the same transaction. If it changes canonical state without recording any Event, the Action Engine treats that as a contract violation and rolls the transaction back. Read-only Actions may complete without an Event.

Actual gameplay Action definitions, their input schemas, authority rules, and Director-facing proposal format remain separate decisions.

## Event history

Events are append-only historical records. Current state remains stored directly; Events do not replace it.

Every Event type is project/module-owned and follows the same stable namespaced ID + positive integer schema-version + JSON Schema validation model as Components and Relations.

Each persisted Event contains:

- an opaque Event ID;
- a monotonically increasing sequence number assigned by SQLite within that world instance;
- a namespaced Event type ID;
- an Event schema version;
- a validated JSON payload;
- a UTC technical/audit timestamp (`recorded_at_utc`).

The Event sequence establishes durable order/causality. The UTC timestamp is not canonical in-world time. Fireworks' world-time model remains undecided.

## Storage migrations

Persistent storage uses an explicit positive integer storage-schema revision and ordered project-owned migrations from revision `N` to `N+1`.

Migrations are ordinary reviewed code, run transactionally, and must fail closed when a required migration path is unavailable. Fireworks does not use automatic schema diffing as canonical migration semantics.

Storage revision 2 adds the Event table to revision 1 while preserving existing Entity / Component / Relation data.
