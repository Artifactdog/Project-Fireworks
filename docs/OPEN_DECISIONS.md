# Open Decisions

These choices are intentionally **not** decided yet. Agents must not silently lock them in.

Accepted decisions are recorded under `docs/decisions/`.

## Immediate implementation decisions
- Exact outer `DirectorDecision` schema, including multi-Action sequencing/commit semantics, narration, clarifications, and procedural-content proposals.
- Exact policy that populates each request's allowed Director Action scope.
- Exact Python minor-version compatibility/support policy; the initial CI job exercising Python 3.14 does not settle this.
- Exact runtime AI provider/model for early real-AI tests.
- Exact model adapter/protocol implementation beyond the provider-neutral Fireworks Action proposal contract.
- Exact hosting/deployment environment.
- Exact authentication/account implementation for the first multiplayer release.
- Exact perception/communication subsystems that produce recipient-scoped Perspective contributions.
- Exact final wording of the Green Star opening prose; current implementation copy is draft pending Artifactdog approval.

## Game/simulation decisions still open
- Final genre/world setting and lore beyond currently accepted canonical facts.
- Why/how the city of Fireworks is always night and what broader world implications that has.
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
