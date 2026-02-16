"""
Volume Pumper Strategy

A trading strategy for generating volume through matched buy/sell orders
with intelligent boundary (paywall) management.

Architecture:
- domain/     : Core data types and enums
- protocols/  : Interface definitions (Protocols)
- services/   : Business logic implementations
- adapters/   : Infrastructure adapters
- utils/      : Pure utility functions
- controller  : Main orchestrator
"""

from hummingbot.strategy_v2.volume_pumper.controller import VolumePumperController, create_volume_pumper_controller
from hummingbot.strategy_v2.volume_pumper.domain.enums import MovementType, StrategyState

__all__ = [
    "VolumePumperController",
    "create_volume_pumper_controller",
    "StrategyState",
    "MovementType",
]
