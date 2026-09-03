import pytest

from fireworks.world import (
    ComponentTypeDefinition,
    RelationTypeDefinition,
    TypeDefinitionError,
    TypePayloadError,
    TypeRegistry,
)


IDENTITY_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "age": {"type": ["integer", "null"], "minimum": 0},
    },
    "required": ["name"],
    "additionalProperties": False,
}

EMPTY_OBJECT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
}


def test_component_payload_must_match_registered_schema() -> None:
    registry = TypeRegistry()
    registry.register_component(
        ComponentTypeDefinition(
            type_id="person.identity",
            schema_version=1,
            schema=IDENTITY_SCHEMA,
        )
    )

    definition = registry.validate_component_payload(
        "person.identity", {"name": "Nadia", "age": 31}
    )

    assert definition.schema_version == 1

    with pytest.raises(TypePayloadError):
        registry.validate_component_payload(
            "person.identity", {"name": "Nadia", "invented_by_ai": True}
        )


def test_latest_registered_schema_version_is_used_by_default() -> None:
    registry = TypeRegistry()
    registry.register_component(
        ComponentTypeDefinition(
            type_id="person.identity",
            schema_version=1,
            schema=IDENTITY_SCHEMA,
        )
    )
    registry.register_component(
        ComponentTypeDefinition(
            type_id="person.identity",
            schema_version=2,
            schema=IDENTITY_SCHEMA,
        )
    )

    assert registry.component("person.identity").schema_version == 2
    assert registry.component("person.identity", 1).schema_version == 1


def test_type_ids_are_namespaced_and_definitions_cannot_be_redefined() -> None:
    registry = TypeRegistry()

    with pytest.raises(TypeDefinitionError):
        registry.register_component(
            ComponentTypeDefinition(
                type_id="identity",
                schema_version=1,
                schema=IDENTITY_SCHEMA,
            )
        )

    definition = ComponentTypeDefinition(
        type_id="person.identity",
        schema_version=1,
        schema=IDENTITY_SCHEMA,
    )
    registry.register_component(definition)

    with pytest.raises(TypeDefinitionError):
        registry.register_component(definition)


def test_relation_definition_carries_endpoint_and_cardinality_rules() -> None:
    registry = TypeRegistry()
    registry.register_relation(
        RelationTypeDefinition(
            type_id="core.physical_location",
            schema_version=1,
            payload_schema=EMPTY_OBJECT_SCHEMA,
            directional=True,
            source_requires=frozenset({"core.physical"}),
            target_requires=frozenset({"core.location"}),
            max_from_source=1,
        )
    )

    definition = registry.validate_relation_payload("core.physical_location", {})

    assert definition.source_requires == frozenset({"core.physical"})
    assert definition.target_requires == frozenset({"core.location"})
    assert definition.max_from_source == 1


def test_non_directional_relation_rules_must_be_symmetric() -> None:
    registry = TypeRegistry()

    with pytest.raises(TypeDefinitionError):
        registry.register_relation(
            RelationTypeDefinition(
                type_id="social.knows",
                schema_version=1,
                payload_schema=EMPTY_OBJECT_SCHEMA,
                directional=False,
                source_requires=frozenset({"person.identity"}),
                target_requires=frozenset(),
            )
        )
