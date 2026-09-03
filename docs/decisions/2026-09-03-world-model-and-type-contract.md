# World Model and Type Contract

Status: accepted

Decision date: 2026-09-03

## Core world model

Project Fireworks represents persistent reality using a small project-owned model:

- **Entity**: a thing that needs stable identity, references, relationships, or independent history.
- **Component**: typed, versioned structured data attached to an Entity.
- **Relation**: a typed, versioned connection between Entities.
- **Current state**: stored directly and used by the running engine.
- **Event history**: an immutable historical record of meaningful changes; it does not replace directly stored current state.
- **Knowledge / belief**: persistent character-specific information will be modeled explicitly.
- **Perspective**: a temporary view computed from canonical state, knowledge, presence, communication, permissions, and other applicable rules rather than a second canonical universe.

Not every value is an Entity. Ordinary descriptive values remain Component data unless they independently need identity, relationships, or history.

## Component type contract

A Component type is project/module-defined and must have:

- a stable namespaced type ID, such as `person.identity`;
- a positive integer schema version;
- a language-neutral JSON Schema describing the stored payload;
- at most one instance of that Component type on a given Entity (singleton semantics);
- optional module code for semantic validation that cannot reasonably be expressed by schema alone.

If several independently meaningful things of the same general concept need to exist, prefer modeling them as Entities and connecting them with Relations instead of introducing arbitrary repeated Component instances.

## Relation type contract

A Relation type is project/module-defined and must have:

- a stable namespaced type ID;
- a positive integer schema version;
- directional or non-directional semantics;
- endpoint requirements describing what Components the connected Entities must have, where applicable;
- cardinality/exclusivity limits where applicable;
- an optional typed JSON payload with its own schema;
- optional module code for deeper semantic validation.

A simple relationship remains a Relation. If the relationship itself needs substantial independent state, identity, relationships, or history, promote it to an Entity.

## Authority and validation

Type definitions belong to version-controlled project/modules in Git. Runtime AI may use registered types but may not invent or redefine type semantics on the fly.

Malformed Component or Relation payloads must be rejected before reaching canonical persistence. Deeper validators and game actions may impose stricter rules than the structural schemas.

## Storage direction

SQLite is the current persistence implementation. Component and Relation payloads may be stored as structured JSON inside SQLite while remaining validated against project-owned schemas.

The exact Event and Knowledge persistence layouts, the environment/world isolation mechanism, and the migration framework remain separate decisions.
