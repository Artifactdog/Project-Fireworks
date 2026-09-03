from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, TypeVar

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from .types import (
    ComponentTypeDefinition,
    EpistemicClaimTypeDefinition,
    EventTypeDefinition,
    RelationTypeDefinition,
    TypeDefinitionError,
    TypeNotRegisteredError,
    TypePayloadError,
)

Definition = TypeVar(
    "Definition",
    ComponentTypeDefinition,
    RelationTypeDefinition,
    EventTypeDefinition,
    EpistemicClaimTypeDefinition,
)

_TYPE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)+$")


class TypeRegistry:
    """Registry of project/module-owned world type definitions."""

    def __init__(self) -> None:
        self._components: dict[tuple[str, int], ComponentTypeDefinition] = {}
        self._relations: dict[tuple[str, int], RelationTypeDefinition] = {}
        self._events: dict[tuple[str, int], EventTypeDefinition] = {}
        self._epistemic_claims: dict[tuple[str, int], EpistemicClaimTypeDefinition] = {}

    def register_component(self, definition: ComponentTypeDefinition) -> None:
        self._validate_common_definition(definition.type_id, definition.schema_version)
        self._validate_schema(definition.schema, definition.type_id)
        self._register(self._components, definition)

    def register_relation(self, definition: RelationTypeDefinition) -> None:
        self._validate_common_definition(definition.type_id, definition.schema_version)
        self._validate_schema(definition.payload_schema, definition.type_id)
        self._validate_relation_definition(definition)
        self._register(self._relations, definition)

    def register_event(self, definition: EventTypeDefinition) -> None:
        self._validate_common_definition(definition.type_id, definition.schema_version)
        self._validate_schema(definition.schema, definition.type_id)
        self._register(self._events, definition)

    def register_epistemic_claim(self, definition: EpistemicClaimTypeDefinition) -> None:
        self._validate_common_definition(definition.type_id, definition.schema_version)
        self._validate_schema(definition.schema, definition.type_id)
        self._register(self._epistemic_claims, definition)

    def component(self, type_id: str, version: int | None = None) -> ComponentTypeDefinition:
        return self._get(self._components, type_id, version)

    def relation(self, type_id: str, version: int | None = None) -> RelationTypeDefinition:
        return self._get(self._relations, type_id, version)

    def event(self, type_id: str, version: int | None = None) -> EventTypeDefinition:
        return self._get(self._events, type_id, version)

    def epistemic_claim(
        self, type_id: str, version: int | None = None
    ) -> EpistemicClaimTypeDefinition:
        return self._get(self._epistemic_claims, type_id, version)

    def validate_component_payload(
        self,
        type_id: str,
        payload: Mapping[str, Any],
        version: int | None = None,
    ) -> ComponentTypeDefinition:
        definition = self.component(type_id, version)
        self._validate_payload(definition.schema, payload, type_id)
        return definition

    def validate_relation_payload(
        self,
        type_id: str,
        payload: Mapping[str, Any],
        version: int | None = None,
    ) -> RelationTypeDefinition:
        definition = self.relation(type_id, version)
        self._validate_payload(definition.payload_schema, payload, type_id)
        return definition

    def validate_event_payload(
        self,
        type_id: str,
        payload: Mapping[str, Any],
        version: int | None = None,
    ) -> EventTypeDefinition:
        definition = self.event(type_id, version)
        self._validate_payload(definition.schema, payload, type_id)
        return definition

    def validate_epistemic_claim_payload(
        self,
        type_id: str,
        payload: Mapping[str, Any],
        version: int | None = None,
    ) -> EpistemicClaimTypeDefinition:
        definition = self.epistemic_claim(type_id, version)
        self._validate_payload(definition.schema, payload, type_id)
        return definition

    @staticmethod
    def _validate_common_definition(type_id: str, schema_version: int) -> None:
        if not _TYPE_ID_PATTERN.fullmatch(type_id):
            raise TypeDefinitionError(
                f"Type ID {type_id!r} must be a lowercase namespaced ID such as 'core.identity'."
            )
        if schema_version < 1:
            raise TypeDefinitionError("Schema versions are positive integers starting at 1.")

    @staticmethod
    def _validate_schema(schema: Mapping[str, Any], type_id: str) -> None:
        try:
            Draft202012Validator.check_schema(dict(schema))
        except SchemaError as exc:
            raise TypeDefinitionError(f"Invalid JSON Schema for {type_id!r}: {exc.message}") from exc

    @staticmethod
    def _validate_relation_definition(definition: RelationTypeDefinition) -> None:
        for label, value in (
            ("max_from_source", definition.max_from_source),
            ("max_to_target", definition.max_to_target),
        ):
            if value is not None and value < 1:
                raise TypeDefinitionError(f"{label} must be a positive integer or None.")

        if not definition.directional:
            if definition.source_requires != definition.target_requires:
                raise TypeDefinitionError(
                    "Non-directional Relations must use the same Component requirements at both endpoints."
                )
            if definition.max_from_source != definition.max_to_target:
                raise TypeDefinitionError(
                    "Non-directional Relations must use the same cardinality limit at both endpoints."
                )

    @staticmethod
    def _register(registry: dict[tuple[str, int], Definition], definition: Definition) -> None:
        key = (definition.type_id, definition.schema_version)
        if key in registry:
            raise TypeDefinitionError(
                f"Type {definition.type_id!r} version {definition.schema_version} is already registered."
            )
        registry[key] = definition

    @staticmethod
    def _get(
        registry: dict[tuple[str, int], Definition],
        type_id: str,
        version: int | None,
    ) -> Definition:
        if version is not None:
            try:
                return registry[(type_id, version)]
            except KeyError as exc:
                raise TypeNotRegisteredError(
                    f"Type {type_id!r} version {version} is not registered."
                ) from exc

        candidates = [
            definition
            for (candidate_type_id, _), definition in registry.items()
            if candidate_type_id == type_id
        ]
        if not candidates:
            raise TypeNotRegisteredError(f"Type {type_id!r} is not registered.")
        return max(candidates, key=lambda definition: definition.schema_version)

    @staticmethod
    def _validate_payload(
        schema: Mapping[str, Any],
        payload: Mapping[str, Any],
        type_id: str,
    ) -> None:
        try:
            Draft202012Validator(dict(schema)).validate(dict(payload))
        except ValidationError as exc:
            location = ".".join(str(part) for part in exc.absolute_path)
            suffix = f" at {location}" if location else ""
            raise TypePayloadError(
                f"Invalid payload for {type_id!r}{suffix}: {exc.message}"
            ) from exc
