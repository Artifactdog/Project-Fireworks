from __future__ import annotations

from dataclasses import dataclass

from fireworks.world import EpistemicWorldRepository, WorldInvariantError

FIREWORKS_CITY_ID = "b848af3b-8501-4b63-b232-184857bfed88"
GREEN_STAR_ID = "78d4872f-3f19-442f-8c7a-f889412e66f5"
GREEN_STAR_MAIN_BAR_ID = "fc2ad1c0-c863-4fcb-934f-78ca9dc8de86"
GREEN_STAR_RESTROOM_ID = "042f5c6f-34ca-47b4-880a-900dff77df25"


@dataclass(frozen=True, slots=True)
class OpeningCopy:
    intro: str
    appearance_prompt: str
    name_prompt: str
    completion_template: str


# Draft authored copy for Artifactdog review. The mechanics do not depend on the wording.
OPENING_COPY = OpeningCopy(
    intro=(
        "Outside, Fireworks is night, as it always is. Green Star keeps it soft around the edges: "
        "dark wood, low comfortable light, a few restrained strips of color glowing where they do not "
        "need to announce themselves. You have already had a drink at the bar. Enough to sit with yourself "
        "for a while. Enough to decide you need water.\n\n"
        "You leave the bar behind and step into Green Star's restroom. It is public, ungendered, cleaner and "
        "nicer than it has any obligation to be. You brace your hands against the sink and wash your face. "
        "Water runs cold over your skin. For a few seconds, that is all there is.\n\n"
        "Then you straighten up.\n\n"
        "There is a body in the mirror. Your brain starts doing what brains do: connecting fragments, assigning "
        "meaning, fabricating something coherent enough to call reality. Little by little, the person looking "
        "back at you begins to become you."
    ),
    appearance_prompt="What do you look like? Describe the person taking shape in the mirror.",
    name_prompt=(
        "The face has settled, but one thing still feels strangely detached from it: the name. You look yourself "
        "in the eye, as if saying it might help the rest of you click into place. What name do you say to the mirror?"
    ),
    completion_template=(
        '"{name}."\n\nYou say it out loud to the mirror. The sound hangs there for a moment while you try to make '
        "sense of how that sequence of letters and sounds belongs to the person staring back at you."
    ),
)


def _ensure_location(world: EpistemicWorldRepository, entity_id: str, display_name: str) -> None:
    if not world.entity_exists(entity_id):
        world.create_entity(entity_id)
        world.set_component(entity_id, "core.location", {})
        world.set_component(entity_id, "core.display_name", {"name": display_name})
        return

    location = world.component(entity_id, "core.location")
    name = world.component(entity_id, "core.display_name")
    if location is None or name is None:
        raise WorldInvariantError(
            f"Authored Green Star Entity {entity_id!r} exists without its required canonical Components."
        )
    if name.payload != {"name": display_name}:
        raise WorldInvariantError(
            f"Authored Green Star Entity {entity_id!r} has unexpected display-name state."
        )


def _directed_relation_exists(
    world: EpistemicWorldRepository,
    type_id: str,
    source_entity_id: str,
    target_entity_id: str,
) -> bool:
    return any(
        relation.source_entity_id == source_entity_id
        and relation.target_entity_id == target_entity_id
        for relation in world.relations_for(source_entity_id, type_id)
    )


def _undirected_relation_exists(
    world: EpistemicWorldRepository,
    type_id: str,
    first_entity_id: str,
    second_entity_id: str,
) -> bool:
    expected = {first_entity_id, second_entity_id}
    return any(
        {relation.source_entity_id, relation.target_entity_id} == expected
        for relation in world.relations_for(first_entity_id, type_id)
    )


def seed_green_star(world: EpistemicWorldRepository) -> None:
    """Idempotently seed the currently established canonical opening locations."""

    _ensure_location(world, FIREWORKS_CITY_ID, "Fireworks")
    _ensure_location(world, GREEN_STAR_ID, "Green Star")
    _ensure_location(world, GREEN_STAR_MAIN_BAR_ID, "Green Star / Main Bar")
    _ensure_location(world, GREEN_STAR_RESTROOM_ID, "Green Star / Restroom")

    if not _directed_relation_exists(world, "core.contains", FIREWORKS_CITY_ID, GREEN_STAR_ID):
        world.add_relation("core.contains", FIREWORKS_CITY_ID, GREEN_STAR_ID)
    if not _directed_relation_exists(world, "core.contains", GREEN_STAR_ID, GREEN_STAR_MAIN_BAR_ID):
        world.add_relation("core.contains", GREEN_STAR_ID, GREEN_STAR_MAIN_BAR_ID)
    if not _directed_relation_exists(world, "core.contains", GREEN_STAR_ID, GREEN_STAR_RESTROOM_ID):
        world.add_relation("core.contains", GREEN_STAR_ID, GREEN_STAR_RESTROOM_ID)
    if not _undirected_relation_exists(
        world,
        "core.directly_reachable",
        GREEN_STAR_MAIN_BAR_ID,
        GREEN_STAR_RESTROOM_ID,
    ):
        world.add_relation(
            "core.directly_reachable",
            GREEN_STAR_MAIN_BAR_ID,
            GREEN_STAR_RESTROOM_ID,
        )
