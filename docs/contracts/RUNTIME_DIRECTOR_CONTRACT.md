# Runtime AI Director Contract

Status: foundational interface contract; implementation details still open

## Goal
The Runtime Director is interchangeable. Fireworks must be able to replace one model/provider with another without changing canonical world semantics.

## Director responsibilities
The Director may:
- interpret natural-language player intent;
- request relevant information only through approved perspective-safe read tools;
- propose one or more game operations through registered Director Action contracts;
- play/narrate NPC behavior within granted authority;
- narrate validated results from the Perspective supplied by the engine;
- generate low-impact procedural material when policy explicitly permits it;
- report unsupported player intents for creator review.

## Director prohibitions
The Director may not:
- directly mutate canonical state;
- receive arbitrary `WorldRepository` / `WorldTransaction` access;
- query omniscient Components, Relations, Events, or epistemic state outside the current Perspective boundary;
- choose or override the trusted acting character Entity ID in an Action proposal;
- invoke a registered Action that the engine did not explicitly allow for the current request;
- invent authoritative state that conflicts with engine-provided facts;
- reveal information outside the supplied Perspective/knowledge boundary;
- decide that an additional character perceived or learned information when engine/module perception rules did not grant it;
- silently create high-impact canon outside explicit authority;
- assume model-specific hidden memory is canonical project memory;
- access Creator/Developer tools or authority because it happens to share an underlying model with that role.

## Perspective boundary
Before a Director call, Fireworks constructs a temporary character-scoped Perspective.

The Perspective may contain:
- the current character's persistent typed Epistemic Records;
- recipient-scoped current-perception facts;
- recipient-scoped communication facts;
- recipient-scoped public-information facts;
- other information explicitly authorized by engine/module rules.

The Director is not given omitted canonical truth and instructed merely to keep it secret. Information isolation occurs before the model call.

Perspective-safe tools must preserve the same boundary. A Director-side lookup for a character or subject may return known/last-observed information, but must not silently fall through to omniscient current world state.

Creator/Developer tools are a separate authority surface and may be omniscient.

## Registered Action boundary
Director-proposable Actions are project/module-owned contracts registered by stable namespaced type ID and positive integer schema version.

For each request, the engine provides an explicit Action scope containing only the exact `(action_type, schema_version)` pairs currently allowed. Registration alone does not grant Director access to an Action.

A Director-visible Action offer may contain:
- Action type ID;
- exact schema version;
- description;
- JSON Schema for its arguments.

It must not expose Action factories, the Action Engine, repositories, world transactions, or Creator authority.

### Canonical Action proposal
One provider-neutral Director Action proposal is exactly:

```json
{
  "action_type": "core.move",
  "schema_version": 1,
  "arguments": {}
}
```

Actor identity is intentionally absent. Trusted engine/session state supplies the acting character separately.

The exact Action schema version is mandatory. Fireworks does not resolve an omitted version to "latest".

The write-side flow is:

`Director proposal -> envelope validation -> allowed-scope check -> registered argument-schema validation -> Action construction with trusted actor/context -> ActionEngine -> WorldTransaction -> canonical state + Event`

World-dependent Action validation belongs inside the transactional Action execution rather than in model output or a stale preflight check.

Provider-native function/tool calling may be used by adapters, but it must translate to/from this Fireworks-owned Action proposal contract. Provider-native schemas are not canonical semantics.

## Adapter boundary
Each model/provider integration must implement the same Fireworks-owned conceptual interface.

Conceptually:

`DirectorRequest -> DirectorDecision`

A request should contain only the context needed for the current decision, such as:
- player input;
- trusted actor identity;
- Perspective-visible state;
- relevant known facts;
- currently allowed Director Action offers/tools;
- authority limits;
- current scene/context;
- applicable rules.

A decision should be validated project-owned structured data, conceptually including:
- interpreted intent;
- zero or more Action proposals using the canonical proposal shape above;
- requested clarifications only when genuinely needed;
- narration plan/output;
- procedural facts proposed under explicit authority;
- unsupported-intent feedback when applicable.

The exact outer `DirectorDecision` schema, multi-Action sequencing semantics, narration representation, and clarification/procedural-content envelopes are intentionally not fixed yet.

## Model compatibility
Do not rely on one provider's proprietary tool-calling semantics as the canonical representation.

Provider adapters may translate between native model features and Fireworks-owned request/decision schemas.

If a model cannot reliably produce the required structure, the adapter may use validation, constrained decoding, repair, retry, or reject/fallback behavior. Canonical state must never accept malformed model output.

## Conformance tests
The project should eventually maintain a provider-independent Director conformance suite containing representative scenarios such as:
- simple movement;
- unavailable or out-of-scope Action;
- attempted actor-identity override;
- invalid Action arguments;
- private information unavailable to the current character;
- stale last-known information versus newer hidden canonical truth;
- two-player co-presence;
- whisper/private-perception isolation;
- phone communication;
- conflicting player request versus canonical state;
- low-impact procedural generation;
- prohibited high-impact canon creation.

A new Director/provider is usable only if it meets the required contract sufficiently for the selected runtime role.
