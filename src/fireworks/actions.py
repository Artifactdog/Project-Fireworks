from __future__ import annotations

from typing import Protocol, TypeVar

from .world.repository import WorldRepository, WorldTransaction

Result = TypeVar("Result", covariant=True)


class Action(Protocol[Result]):
    """A validated engine action executable inside one world transaction."""

    def execute(self, transaction: WorldTransaction) -> Result: ...


class ActionEngine:
    """Runs one Action as one atomic canonical-world transaction.

    This layer deliberately does not define gameplay Actions. Player/Director intent
    will later resolve to project/module-owned Action implementations before reaching
    this boundary.
    """

    def __init__(self, world: WorldRepository) -> None:
        self.world = world

    def execute(self, action: Action[Result]) -> Result:
        with self.world.transaction() as transaction:
            return action.execute(transaction)
