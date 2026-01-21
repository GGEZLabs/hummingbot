"""
Mathematical utility functions for the Volume Pumper strategy.

This module contains pure mathematical functions with no side effects
or dependencies on external state.
"""

import random
from decimal import Decimal
from typing import Union

# Type alias for numeric values
Numeric = Union[Decimal, float, int]


def random_decimal(min_val: Numeric, max_val: Numeric) -> Decimal:
    """
    Generate a random Decimal within a range.

    Args:
        min_val: Minimum value (inclusive)
        max_val: Maximum value (inclusive)

    Returns:
        A random Decimal in the range [min_val, max_val]

    Examples:
        >>> result = random_decimal(Decimal("1.0"), Decimal("2.0"))
        >>> Decimal("1.0") <= result <= Decimal("2.0")
        True
    """
    min_float = float(min_val)
    max_float = float(max_val)
    return Decimal(str(random.uniform(min_float, max_float)))


def random_int(min_val: int, max_val: int) -> int:
    """
    Generate a random integer within a range.

    Args:
        min_val: Minimum value (inclusive)
        max_val: Maximum value (inclusive)

    Returns:
        A random integer in the range [min_val, max_val]
    """
    return random.randint(min_val, max_val)


def random_float(min_val: float, max_val: float) -> float:
    """
    Generate a random float within a range.

    Args:
        min_val: Minimum value (inclusive)
        max_val: Maximum value (inclusive)

    Returns:
        A random float in the range [min_val, max_val]
    """
    return random.uniform(min_val, max_val)


def percent_distance_from_bid(
    ask: Numeric,
    bid: Numeric,
    price: Numeric,
) -> Decimal:
    """
    Calculate how far a price is from the bid as a percentage of the spread.

    0% = at the bid
    100% = at the ask
    50% = at the mid

    Args:
        ask: The ask price
        bid: The bid price
        price: The price to measure

    Returns:
        Percentage distance from bid (0-100)

    Examples:
        >>> percent_distance_from_bid(110, 100, 100)
        Decimal('0')  # At the bid
        >>> percent_distance_from_bid(110, 100, 110)
        Decimal('100')  # At the ask
        >>> percent_distance_from_bid(110, 100, 105)
        Decimal('50')  # At the mid
    """
    ask_dec = Decimal(str(ask))
    bid_dec = Decimal(str(bid))
    price_dec = Decimal(str(price))

    price_range = ask_dec - bid_dec

    if price_range == 0:
        return Decimal("0")

    distance_from_bid = (price_dec - bid_dec) / price_range
    return distance_from_bid * Decimal("100")


def rescale_value(
    value: Numeric,
    from_min: Numeric,
    from_max: Numeric,
    to_min: Numeric,
    to_max: Numeric,
) -> Decimal:
    """
    Rescale a value from one range to another.

    Linear interpolation: maps [from_min, from_max] to [to_min, to_max]

    Args:
        value: The value to rescale
        from_min: Original range minimum
        from_max: Original range maximum
        to_min: Target range minimum
        to_max: Target range maximum

    Returns:
        The rescaled value

    Examples:
        >>> rescale_value(50, 0, 100, 0, 1)
        Decimal('0.5')
        >>> rescale_value(75, 0, 100, 0, 10)
        Decimal('7.5')
    """
    value_dec = Decimal(str(value))
    from_min_dec = Decimal(str(from_min))
    from_max_dec = Decimal(str(from_max))
    to_min_dec = Decimal(str(to_min))
    to_max_dec = Decimal(str(to_max))

    from_range = from_max_dec - from_min_dec

    if from_range == 0:
        return to_min_dec

    normalized = (value_dec - from_min_dec) / from_range
    return to_min_dec + normalized * (to_max_dec - to_min_dec)


