# Runtime AI Director Contract

Status: foundational interface contract; implementation details still open

## Goal
The Runtime Director is interchangeable. Fireworks must be able to replace one model/provider with another without changing canonical world semantics.

## Director responsibilities
The Director may:
- interpret natural-language player intent;
- request relevant world information through approved read tools;
- propose one or more game operations;
- play/narrate NPC behavior within granted authority;
- narrate validated results from the perspective supplied by the engine;
- generate low-impact procedural material when policy explicitly permits it;
- report unsupported player intents for creator review.

## Director prohibitions
The Director may not:
- directly mutate canonical state;
- invent authoritative state that conflicts with engine-provided facts;
- reveal information outside the supplied perspective/knowledge boundary;
- silently create high-impact canon outside explicit authority;
- assume model-specific hidden memory is canonical project memory;
- access Creator/Developer tools or authority because it happens to share an underlying model with that role.

## Adapter boundary
Each model/provider integration must implement the same Fireworks-owned conceptual interface.

Conceptually:

`DirectorRequest -> DirectorDecision`

A request should contain only the context needed for the current decision, such as:
- player input;
- actor identity;
- perspective-visible state;
- relevant known facts;
- allowed operations/tools;
- authority limits;
- current scene/context;
- applicable rules.

A decision should be validated project-owned structured data, conceptually including:
- interpreted intent;
- proposed operations;
- requested clarifications only when genuinely needed;
- narration plan/output;
- procedural facts proposed under explicit authority;
- unsupported-intent feedback when applicable.

Exact schemas are intentionally not fixed yet.

## Model compatibility
Do not rely on one provider's proprietary tool-calling semantics as the canonical representation.

Provider adapters may translate between native model features and Fireworks-owned request/decision schemas.

If a model cannot reliably produce the required structure, the adapter may use validation, constrained decoding, repair, retry, or reject/fallback behavior. Canonical state must never accept malformed model output.

## Conformance tests
The project should eventually maintain a provider-independent Director conformance suite containing representative scenarios such as:
- simple movement;
- unavailable action;
- private information;
- two-player co-presence;
- phone communication;
- conflicting player request versus canonical state;
- low-impact procedural generation;
- prohibited high-impact canon creation.

A new Director/provider is usable only if it meets the required contract sufficiently for the selected runtime role.
