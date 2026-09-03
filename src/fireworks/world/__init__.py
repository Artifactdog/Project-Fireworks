"""Project-owned world model primitives, type registry, and persistence boundary."""

from .registry import TypeRegistry
from .repository import (
    ComponentRecord,
    EntityAlreadyExistsError,
    EntityNotFoundError,
    EntityRecord,
    RelationRecord,
    StorageSchemaError,
    WorldInvariantError,
    WorldRepository,
    WorldStateError,
)
from .types import (
    ComponentTypeDefinition,
    RelationTypeDefinition,
    TypeDefinitionError,
    TypeNotRegisteredError,
    TypePayloadError,
)

__all__ = [
    "ComponentRecord",
    "ComponentTypeDefinition",
    "EntityAlreadyExistsError",
    "EntityNotFoundError",
    "EntityRecord",
    "RelationRecord",
    "RelationTypeDefinition",
    "StorageSchemaError",
    "TypeDefinitionError",
    "TypeNotRegisteredError",
    "TypePayloadError",
    "TypeRegistry",
    "WorldInvariantError",
    "WorldRepository",
    "WorldStateError",
]