def geometric_amount(
    position: int,
    total_levels: int,
    total_balance: Numeric,
    common_ratio: float = 1.5,
) -> Decimal:
    """
    Calculate order amount using geometric progression.

    Formula: amount_i = base_amount * r^position
    where base_amount = total * (r - 1) / (r^n - 1)

    This distributes more balance to outer levels (farther from current price).

    Args:
        position: The level position (0-indexed, 0 = closest to price)
        total_levels: Total number of levels
        total_balance: Total balance to distribute
        common_ratio: Geometric ratio (default 1.5)

    Returns:
        The calculated amount for this level

    Raises:
        ValueError: If common_ratio <= 1.0 or invalid position

    Examples:
        >>> geometric_amount(0, 3, Decimal("100"), 2.0)
        Decimal('14.285...')  # Smallest amount at position 0
        >>> geometric_amount(2, 3, Decimal("100"), 2.0)
        Decimal('57.142...')  # Largest amount at position 2
    """
    if common_ratio <= 1.0:
        raise ValueError("Common ratio must be > 1.0")

    if position < 0 or position >= total_levels:
        raise ValueError(f"Position {position} out of range [0, {total_levels})")

    if total_levels <= 0:
        raise ValueError("Total levels must be > 0")

    total_dec = Decimal(str(total_balance))

    if total_dec <= 0:
        return Decimal("0")

    r = common_ratio
    n = total_levels

    # base_amount = total * (r - 1) / (r^n - 1)
    base_amount = float(total_dec) * (r - 1) / (r**n - 1)

    # amount at position = base * r^position
    amount = base_amount * (r**position)

    return Decimal(str(amount))


def cube(value: Numeric) -> Decimal:
    """
    Calculate the cube of a value.

    Args:
        value: The value to cube

    Returns:
        value^3 as a Decimal
    """
    value_dec = Decimal(str(value))
    return value_dec**3


def calculate_weighted_random_choice(
    weights: dict,
) -> str:
    """
    Make a weighted random choice from a dictionary of options.

    Args:
        weights: Dictionary mapping options to their weights

    Returns:
        The selected option key

    Examples:
        >>> weights = {"a": 50, "b": 30, "c": 20}
        >>> choice = calculate_weighted_random_choice(weights)
        >>> choice in weights
        True
    """
    population = list(weights.keys())
    weight_values = [float(weights[k]) for k in population]
    return random.choices(population=population, weights=weight_values, k=1)[0]


def calculate_movement_probabilities(bid_distance: Numeric) -> dict:
    """
    Calculate probabilities for market movement types based on bid distance.

    Interpolates between support (0%) and resistance (100%):
    - At support: favor upward movement
    - At resistance: favor downward movement
    - At mid: more balanced

    Args:
        bid_distance: Percentage distance from bid (0-100)

    Returns:
        Dictionary with movement type probabilities

    Examples:
        >>> probs = calculate_movement_probabilities(0)
        >>> probs["upwards"] > probs["downwards"]  # At support, favor up
        True
        >>> probs = calculate_movement_probabilities(100)
        >>> probs["downwards"] > probs["upwards"]  # At resistance, favor down
        True
    """
    bd = float(bid_distance)

    if bd <= 50:
        # Interpolate between support (0: 50,0,50) and mid (50: 30,30,40)
        t = bd / 50
        upward = 50 - (20 * t)
        downward = 0 + (30 * t)
        sideways = 50 - (10 * t)
    else:
        # Interpolate between mid (50: 30,30,40) and resistance (100: 0,50,50)
        t = (bd - 50) / 50
        upward = 30 - (30 * t)
        downward = 30 + (20 * t)
        sideways = 40 + (10 * t)

    return {
        "upwards": round(upward, 2),
        "downwards": round(downward, 2),
        "sideways": round(sideways, 2),
    }


def calculate_drift_per_interval(
    start_price: Numeric,
    end_price: Numeric,
    total_time: float,
    update_interval: float,
) -> Decimal:
    """
    Calculate the price drift per update interval.

    Args:
        start_price: Starting price
        end_price: Target ending price
        total_time: Total time for the phase (seconds)
        update_interval: Time between updates (seconds)

    Returns:
        Price drift per interval
    """
    if total_time <= 0 or update_interval <= 0:
        return Decimal("0")

    start_dec = Decimal(str(start_price))
    end_dec = Decimal(str(end_price))

    price_diff = end_dec - start_dec
    num_intervals = Decimal(str(total_time / update_interval))

    if num_intervals == 0:
        return Decimal("0")

    return price_diff / num_intervals


def min_update_interval_for_tick(
    start_price: Numeric,
    end_price: Numeric,
    total_time: float,
    tick_size: Numeric,
) -> float:
    """
    Calculate minimum update interval to ensure drift >= tick_size.

    Args:
        start_price: Starting price
        end_price: Target ending price
        total_time: Total time for the phase
        tick_size: Minimum price increment

    Returns:
        Minimum update interval in seconds
    """
    price_diff = abs(Decimal(str(end_price)) - Decimal(str(start_price)))

    if price_diff == 0:
        return 0

    tick_dec = Decimal(str(tick_size))
    time_dec = Decimal(str(total_time))

    # interval = time * tick_size / price_diff
    return float((time_dec * tick_dec) / price_diff)
