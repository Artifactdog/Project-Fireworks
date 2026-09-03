# Project Fireworks Constitution

Status: foundational, agreed principles

## Purpose
Project Fireworks is intended to be a very long-lived, continuously expandable, text-based game/universe rather than a one-shot released campaign.

It should support at least one player and may support a small number of simultaneous players. Multiplayer must preserve coherent shared reality while allowing players to have private perceptions and private communication.

## Core principles

### 1. Ellie retains authorship
AI assists with development and runtime direction, but does not become the author of the universe by default.

Consequential creative and architectural decisions belong to Ellie. AI-generated content is allowed only within explicit authority boundaries.

### 2. Text is the primary interface
The project should remain usable through text input and text output. Natural language is the main interaction mode.

Deterministic commands may exist as precision/utility shortcuts, but the project should not require a complex GUI to function.

Presentation may become richer later, but UI complexity must not become a prerequisite for the game itself.

### 3. One coherent shared world
The live universe has one canonical reality. Persistent entities may not simultaneously occupy contradictory canonical states.

Examples of invariants:
- A persistent person cannot be physically present in two exclusive physical locations at once.
- An exclusively owned item cannot simultaneously have two exclusive owners.
- Unreleased content may not leak into the live world.
- A player may only perceive information their character can plausibly access through presence, communication, knowledge, or another explicit mechanism.

### 4. AI is not canonical state
Runtime AI interprets intent, directs allowed procedural material, plays NPCs, and narrates outcomes.

It must not directly write arbitrary canonical facts or mutations. Important changes go through engine-defined validated operations.

### 5. Model/provider independence
Neither the runtime Director nor the developer workflow may require a particular AI model/provider.

Provider/model-specific capabilities may be used behind adapters, but Fireworks semantics must remain project-owned and portable.

### 6. Modularity
New systems should be addable without requiring the original project to have predicted every future concept.

The core should expose stable primitives/interfaces. Features should be isolated into modules where practical. Removal/deprecation/migration must be possible without pretending historical events never happened.

### 7. Persistence and archival survival
The live runtime store is an implementation detail, not the only representation of the universe.

The project must eventually be exportable to documented, open formats so its world, entities, events, authored material, and history remain intelligible even if the original software stack disappears.

### 8. Staging and experimentation
Unreleased content and experimental systems must be testable without contaminating live player progression.

The architecture should support:
- Live: released canonical universe.
- Staging: unreleased content/systems with isolated state.
- Sandbox: disposable test copies/experiments.

### 9. Cheap operation
Development should make maximal use of Ellie's existing ChatGPT/Codex subscription.

Runtime AI should be designed for very cheap models and minimal token use. Expensive models must never be architectural requirements.

### 10. Grow from a small real prototype
The first release should prove the architecture with a small coherent world instead of attempting the final simulation immediately.
