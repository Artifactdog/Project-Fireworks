# Registered Actions and Director Proposals

Status: accepted

Decision date: 2026-09-03

## Registered Actions

Director-proposable game Actions are project/module-owned definitions registered with Fireworks code.

Each Action definition has:

- a stable lowercase namespaced type ID;
- a positive integer schema version;
- a human/model-facing description;
- a JSON Schema describing its input arguments;
- a project/module-owned factory that constructs the executable Action from trusted engine context plus validated arguments.

Action definitions are immutable by `(type_id, schema_version)` within one registry. A changed contract receives a new integer schema version rather than silently changing the meaning of an existing version.

The generic Action registry does not define gameplay semantics or authority policy. Individual Actions still validate canonical world conditions while executing inside `WorldTransaction`.

## Provider-neutral Action proposal

The canonical Director-facing proposal for one Action is exactly:

```json
{
  "action_type": "core.move",
  "schema_version": 1,
  "arguments": {}
}
```

The proposal envelope does not contain actor identity, repository references, Event records, arbitrary state patches, or provider-specific tool-call metadata.

`schema_version` is required. Fireworks does not silently reinterpret an old or ambiguous proposal using whichever Action version happens to be newest.

Provider adapters may translate native model tool/function calls into this Fireworks-owned proposal shape, but native provider formats are not canonical project semantics.

## Trusted actor context

The acting character Entity ID is supplied by trusted engine/session state in `ActionExecutionContext`. It is never accepted from Director model output.

This prevents a Director from escalating authority by changing an `actor_entity_id` field in its proposal.

Additional trusted execution context may be added later only when a real engine requirement exists.

## Per-request Action scope

The engine supplies each Director request with an explicit set of allowed `(action_type, schema_version)` references.

Only those exact Actions may be proposed and executed for that request. Registration alone does not make an Action available to the Director.

The Director may receive safe `DirectorActionOffer` descriptions containing the Action ID, exact version, description, and argument schema. The factories, `ActionEngine`, `WorldRepository`, and `WorldTransaction` are never exposed to the model.

The policy that decides which Actions belong in a particular request's allowed scope remains a separate gameplay/authority decision.

## Validation and execution

The write-side flow is:

`Director output -> proposal-envelope validation -> allowed-scope check -> registered argument-schema validation -> Action construction with trusted context -> ActionEngine -> WorldTransaction -> state + Event`

Malformed envelopes, unknown versions, schema-invalid arguments, and out-of-scope Actions are rejected before canonical mutation.

World-dependent validation remains inside Action execution so it runs against current canonical state inside the atomic transaction.

## One proposal versus a full Director decision

This decision defines one Action proposal only.

It does not yet decide whether a future `DirectorDecision` may contain zero, one, or several Action proposals, how several proposals would be ordered/committed, or how narration, clarifications, unsupported-intent feedback, and procedural-content proposals are wrapped around them.
