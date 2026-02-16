from decimal import Decimal

from pydantic import BaseModel


class VolumePumperMarketConfig(BaseModel):
    movement_type: str
    static_support: Decimal
    static_resistance: Decimal
    flexible_support: Decimal
    flexible_resistance: Decimal
    phase_start_time: float
    phase_end_time: float
    minimum_phase_period: float
    maximum_phase_period: float
    phase_start_price: Decimal
    phase_end_price: Decimal
    minimum_phase_price_change_perc: Decimal
    maximum_phase_price_change_perc: Decimal
    target_drift_per_interval: Decimal
    minimum_flexible_wall_spread: Decimal
    maximum_flexible_wall_spread: Decimal
    current_flexible_wall_spread: Decimal
    minimum_boundaries_update_interval: float
    maximum_boundaries_update_interval: float
    current_boundaries_update_interval: float
    order_levels_steps: Decimal
    """
    ## only these data need to be changed each decision##

    movement_type
    flexible_support
    flexible_resistance
    phase_start_time
    phase_end_time
    phase_start_price
    phase_end_price
    current_target_drift_per_interval
    current_flexible_wall_spread
    current_boundaries_update_interval
    next_boundary_time_update

    ## only these data need to be changed each boundaries update ##

    flexible_support
    flexible_resistance
    next_boundary_time_update

    ## all data must be initialized when the strategy runs for the first time ##
    ** the data should be available on the database for strategy config **

    static_support
    static_resistance
    minimum_phase_period
    maximum_phase_period
    minimum_phase_price_change_perc
    maximum_phase_price_change_perc
    minimum_flexible_wall_spread
    maximum_flexible_wall_spread
    minimum_boundaries_update_interval
    maximum_boundaries_update_interval
    order_levels_steps

    """
