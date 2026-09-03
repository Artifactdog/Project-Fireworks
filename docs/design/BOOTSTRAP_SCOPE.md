# Bootstrap Scope

This document describes what the first implementation phase should prove without overcommitting the final design.

## The bootstrap should prove
- the repository/instruction workflow works across interchangeable developer AIs;
- game state can be authoritative and separate from AI narration;
- natural-language input can eventually map to validated operations;
- state changes can produce durable events;
- a player perspective can be distinct from canonical omniscient state;
- live/staging/sandbox separation can be represented cleanly;
- runtime model integration can sit behind a provider-neutral adapter;
- Director and Creator/Developer roles can remain permission-isolated even when powered by the same underlying model.

## The bootstrap should not prematurely solve
- the final city/world;
- final combat balance;
- final travel/time system;
- final UI;
- final hosting;
- final AI provider;
- every possible future entity/system concept.

## Success criterion
The first playable prototype should be small enough to understand end-to-end and structured well enough that adding a new module does not require rewriting the core.
