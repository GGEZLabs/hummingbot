"""
Domain enums for the Volume Pumper strategy.

These enums represent core domain concepts that are used throughout
the strategy implementation.
"""

from enum import Enum, auto


class StrategyState(Enum):
    """
    Represents the current state of the Volume Pumper strategy.

    State Transitions:
        NOT_INITIALIZED -> RUNNING (after initialization)
        RUNNING -> STOPPED (balance loss threshold breached)
        RUNNING -> UNDERBALANCED (insufficient funds for minimum order)
        RUNNING -> ARCHITECT_COOLDOWN (conflicting orders detected)
        ARCHITECT_COOLDOWN -> RUNNING (cooldown period expired)
    """

    NOT_INITIALIZED = auto()
    """Initial state before strategy setup is complete."""

    RUNNING = auto()
    """Normal operation - actively creating volume and boundary orders."""

    STOPPED = auto()
    """Strategy halted due to balance loss exceeding threshold."""

    UNDERBALANCED = auto()
    """Insufficient balance to place minimum required orders."""

    ARCHITECT_COOLDOWN = auto()
    """Paused due to conflicting external orders in the order book."""


class MovementType(Enum):
    """
    Represents the current market movement direction for phase management.

    The movement type determines how flexible boundaries drift over time:
    - UPWARDS: Boundaries drift upward each interval
    - DOWNWARDS: Boundaries drift downward each interval
    - SIDEWAYS: Boundaries remain relatively stable
    """

    UPWARDS = "upwards"
    """Price is trending upward - boundaries drift higher."""

    DOWNWARDS = "downwards"
    """Price is trending downward - boundaries drift lower."""

    SIDEWAYS = "sideways"
    """Price is consolidating - boundaries remain stable."""

    @classmethod
    def from_string(cls, value: str) -> "MovementType":
        """Convert a string value to MovementType enum."""
        for member in cls:
            if member.value == value.lower():
                return member
        raise ValueError(f"Unknown movement type: {value}")

    def __str__(self) -> str:
        return self.value
