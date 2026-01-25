"""
Market configuration model for the Volume Pumper strategy.

This module contains the VolumePumperMarketConfig model which represents
the complete market state for the architect/boundary management system.
"""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from hummingbot.strategy_v2.volume_pumper.domain.enums import MovementType


class VolumePumperMarketConfig(BaseModel):
    """
    Complete market configuration for the Volume Pumper strategy.

    This model contains all parameters needed for:
    - Phase management (timing and pricing)
    - Boundary calculations (static and flexible)
    - Drift and spread settings
    - Update intervals

    Field Update Schedule:
    - On Decision: movement_type, flexible_*, phase_*, target_drift, current_*
    - On Boundary Update: flexible_support, flexible_resistance
    - On Init Only: static_*, minimum_*, maximum_*, order_levels_steps
    """

    # --- Price Movement ---
    movement_type: str = Field(
        default=MovementType.SIDEWAYS.value,
        description="Current market direction: 'upwards', 'downwards', or 'sideways'",
    )

    # --- Static Boundaries (Fixed price levels) ---
    static_support: Decimal = Field(description="Fixed support price level - absolute floor for orders")
    static_resistance: Decimal = Field(description="Fixed resistance price level - absolute ceiling for orders")

    # --- Flexible Boundaries (Dynamic price levels) ---
    flexible_support: Decimal = Field(description="Current dynamic support level - drifts based on movement")
    flexible_resistance: Decimal = Field(description="Current dynamic resistance level - drifts based on movement")

    # --- Phase Timing ---
    phase_start_time: float = Field(description="Unix timestamp when current phase started")
    phase_end_time: float = Field(description="Unix timestamp when current phase should end")
    minimum_phase_period: float = Field(ge=0, description="Minimum duration of a phase in seconds")
    maximum_phase_period: float = Field(ge=0, description="Maximum duration of a phase in seconds")

    # --- Phase Pricing ---
    phase_start_price: Decimal = Field(description="Price when current phase started")
    phase_end_price: Decimal = Field(description="Target price for end of phase")
    minimum_phase_price_change_perc: Decimal = Field(
        ge=0, description="Minimum price change percentage per phase (1 = 1%)"
    )
    maximum_phase_price_change_perc: Decimal = Field(
        ge=0, description="Maximum price change percentage per phase (1 = 1%)"
    )

    # --- Drift and Spread ---
    target_drift_per_interval: Decimal = Field(description="How much boundaries should drift per update cycle")
    minimum_flexible_wall_spread: Decimal = Field(ge=0, description="Minimum spread between flexible boundaries")
    maximum_flexible_wall_spread: Decimal = Field(ge=0, description="Maximum spread between flexible boundaries")
    current_flexible_wall_spread: Decimal = Field(ge=0, description="Current spread being used")

    # --- Update Intervals ---
    minimum_boundaries_update_interval: float = Field(
        ge=0, description="Minimum time between boundary updates in seconds"
    )
    maximum_boundaries_update_interval: float = Field(
        ge=0, description="Maximum time between boundary updates in seconds"
    )
    current_boundaries_update_interval: float = Field(ge=0, description="Current update interval being used")

    # --- Order Configuration ---
    order_levels_steps: Decimal = Field(description="Price step between adjacent order levels")

    @field_validator("movement_type")
    @classmethod
    def validate_movement_type(cls, v: str) -> str:
        """Validate that movement_type is a valid MovementType value."""
        valid_values = [mt.value for mt in MovementType]
        if v.lower() not in valid_values:
            raise ValueError(f"movement_type must be one of {valid_values}, got: {v}")
        return v.lower()

    @property
    def movement(self) -> MovementType:
        """Get the movement type as an enum."""
        return MovementType.from_string(self.movement_type)

    @property
    def flexible_spread(self) -> Decimal:
        """Calculate the current spread between flexible boundaries."""
        return self.flexible_resistance - self.flexible_support

    @property
    def static_spread(self) -> Decimal:
        """Calculate the spread between static boundaries."""
        return self.static_resistance - self.static_support

    def is_price_in_flexible_range(self, price: Decimal) -> bool:
        """Check if a price is within the flexible boundaries."""
        return self.flexible_support <= price <= self.flexible_resistance

    def is_price_in_static_range(self, price: Decimal) -> bool:
        """Check if a price is within the static boundaries."""
        return self.static_support <= price <= self.static_resistance

    @classmethod
    def create_initial(
        cls,
        static_support: Decimal,
        static_resistance: Decimal,
        flexible_support: Decimal,
        flexible_resistance: Decimal,
        current_price: Decimal,
        current_time: float,
        flexible_wall_spread: Decimal,
        phase_period: float,
        boundaries_update_interval: float,
        minimum_phase_period: float,
        maximum_phase_period: float,
        minimum_phase_price_change_perc: Decimal,
        maximum_phase_price_change_perc: Decimal,
        minimum_flexible_wall_spread: Decimal,
        maximum_flexible_wall_spread: Decimal,
        minimum_boundaries_update_interval: float,
        maximum_boundaries_update_interval: float,
        order_levels_steps: Decimal,
    ) -> "VolumePumperMarketConfig":
        """
        Factory method to create an initial market configuration.

        Args:
            static_support: Fixed support level
            static_resistance: Fixed resistance level
            current_price: Current market price
            current_time: Current timestamp
            flexible_wall_spread: Initial spread percentage
            phase_period: Initial phase duration
            boundaries_update_interval: Initial update interval
            ... (other config params)

        Returns:
            A new VolumePumperMarketConfig instance
        """

        return cls(
            movement_type=MovementType.SIDEWAYS.value,
            static_support=static_support,
            static_resistance=static_resistance,
            flexible_support=flexible_support,
            flexible_resistance=flexible_resistance,
            phase_start_time=current_time,
            phase_end_time=current_time + phase_period,
            minimum_phase_period=minimum_phase_period,
            maximum_phase_period=maximum_phase_period,
            phase_start_price=current_price,
            phase_end_price=current_price,
            minimum_phase_price_change_perc=minimum_phase_price_change_perc,
            maximum_phase_price_change_perc=maximum_phase_price_change_perc,
            target_drift_per_interval=Decimal("0"),
            minimum_flexible_wall_spread=minimum_flexible_wall_spread,
            maximum_flexible_wall_spread=maximum_flexible_wall_spread,
            current_flexible_wall_spread=flexible_wall_spread,
            minimum_boundaries_update_interval=minimum_boundaries_update_interval,
            maximum_boundaries_update_interval=maximum_boundaries_update_interval,
            current_boundaries_update_interval=boundaries_update_interval,
            order_levels_steps=order_levels_steps,
        )

    def with_updated_boundaries(
        self,
        flexible_support: Optional[Decimal] = None,
        flexible_resistance: Optional[Decimal] = None,
    ) -> "VolumePumperMarketConfig":
        """
        Create a new config with updated flexible boundaries.

        Args:
            flexible_support: New support level (or keep current)
            flexible_resistance: New resistance level (or keep current)

        Returns:
            A new VolumePumperMarketConfig with updated values
        """
        return self.model_copy(
            update={
                "flexible_support": flexible_support or self.flexible_support,
                "flexible_resistance": flexible_resistance or self.flexible_resistance,
            }
        )

    def with_new_phase(
        self,
        movement_type: MovementType,
        phase_start_time: float,
        phase_end_time: float,
        phase_start_price: Decimal,
        phase_end_price: Decimal,
        target_drift_per_interval: Decimal,
        current_flexible_wall_spread: Decimal,
        current_boundaries_update_interval: float,
        flexible_support: Decimal,
        flexible_resistance: Decimal,
    ) -> "VolumePumperMarketConfig":
        """
        Create a new config for a new market phase.

        Returns:
            A new VolumePumperMarketConfig with phase-related updates
        """
        return self.model_copy(
            update={
                "movement_type": movement_type.value,
                "phase_start_time": phase_start_time,
                "phase_end_time": phase_end_time,
                "phase_start_price": phase_start_price,
                "phase_end_price": phase_end_price,
                "target_drift_per_interval": target_drift_per_interval,
                "current_flexible_wall_spread": current_flexible_wall_spread,
                "current_boundaries_update_interval": current_boundaries_update_interval,
                "flexible_support": flexible_support,
                "flexible_resistance": flexible_resistance,
            }
        )
