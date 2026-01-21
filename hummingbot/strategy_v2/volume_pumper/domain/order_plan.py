"""
Order action plan for coordinating order operations.

This module contains the OrderActionPlan dataclass which represents
a plan of orders to create and cancel.
"""

from dataclasses import dataclass, field
from typing import List

from hummingbot.core.data_type.order_candidate import OrderCandidate


@dataclass
class OrderActionPlan:
    """
    A plan of order actions to execute.

    This dataclass holds:
    - cancellations_ids: List of order IDs to cancel
    - creations_candidates: List of new orders to create

    Usage:
        plan = OrderActionPlan()
        plan.add_cancellation("order-123")
        plan.add_creation(order_candidate)

        if plan.has_actions:
            execute_plan(plan)
    """

    cancellations_ids: List[str] = field(default_factory=list)
    """Order IDs to be cancelled."""

    creations_candidates: List[OrderCandidate] = field(default_factory=list)
    """Order candidates to be created."""

    @property
    def has_cancellations(self) -> bool:
        """Check if there are any orders to cancel."""
        return len(self.cancellations_ids) > 0

    @property
    def has_creations(self) -> bool:
        """Check if there are any orders to create."""
        return len(self.creations_candidates) > 0

    @property
    def has_actions(self) -> bool:
        """Check if there are any actions in this plan."""
        return self.has_cancellations or self.has_creations

    @property
    def total_actions(self) -> int:
        """Get the total number of actions in this plan."""
        return len(self.cancellations_ids) + len(self.creations_candidates)

    def add_cancellation(self, order_id: str) -> None:
        """Add an order ID to the cancellation list."""
        if order_id not in self.cancellations_ids:
            self.cancellations_ids.append(order_id)

    def add_creation(self, order: OrderCandidate) -> None:
        """Add an order candidate to the creation list."""
        self.creations_candidates.append(order)

    def remove_cancellation(self, order_id: str) -> bool:
        """
        Remove an order ID from the cancellation list.

        Returns:
            True if the order was found and removed, False otherwise
        """
        if order_id in self.cancellations_ids:
            self.cancellations_ids.remove(order_id)
            return True
        return False

    def remove_creation_by_price(self, price) -> bool:
        """
        Remove order candidates matching a specific price.

        Args:
            price: The price to match

        Returns:
            True if any orders were removed, False otherwise
        """
        original_count = len(self.creations_candidates)
        self.creations_candidates = [
            o for o in self.creations_candidates if o.price != price
        ]
        return len(self.creations_candidates) < original_count

    def clear(self) -> None:
        """Clear all actions from this plan."""
        self.cancellations_ids.clear()
        self.creations_candidates.clear()

    def merge(self, other: "OrderActionPlan") -> "OrderActionPlan":
        """
        Merge another plan into this one.

        Args:
            other: Another OrderActionPlan to merge

        Returns:
            A new OrderActionPlan with combined actions
        """
        return OrderActionPlan(
            cancellations_ids=list(set(self.cancellations_ids + other.cancellations_ids)),
            creations_candidates=self.creations_candidates + other.creations_candidates,
        )

    def __repr__(self) -> str:
        return (
            f"OrderActionPlan("
            f"cancellations={len(self.cancellations_ids)}, "
            f"creations={len(self.creations_candidates)})"
        )
