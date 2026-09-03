# Open Decisions

These choices are intentionally **not** decided yet. Agents must not silently lock them in.

Accepted decisions are recorded under `docs/decisions/`.

## Immediate implementation decisions
- Exact Live / Staging / Sandbox storage-isolation mechanism (for example separate SQLite databases versus one database with explicit environment scoping).
- Exact SQLite table layout and mutation API for persistent Entity / Component / Relation current state.
- Exact Event and Knowledge persistence layouts and Perspective-construction pipeline.
- Exact migration framework and persistent-schema evolution workflow.
- Exact runtime AI provider/model for early real-AI tests.
- Exact model adapter/protocol implementation.
- Exact hosting/deployment environment.
- Exact authentication/account implementation for the first multiplayer release.

## Game/simulation decisions still open
- Final genre/world setting and lore.
- Whether permanent night is a literal world rule, aesthetic framing, or temporary prototype simplification.
- Exact canonical-time model and advancement rules.
- Travel mechanics and interruption frequency.
- Multiplayer action-scene/beat rules.
- Exact skill/competency representation.
- Injury/combat/death simulation details.
- Final permadeath policy and succession after death.
- Exact procedural-generation authority tiers.
- Exact player-created/requested-content policy.

## Deliberately deferred features
- rich GUI;
- vehicle simulation;
- detailed combat;
- large procedural city simulation;
- full mission generator;
- sophisticated archival/wiki UI;
- multiple active characters per player.
