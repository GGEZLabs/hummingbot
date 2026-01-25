"""
Architect service for the Volume Pumper strategy.

The "architect" service handles phase decision making - determining when
to change market phases and calculating the parameters for new phases.
"""

import logging
import time
from decimal import Decimal
from typing import Tuple

from hummingbot.strategy_v2.volume_pumper.adapters.market_data_adapter import MarketDataAdapter
from hummingbot.strategy_v2.volume_pumper.adapters.persistence_adapter import PersistenceAdapter
from hummingbot.strategy_v2.volume_pumper.domain.enums import MovementType
from hummingbot.strategy_v2.volume_pumper.domain.market_config import VolumePumperMarketConfig
from hummingbot.strategy_v2.volume_pumper.utils.math_utils import (
    calculate_drift_per_interval,
    calculate_movement_probabilities,
    calculate_weighted_random_choice,
    min_update_interval_for_tick,
    percent_distance_from_bid,
    random_decimal,
    random_float,
)
from hummingbot.strategy_v2.volume_pumper.utils.price_utils import clamp_price, round_to_tick_size

logger = logging.getLogger(__name__)


class ArchitectService:
    """
    Service for phase decision making.

    The architect decides:
    - When to end the current phase and start a new one
    - What movement type (upward/downward/sideways) to use
    - Phase duration and price targets
    - Boundary update intervals and drift rates

    Single Responsibility: Phase decisions only.
    """

    def __init__(
        self,
        market_data: MarketDataAdapter,
        persistence: PersistenceAdapter,
        static_support: Decimal,
        static_resistance: Decimal,
        minimum_phase_period: float,
        maximum_phase_period: float,
        minimum_phase_price_change_perc: Decimal,
        maximum_phase_price_change_perc: Decimal,
        minimum_flexible_wall_spread: Decimal,
        maximum_flexible_wall_spread: Decimal,
        minimum_boundaries_update_interval: float,
        maximum_boundaries_update_interval: float,
        order_levels_steps: Decimal,
        architect_failover_delay: float = 30,
    ):
        """
        Initialize the architect service.

        Args:
            market_data: Market data adapter
            persistence: Persistence adapter for saving config
            static_support: Fixed support price level
            static_resistance: Fixed resistance price level
            minimum_phase_period: Minimum phase duration (seconds)
            maximum_phase_period: Maximum phase duration (seconds)
            minimum_phase_price_change_perc: Min price change % per phase
            maximum_phase_price_change_perc: Max price change % per phase
            minimum_flexible_wall_spread: Min spread between flexible walls
            maximum_flexible_wall_spread: Max spread between flexible walls
            minimum_boundaries_update_interval: Min update interval (seconds)
            maximum_boundaries_update_interval: Max update interval (seconds)
            order_levels_steps: Price step between order levels
            architect_failover_delay: Delay after phase end before decision
        """
        self._market_data = market_data
        self._persistence = persistence
        self._static_support = static_support
        self._static_resistance = static_resistance
        self._min_phase_period = minimum_phase_period
        self._max_phase_period = maximum_phase_period
        self._min_price_change = minimum_phase_price_change_perc
        self._max_price_change = maximum_phase_price_change_perc
        self._min_wall_spread = minimum_flexible_wall_spread
        self._max_wall_spread = maximum_flexible_wall_spread
        self._min_update_interval = minimum_boundaries_update_interval
        self._max_update_interval = maximum_boundaries_update_interval
        self._order_levels_steps = order_levels_steps
        self._failover_delay = architect_failover_delay

    @property
    def price_tick_size(self) -> Decimal:
        """Get the price tick size."""
        try:
            return self._market_data.price_tick_size
        except Exception as e:
            logger.error(f"Error in price_tick_size: {type(e).__name__}: {e}")
            raise

    def should_make_decision(self, config: VolumePumperMarketConfig) -> bool:
        """
        Check if it's time to make a new phase decision.

        Args:
            config: Current market configuration

        Returns:
            True if a decision should be made
        """
        try:
            current_time = time.time()
            return current_time >= config.phase_end_time + self._failover_delay
        except Exception as e:
            logger.error(f"Error in should_make_decision: {type(e).__name__}: {e}")
            raise

    def should_update_boundaries(
        self,
        config: VolumePumperMarketConfig,
        last_updated: float,
    ) -> bool:
        """
        Check if it's time to update boundaries.

        Args:
            config: Current market configuration
            last_updated: Timestamp of last update

        Returns:
            True if boundaries should be updated
        """
        try:
            current_time = time.time()
            return current_time >= last_updated + config.current_boundaries_update_interval
        except Exception as e:
            logger.error(f"Error in should_update_boundaries: {type(e).__name__}: {e}")
            raise

    def make_decision(
        self,
        config: VolumePumperMarketConfig,
        current_price: Decimal = None,
        current_time: float = None,
    ) -> VolumePumperMarketConfig:
        """
        Make a new phase decision.

        Determines:
        - Movement type based on price position
        - Phase duration
        - Price targets
        - Drift rate
        - Update interval

        Args:
            config: Current market configuration
            current_price: Current price (optional, fetched if not provided)
            current_time: Current time (optional, uses time.time())

        Returns:
            Updated market configuration for the new phase
        """
        try:
            if current_price is None:
                current_price = self._market_data.get_mid_price()
            if current_time is None:
                current_time = time.time()

            # Calculate position within static range
            bid_distance = percent_distance_from_bid(
                config.static_resistance,
                config.static_support,
                current_price,
            )

            # Determine movement type based on position
            probabilities = calculate_movement_probabilities(bid_distance)
            movement_str = calculate_weighted_random_choice(probabilities)
            movement_type = MovementType.from_string(movement_str)

            # Calculate new flexible boundaries
            flexible_spread = random_decimal(self._min_wall_spread, self._max_wall_spread)
            support, resistance = self._calculate_boundaries(current_price, flexible_spread)

            # Calculate phase duration
            phase_duration = random_float(self._min_phase_period, self._max_phase_period)
            phase_end_time = current_time + phase_duration

            # Calculate price target
            price_change_perc = random_decimal(self._min_price_change, self._max_price_change) / Decimal("100")

            phase_end_price = self._calculate_phase_end_price(
                current_price, price_change_perc, movement_type, support, resistance
            )

            # Calculate update interval
            update_interval = random_float(self._min_update_interval, self._max_update_interval)

            # Calculate drift per interval
            drift = self._calculate_drift(
                current_price,
                phase_end_price,
                current_time,
                phase_end_time,
                update_interval,
                movement_type,
            )

            # Validate and adjust update interval if needed
            min_interval = min_update_interval_for_tick(
                current_price,
                phase_end_price,
                phase_end_time - current_time,
                self.price_tick_size,
            )
            update_interval = max(update_interval, min_interval)

            # Create updated configuration
            return config.with_new_phase(
                movement_type=movement_type,
                phase_start_time=current_time,
                phase_end_time=phase_end_time,
                phase_start_price=round_to_tick_size(current_price, self.price_tick_size),
                phase_end_price=round_to_tick_size(phase_end_price, self.price_tick_size),
                target_drift_per_interval=round_to_tick_size(drift, self.price_tick_size),
                current_flexible_wall_spread=flexible_spread,
                current_boundaries_update_interval=update_interval,
                flexible_support=support,
                flexible_resistance=resistance,
            )
        except Exception as e:
            logger.error(f"Error in make_decision: {type(e).__name__}: {e}")
            raise

    def _calculate_boundaries(
        self,
        current_price: Decimal,
        spread_percent: Decimal,
    ) -> Tuple[Decimal, Decimal]:
        """Calculate flexible support and resistance."""
        try:
            half_spread = current_price * (spread_percent / Decimal("200"))

            support = current_price - half_spread
            resistance = current_price + half_spread

            # Clamp to static boundaries
            support = clamp_price(support, self._static_support, self._static_resistance)
            resistance = clamp_price(resistance, self._static_support, self._static_resistance)

            return (
                round_to_tick_size(support, self.price_tick_size),
                round_to_tick_size(resistance, self.price_tick_size),
            )
        except Exception as e:
            logger.error(f"Error in _calculate_boundaries: {type(e).__name__}: {e}")
            raise

    def _calculate_phase_end_price(
        self,
        current_price: Decimal,
        price_change_perc: Decimal,
        movement_type: MovementType,
        support: Decimal,
        resistance: Decimal,
    ) -> Decimal:
        """Calculate the target price at end of phase."""
        try:
            if movement_type == MovementType.UPWARDS:
                end_price = current_price + current_price * price_change_perc
            elif movement_type == MovementType.DOWNWARDS:
                end_price = current_price - current_price * price_change_perc
            else:  # SIDEWAYS
                end_price = current_price

            # Clamp to flexible boundaries
            return clamp_price(end_price, support, resistance)
        except Exception as e:
            logger.error(f"Error in _calculate_phase_end_price: {type(e).__name__}: {e}")
            raise

    def _calculate_drift(
        self,
        current_price: Decimal,
        end_price: Decimal,
        current_time: float,
        end_time: float,
        update_interval: float,
        movement_type: MovementType,
    ) -> Decimal:
        """Calculate the drift per update interval."""
        try:
            if movement_type == MovementType.SIDEWAYS:
                return Decimal("0")

            drift = calculate_drift_per_interval(
                current_price,
                end_price,
                end_time - current_time,
                update_interval,
            )

            # Ensure drift is at least one tick
            drift = max(abs(drift), self.price_tick_size)

            # Apply direction
            if movement_type == MovementType.DOWNWARDS:
                drift = -drift

            return drift
        except Exception as e:
            logger.error(f"Error in _calculate_drift: {type(e).__name__}: {e}")
            raise

    def create_initial_config(self) -> VolumePumperMarketConfig:
        """
        Create the initial market configuration.

        Called when no configuration exists in the database.

        Returns:
            Initial VolumePumperMarketConfig
        """
        try:
            current_price = self._market_data.get_mid_price()
            current_time = time.time()

            flexible_spread = random_decimal(self._min_wall_spread, self._max_wall_spread)
            update_interval = random_float(self._min_update_interval, self._max_update_interval)
            phase_duration = random_float(self._min_phase_period, self._max_phase_period)

            support, resistance = self._calculate_boundaries(current_price, flexible_spread)

            return VolumePumperMarketConfig.create_initial(
                static_support=round_to_tick_size(self._static_support, self.price_tick_size),
                static_resistance=round_to_tick_size(self._static_resistance, self.price_tick_size),
                flexible_support=support,
                flexible_resistance=resistance,
                current_price=round_to_tick_size(current_price, self.price_tick_size),
                current_time=current_time,
                flexible_wall_spread=flexible_spread,
                phase_period=phase_duration,
                boundaries_update_interval=update_interval,
                minimum_phase_period=self._min_phase_period,
                maximum_phase_period=self._max_phase_period,
                minimum_phase_price_change_perc=self._min_price_change,
                maximum_phase_price_change_perc=self._max_price_change,
                minimum_flexible_wall_spread=self._min_wall_spread,
                maximum_flexible_wall_spread=self._max_wall_spread,
                minimum_boundaries_update_interval=self._min_update_interval,
                maximum_boundaries_update_interval=self._max_update_interval,
                order_levels_steps=self._order_levels_steps,
            )
        except Exception as e:
            logger.error(f"Error in create_initial_config: {type(e).__name__}: {e}")
            raise
