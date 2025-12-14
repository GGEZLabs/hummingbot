import json
import time
from decimal import Decimal
from enum import Enum
from random import choices, uniform

from cachetools import TTLCache, cachedmethod

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.model.market_config import MarketConfig
from hummingbot.strategy_v2.utils.custom_volume_pumper_utils import CustomVolumePumperUtils
from hummingbot.strategy_v2.utils.market_config_manager import MarketConfigManager
from hummingbot.strategy_v2.utils.volume_pumper_config import VolumePumperConfigBase

from .market_config_types import VolumePumperMarketConfig


class MarketMovementTypes(Enum):
    UPWARDS = "upwards"
    DOWNWARDS = "downwards"
    SIDEWAYS = "sideways"


class VolumePumperPaywallsArchitect:
    def __init__(
        self, market_config_manager: MarketConfigManager, config: VolumePumperConfigBase, connector: ConnectorBase
    ):
        self._market_config_manager = market_config_manager
        self.config = config
        self.connector = connector
        self.trading_pair = config.trading_pair
        self.strategy_name = config.strategy_name
        self._market_config_cache = TTLCache(maxsize=10, ttl=10.0)
        self.utils = CustomVolumePumperUtils(self.connector, self.trading_pair)

    def _is_market_config_exists(self) -> bool:
        return self._market_config_manager.is_config_exists(self.trading_pair, self.strategy_name)

    def _update_market_config_data(self, market_config: VolumePumperMarketConfig):
        return self._market_config_manager.update_market_config(self.trading_pair, self.strategy_name, market_config)

    @property
    @cachedmethod(lambda self: self._market_config_cache)
    def market_config(self) -> MarketConfig:
        return self._market_config_manager.get_market_config(self.trading_pair, self.strategy_name)

    def is_time_to_make_decision(self) -> bool:
        market_config = self._market_config_manager.get_market_config(self.trading_pair, self.strategy_name)
        config = VolumePumperMarketConfig(**market_config.config)
        current_time = time.time()
        if current_time >= config.phase_end_time + self.config.architect_failover_delay:
            return True
        return False

    def is_time_to_update_boundaries(self) -> bool:
        market_config = self.market_config
        config = VolumePumperMarketConfig(**market_config.config)
        current_time = time.time()
        if current_time >= market_config.last_updated + config.current_boundaries_update_interval:
            return True
        return False

    def initializing_market_config(self) -> VolumePumperMarketConfig:
        if self._is_market_config_exists():
            return VolumePumperMarketConfig(**self.market_config.config)
        else:

            current_price = self.connector.get_mid_price(self.trading_pair)
            current_time = time.time()

            flexible_wall_spread = self.utils.get_random_decimal(
                self.config.minimum_flexible_wall_spread, self.config.maximum_flexible_wall_spread
            )
            boundaries_update_interval = uniform(
                self.config.minimum_boundaries_update_interval, self.config.maximum_boundaries_update_interval
            )
            support_price, resistance_price = self._calculate_support_and_resistance_prices(
                current_price, flexible_wall_spread, self.config.static_support, self.config.static_resistance
            )
            config_data = VolumePumperMarketConfig(
                movement_type=MarketMovementTypes.SIDEWAYS.value,
                static_support=self.utils.round_price_to_tick_size(self.config.static_support),
                static_resistance=self.utils.round_price_to_tick_size(self.config.static_resistance),
                flexible_support=support_price,
                flexible_resistance=resistance_price,
                phase_start_time=current_time,
                minimum_phase_period=self.config.minimum_phase_period,
                maximum_phase_period=self.config.maximum_phase_period,
                phase_end_time=current_time
                + uniform(self.config.minimum_phase_period, self.config.maximum_phase_period),
                phase_start_price=self.utils.round_price_to_tick_size(current_price),
                minimum_phase_price_change_perc=self.config.minimum_phase_price_change_perc,
                maximum_phase_price_change_perc=self.config.maximum_phase_price_change_perc,
                phase_end_price=self.utils.round_price_to_tick_size(current_price),
                target_drift_per_interval=Decimal("0"),
                minimum_flexible_wall_spread=self.config.minimum_flexible_wall_spread,
                maximum_flexible_wall_spread=self.config.maximum_flexible_wall_spread,
                current_flexible_wall_spread=Decimal(str(flexible_wall_spread)),
                minimum_boundaries_update_interval=self.config.minimum_boundaries_update_interval,
                maximum_boundaries_update_interval=self.config.maximum_boundaries_update_interval,
                current_boundaries_update_interval=boundaries_update_interval,
                order_levels_steps=self.config.order_levels_steps,
            )
            # json.loads(config_data.model_dump_json())
            market_config = MarketConfig(
                trading_pair=self.trading_pair,
                strategy_name=self.strategy_name,
                config=json.loads(config_data.model_dump_json()),
                last_updated=current_time,
            )
            self._market_config_manager.create_market_config(market_config)
            return config_data

    def update_boundaries_config(self):
        market_config = self.market_config
        market_config_json = VolumePumperMarketConfig(**market_config.config)
        # Determine new flexible support and resistance
        new_support = market_config_json.flexible_support + market_config_json.target_drift_per_interval
        new_resistance = market_config_json.flexible_resistance + market_config_json.target_drift_per_interval
        new_support = max(new_support, market_config_json.static_support)
        new_resistance = min(new_resistance, market_config_json.static_resistance)
        # Update market config
        market_config_json.flexible_support = self.utils.round_price_to_tick_size(Decimal(new_support))
        market_config_json.flexible_resistance = self.utils.round_price_to_tick_size(Decimal(new_resistance))
        # Save updated config
        self._update_market_config_data(market_config_json)

    def make_decision(self) -> VolumePumperMarketConfig:
        market_config = self.market_config
        market_config_json = VolumePumperMarketConfig(**market_config.config)
        current_time = time.time()
        current_price = self.connector.get_mid_price(self.trading_pair)
        bid_distance = CustomVolumePumperUtils.percent_distance_from_bid(
            market_config_json.static_resistance, market_config_json.static_support, current_price
        )
        weights = self._calculate_probabilities(bid_distance)
        # Determine new movement type
        movement_type = self._get_new_movement_type(weights)

        # Determine new flexible wall spread
        flexible_wall_spread = self.utils.get_random_decimal(
            market_config_json.minimum_flexible_wall_spread, market_config_json.maximum_flexible_wall_spread
        )

        # Determine new flexible support and resistance
        support_price, resistance_price = self._calculate_support_and_resistance_prices(
            current_price, flexible_wall_spread, market_config_json.static_support, market_config_json.static_resistance
        )
        # determine the phase end
        # time
        phase_end_time = current_time + uniform(
            market_config_json.minimum_phase_period, market_config_json.maximum_phase_period
        )
        # price
        price_change_perc = self.utils.get_random_decimal(
            market_config_json.minimum_phase_price_change_perc, market_config_json.maximum_phase_price_change_perc
        ) / Decimal("100")
        phase_end_price = current_price
        if movement_type == MarketMovementTypes.UPWARDS.value:
            phase_end_price += current_price * price_change_perc
        elif movement_type == MarketMovementTypes.DOWNWARDS.value:
            phase_end_price -= current_price * price_change_perc

        if phase_end_price > resistance_price:
            phase_end_price = resistance_price
        elif phase_end_price < support_price:
            phase_end_price = support_price

        boundaries_update_interval = uniform(
            market_config_json.minimum_boundaries_update_interval, market_config_json.maximum_boundaries_update_interval
        )
        drift_per_interval = self._calculate_price_drift(
            current_price,
            phase_end_price,
            current_time,
            phase_end_time,
            boundaries_update_interval,
        )
        # validate price drift and  boundaries_update_interval
        min_allowed_boundaries_update_interval = self._calculate_min_allowed_boundaries_update_interval(
            current_price, phase_end_price, current_time, phase_end_time
        )
        boundaries_update_interval = max(boundaries_update_interval, min_allowed_boundaries_update_interval)
        drift_per_interval = (
            Decimal("0")
            if movement_type == MarketMovementTypes.SIDEWAYS.value
            else max(drift_per_interval, self.utils.price_tick_size)
        )

        if movement_type == MarketMovementTypes.DOWNWARDS.value:
            drift_per_interval = -drift_per_interval

        # update json data
        market_config_json.movement_type = movement_type
        market_config_json.flexible_support = support_price
        market_config_json.flexible_resistance = resistance_price
        market_config_json.phase_start_time = current_time
        market_config_json.phase_end_time = phase_end_time
        market_config_json.phase_start_price = self.utils.round_price_to_tick_size(current_price)
        market_config_json.phase_end_price = self.utils.round_price_to_tick_size(phase_end_price)
        market_config_json.target_drift_per_interval = self.utils.round_price_to_tick_size(drift_per_interval)
        market_config_json.current_flexible_wall_spread = flexible_wall_spread
        market_config_json.current_boundaries_update_interval = boundaries_update_interval

        self._update_market_config_data(market_config_json)
        return market_config_json

    def _calculate_support_and_resistance_prices(self, current_price, spread, static_support, static_resistance):
        support_price = current_price - (current_price * (spread / Decimal((2 * 100))))
        resistance_price = current_price + (current_price * (spread / Decimal((2 * 100))))
        if support_price < static_support:
            support_price = static_support
        if resistance_price > static_resistance:
            resistance_price = static_resistance

        return self.utils.round_price_to_tick_size(support_price), self.utils.round_price_to_tick_size(resistance_price)

    def _calculate_probabilities(self, bid_distance: float):
        # change the function to use Decimal
        if bid_distance <= 50:
            # interpolate between support (0: 50,0,50) and mid (50: 30,30,40)
            t = bid_distance / 50
            upward = 50 - (20 * t)
            downward = 0 + (30 * t)
            sideway = 50 - (10 * t)
        else:
            # interpolate between mid (50: 30,30,40) and resistance (100: 0,50,50)
            t = (bid_distance - 50) / 50
            upward = 30 - (30 * t)
            downward = 30 + (20 * t)
            sideway = 40 + (10 * t)

        return {
            MarketMovementTypes.UPWARDS.value: round(upward, 2),
            MarketMovementTypes.DOWNWARDS.value: round(downward, 2),
            MarketMovementTypes.SIDEWAYS.value: round(sideway, 2),
        }

    def _get_new_movement_type(self, price_movement_probs):
        population = [market_type.value for market_type in MarketMovementTypes]
        weights = [float(price_movement_probs[market_type.value]) for market_type in MarketMovementTypes]
        new_movement_type = choices(
            population=population,
            weights=weights,
            k=1,
        )[0]
        return new_movement_type

    def _calculate_price_drift(
        self,
        start_price: Decimal,
        end_price: Decimal,
        start_time: float,
        end_time: float,
        boundaries_update_interval: float,
    ) -> Decimal:

        price_diff = end_price - start_price
        time_diff = end_time - start_time
        num_of_periods_in_phase = time_diff / boundaries_update_interval
        price_drift_per_interval = price_diff / Decimal(num_of_periods_in_phase)

        return self.utils.round_price_to_tick_size(price_drift_per_interval)

    def _calculate_min_allowed_boundaries_update_interval(
        self, start_price: Decimal, end_price: Decimal, start_time: float, end_time: float
    ):
        time_diff = Decimal(str(end_time - start_time))
        price_diff = end_price - start_price
        if price_diff == 0:
            return 0
        return (time_diff * self.utils.price_tick_size) / price_diff
