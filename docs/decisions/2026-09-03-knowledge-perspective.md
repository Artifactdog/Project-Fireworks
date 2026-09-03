# Knowledge, Belief, and Perspective

Status: accepted

Decision date: 2026-09-03

## World truth versus character belief

Canonical world truth and character belief are separate systems. A character may know something, suspect something, doubt it, reject it, or hold an incorrect belief without changing canonical reality.

Persistent character-specific information is stored as **Epistemic Records**. The core does not assume that records are true, mutually consistent, or complete.

## Typed epistemic claims

Epistemic claims are project/module-owned types using the same stable namespaced ID, positive integer schema version, and JSON Schema validation model as Components, Relations, and Events.

Epistemic data is structured rather than stored as arbitrary prose. Runtime AI may consume rendered prose later, but the durable underlying claim remains typed and validated.

The generic core does not attempt to infer which two records represent the same proposition. Multiple active records of the same claim type may coexist, including contradictory records. Modules/Actions explicitly replace or remove records when their own semantics require it.

## Certainty

The foundational certainty vocabulary is semantic rather than numeric:

- `certain`
- `believed`
- `suspected`
- `doubted`
- `rejected`

Fireworks does not assign arbitrary floating-point belief probabilities as core semantics.

## Provenance and staleness

An Epistemic Record may carry an `as_of_event_sequence` referring to the Event whose information it is based on. When present, that Event must exist in the same world.

The record does not automatically update when canonical truth changes later. This permits safe statements such as “last known location” without leaking a character's current location.

Authored/bootstrap beliefs may exist without Event provenance; runtime Actions can attach provenance when appropriate.

## Persistence and atomicity

Storage revision 3 adds the `epistemic_records` table to the revision-2 state/Event store.

Epistemic mutations use the same SQLite transaction as ordinary world state and Events. Therefore an Action may atomically record what happened and what a character learned from it. The existing Action Engine rule still applies: a state-changing Action, including an epistemic change, must record at least one Event or the transaction is rolled back.

Older revision-2 repository code refuses to open a revision-3 knowledge-enabled world instead of silently ignoring epistemic state.

## Perspective

Perspective is computed, temporary, and character-scoped. It is not a second canonical universe and is not persisted as world state.

A Perspective consists of:

- the holder's persistent Epistemic Records (memory/belief);
- transient recipient-scoped contributions from future perception, communication, or public-information subsystems.

Transient contributions use registered epistemic claim schemas and are filtered by recipient before entering the Perspective.

The PerspectiveBuilder deliberately has no interface for querying arbitrary canonical Components or Relations. It consumes only character-scoped epistemic reads plus already recipient-scoped contributions.

## Director boundary

The runtime Director must receive Perspective-derived context and perspective-safe tools rather than an omniscient world repository. Creator/Developer authority may remain omniscient.

Who perceives or learns information is determined by engine/module systems before the Director call. The Director may narrate the result but must not invent additional recipients or bypass the information boundary.

## Still open

This decision does not define exact eyesight/hearing rules, spatial perception, whisper mechanics, phone/radio behavior, rumor propagation, public-news propagation, or the final Director-facing context/tool schema.
