# Green Star Opening and Character Establishment

Status: accepted design; exact prose remains draft

Decision date: 2026-09-04

## First canonical scene

The first playable Fireworks scene is canonical rather than disposable demo content.

The opening takes place in the city of **Fireworks**, where it is always night. The cause and larger world explanation are not established by this decision.

The opening venue is **Green Star**, a cozy bar with a wood-heavy feel, very dim comfortable lighting, and restrained colored/RGB light accents.

Green Star includes a public, fancy, non-gendered restroom.

The opening character has already had a drink at the bar. They leave the Main Bar for the Restroom, wash their face at the sink, straighten up, and look into the mirror.

## Player-created characters

Fireworks does not begin with one fixed authored player character. A new player establishes their own character during the mirror sequence.

The mirror scene intentionally creates only what is needed at the beginning:

1. the player freely describes how the character looks;
2. Fireworks preserves that initial appearance description as durable character state;
3. the player supplies the character's name;
4. the character says that name aloud to the mirror;
5. character creation is complete for the opening slice.

Gender, apparent age, clothing, body, hair, and similar information may naturally be expressed inside the freeform appearance description. The first implementation does not force those details into separate form fields or pretend to infer a complete RPG character sheet.

Backstory, history, personality, skills, and other character lore are not required during this creation sequence. They may emerge or be established later through play and future systems.

## Spatial granularity

Green Star is a venue-level Location, while **Green Star / Main Bar** and **Green Star / Restroom** are distinct contained Locations.

The general spatial principle is that Fireworks records a separate Location when crossing that boundary changes meaningful gameplay facts such as presence, perception, communication, or available interactions. It does not model every coordinate or every few steps as a Location.

The Main Bar and Restroom are directly reachable from one another for this opening slice. This does not settle future travel duration, travel mode, interruption, encounter, or pathfinding mechanics.

## First deterministic Director slice

The first executable opening uses a zero-cost deterministic Director only to prove the provider-neutral Action boundary.

The first freeform appearance input becomes a proposal for `character.establish_appearance` v1. The next input becomes a proposal for `character.establish_name` v1. Trusted engine state supplies the acting character identity.

The opening cutscene also performs `core.move` v1 from Green Star / Main Bar to Green Star / Restroom so canonical physical location and Event history are exercised immediately.

## Authored prose

Atmospheric prose is a core presentation goal, with dialogue able to become prominent where scenes call for it.

The exact opening wording currently stored in the implementation is **draft copy for Artifactdog review**. Merging the mechanics must not be interpreted as approval of assistant-invented wording unless Artifactdog explicitly accepts that copy.
