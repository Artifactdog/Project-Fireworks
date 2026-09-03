"""Project-owned world model primitives, type registry, persistence, and transactions."""

from .registry import TypeRegistry
from .repository import (
    ComponentRecord,
    EntityAlreadyExistsError,
    EntityNotFoundError,
    EntityRecord,
    EventRecord,
    RelationRecord,
    StorageSchemaError,
    WorldInvariantError,
    WorldRepository,
    WorldStateError,
    WorldTransaction,
)
from .types import (
    ComponentTypeDefinition,
    EventTypeDefinition,
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
    "EventRecord",
    "EventTypeDefinition",
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
    "WorldTransaction",
]
