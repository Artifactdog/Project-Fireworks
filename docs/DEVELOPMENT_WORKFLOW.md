# Development Workflow

Status: foundational

## Roles

### Artifactdog
- Final author and design authority.
- Chooses consequential behavior, creative direction, and hard-to-reverse architecture when alternatives materially affect the project.

### Developer AI
May be Sol/ChatGPT, Codex, or another capable agent.

Responsibilities:
- inspect the repository and relevant project documentation;
- propose designs and implementation changes;
- implement approved work;
- preserve architecture and invariants;
- add tests and documentation;
- surface consequential ambiguity rather than silently resolving it.

The developer AI is interchangeable. No critical workflow may depend on hidden memory from one specific agent.

### AI roles
Fireworks has distinct AI roles with distinct authority, but they do not require distinct underlying models.

At minimum:
- **Director role**: runtime world/game role with tightly constrained game tools.
- **Creator/Developer role**: privileged project-development role that may inspect and modify project material only through explicit development tooling and workflow.

The same model/provider may power both roles, or different models/providers may be selected independently. Context, tools, permissions, and audit trails must remain isolated between roles. Player input must never gain creator/developer privileges.

The built-in Creator Mode may eventually become a primary development interface, but it must remain a frontend to ordinary Git-controlled source code rather than the only way Fireworks can be developed.

See `docs/contracts/RUNTIME_DIRECTOR_CONTRACT.md` and `docs/contracts/DEVELOPER_AI_CONTRACT.md`.

## Source of truth
Repository content is the durable project memory.

Use:
- `AGENTS.md` as a short agent entry point;
- `docs/PROJECT_CONSTITUTION.md` for foundational rules;
- `docs/OPEN_DECISIONS.md` for unresolved design forks;
- `docs/decisions/` for accepted decision records;
- `docs/contracts/` for stable interfaces;
- code/tests for executable truth.

Chat history is useful context but must not be the only place a durable project rule exists.

## Decision policy

### Ask Artifactdog before choosing
Ask before committing a choice that materially changes:
- player-visible behavior;
- lore/canon;
- player authority or freedom;
- world simulation semantics;
- runtime AI authority;
- architecture or long-term coupling;
- persistence/migration behavior;
- security/privacy;
- recurring cost;
- public compatibility/protocols;
- other hard-to-reverse choices.

### May choose autonomously
Ordinary reversible implementation details that do not shape the project may be chosen without interruption, for example:
- local variable/function names;
- test helper organization;
- conventional formatting;
- tiny refactors required by existing architecture.

If uncertain, treat the choice as consequential.

## Git workflow
Non-trivial changes should be isolated on branches and reviewed before becoming stable/released code.

Prefer small commits with a single purpose. Avoid large opaque rewrites.

Experiments should be easy to discard.

## Versioning
When an explicit Fireworks version identifier is needed, use `YYYY.M.D.N` with no zero-padding for month or day. The first release on a date is iteration `0`; subsequent releases on that date increment the final number. Do not use semantic-version labels such as `v0.1` or `v1.0`.

## Tests
Every discovered invariant violation should become a regression test where practical.

High-value invariant examples:
- no contradictory exclusive locations;
- no contradictory exclusive ownership;
- AI cannot commit a rejected operation;
- private information cannot leak to unrelated players;
- staging cannot mutate live state;
- unreleased content cannot appear in live state.
