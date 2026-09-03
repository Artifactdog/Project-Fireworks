from __future__ import annotations

from typing import Protocol, TypeVar

from .world.repository import WorldRepository, WorldTransaction

Result = TypeVar("Result", covariant=True)


class ActionContractError(RuntimeError):
    """An Action violated the engine's atomic-history contract."""


class Action(Protocol[Result]):
    """A validated engine action executable inside one world transaction."""

    def execute(self, transaction: WorldTransaction) -> Result: ...


class ActionEngine:
    """Runs one Action as one atomic canonical-world transaction.

    Gameplay Action schemas and Director-facing proposal semantics remain separate.
    A state-changing Action must append at least one Event in the same transaction.
    """

    def __init__(self, world: WorldRepository) -> None:
        self.world = world

    def execute(self, action: Action[Result]) -> Result:
        with self.world.transaction() as transaction:
            connection = transaction._connection
            changes_before = connection.total_changes
            events_before = connection.execute("SELECT COUNT(*) AS count FROM events").fetchone()[
                "count"
            ]

            result = action.execute(transaction)

            events_after = connection.execute("SELECT COUNT(*) AS count FROM events").fetchone()[
                "count"
            ]
            event_delta = events_after - events_before
            total_delta = connection.total_changes - changes_before
            state_delta = total_delta - event_delta

            if state_delta > 0 and event_delta == 0:
                raise ActionContractError(
                    "State-changing Actions must append at least one Event in the same transaction."
                )
            return result
