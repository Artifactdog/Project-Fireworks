# Project Fireworks — Agent Instructions

This repository is a long-lived, modular, text-first persistent game project co-authored with Ellie.

## Before changing anything
1. Read `docs/PROJECT_CONSTITUTION.md`.
2. Read `docs/DEVELOPMENT_WORKFLOW.md`.
3. Read `docs/OPEN_DECISIONS.md`.
4. Read any design/contract/decision document relevant to the files you will touch.
5. For AI integration or creator tooling, read `docs/design/AI_ROLES.md`.

## Authorship rule
Ellie is the author and final design authority.

Do **not** silently make consequential choices when requirements are ambiguous. A consequential choice includes anything that materially affects player-visible behavior, lore, world rules, architecture, security, recurring cost, persistence semantics, compatibility, or a hard-to-reverse direction.

When a consequential choice is genuinely unresolved, stop before committing that choice and surface the alternatives to Ellie.

Small, reversible, invisible implementation details may be chosen autonomously when necessary. Keep them conventional and document anything non-obvious.

## Durability rule
Prefer simple, boring, documented interfaces over clever coupling. No important Fireworks concept may depend on one LLM provider, one developer agent, one UI, or one hosting vendor.

## State rule
AI may propose actions and narration, but may not directly mutate canonical game state. Canonical mutations must pass through validated game operations.

## Safety rule for development
- Work on a branch for non-trivial changes.
- Add or update tests for invariants and regressions.
- Do not destructively rewrite persistent data without an explicit migration/recovery plan.
- Keep unreleased/staging data isolated from live data.
- Keep exports possible in open, documented formats.

## Documentation rule
This file is a map, not the encyclopedia. Put durable knowledge in `docs/` and keep this file short.
