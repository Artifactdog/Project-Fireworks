# Canonical World Model

Status: accepted conceptual architecture

Decision date: 2026-09-03

## Decision

Project Fireworks uses a generic, typed world model built around persistent entities, typed components, typed relations, current authoritative state, event history, explicit knowledge/belief state, and computed perspective.

### Entity
An Entity is a persistent thing that needs stable identity, history, relationships, or references.

Examples include a person, location, specific item, organization, vehicle, phone, or other future concept that needs identity.

Not every value is an Entity. Simple descriptive values such as height, battery percentage, or a display name normally remain component data unless they later require their own identity/history.

### Component
Components hold typed, versioned structured data attached to an Entity.

Components are module-owned and schema-validated. They are not arbitrary AI-authored JSON. New modules may introduce new component types without redefining the core Entity concept.

The current preference is that component payloads may be stored in a flexible structured form such as JSON behind validation, but the exact SQL/storage representation remains a separate implementation decision.

### Relation
Relations are typed connections between Entities. Relation types are module-owned and validated, and may declare semantic constraints such as exclusivity, directionality, and allowed endpoints.

Examples include physical location, ownership, employment, membership, or future module-defined relationships.

### Current state and event history
Current authoritative state is stored directly and is what the running game queries.

Meaningful state changes also produce durable Events recording what happened. Fireworks is not a full event-sourced architecture: the game must not need to replay all history to reconstruct normal current state.

### Knowledge and belief
Character-specific knowledge/belief state is modeled explicitly where needed so the engine can distinguish canonical truth from what an individual character knows, suspects, believes, or has learned.

The exact representation of knowledge/belief records remains a separate implementation decision.

### Perspective
Perspective is primarily a computed, temporary view built from canonical state, character knowledge/beliefs, physical presence, communication connections, permissions, and other perception rules.

The runtime Director receives only the perspective/context it is allowed to see rather than direct unrestricted database access.

## Mutation boundary

AI and ordinary gameplay code must not mutate component payloads or relations arbitrarily.

Low-level validated state operations may exist, but player/game behavior should normally route through higher-level game actions that validate rules, perform state changes transactionally, and record resulting events.

## Durability goal

This model is intended to allow future mechanics and concepts to be added as modules without replacing the project foundation. New mechanics may require new code, component types, relation types, actions, and validators, but should not require rebuilding identity, persistence, history, AI boundaries, or multiplayer state semantics.

## Explicitly not decided by this decision

This decision does not yet define:

- the exact SQLite table layout;
- the exact component payload encoding;
- the schema-validation library or format;
- the exact metadata required for every component type;
- the exact metadata required for every relation type;
- the exact event record schema;
- the exact knowledge/belief record schema;
- migration mechanics;
- module registration/loading mechanics.
