"""
Price utility functions for the Volume Pumper strategy.

This module contains pure functions for price calculations
with no side effects or dependencies on external state.
"""

import logging
import math
from decimal import Decimal
from typing import Union

logger = logging.getLogger(__name__)

# Type alias for numeric values
Numeric = Union[Decimal, float, int]


def round_to_tick_size(value: Numeric, tick_size: Numeric) -> Decimal:
    """
    Round a value down to the nearest tick size.

    Uses floor rounding to ensure we never exceed the original value.

    Args:
        value: The value to round
        tick_size: The tick size to round to

    Returns:
        The rounded value as a Decimal

    Examples:
        >>> round_to_tick_size(Decimal("1.2345"), Decimal("0.01"))
        Decimal('1.23')
        >>> round_to_tick_size(100.567, 0.1)
        Decimal('100.5')
    """
    try:
        value_dec = Decimal(str(value))
        tick_dec = Decimal(str(tick_size))

        if tick_dec == 0:
            return value_dec

        return Decimal(str(math.floor(value_dec / tick_dec))) * tick_dec
    except Exception as e:
        logger.error(
            f"Error in round_to_tick_size(value={value}, tick_size={tick_size}): {type(e).__name__}: {e}"
        )
        raise


def calculate_spread_percent(bid: Numeric, ask: Numeric) -> Decimal:
    """
    Calculate the spread as a percentage of the mid price.

    Formula: (ask - bid) / ((ask + bid) / 2) * 100

    Args:
        bid: The best bid price
        ask: The best ask price

    Returns:
        The spread percentage

    Examples:
        >>> calculate_spread_percent(100, 101)
        Decimal('0.995...')  # approximately 1%
    """
    try:
        bid_dec = Decimal(str(bid))
        ask_dec = Decimal(str(ask))

        if bid_dec + ask_dec == 0:
            return Decimal("0")

        mid_price = (ask_dec + bid_dec) / 2
        spread = ask_dec - bid_dec

        return (spread / mid_price) * Decimal("100")
    except Exception as e:
        logger.error(
            f"Error in calculate_spread_percent(bid={bid}, ask={ask}): {type(e).__name__}: {e}"
        )
        raise


def is_price_in_range(
    price: Numeric,
    low: Numeric,
    high: Numeric,
    exclusive: bool = False,
) -> bool:
    """
    Check if a price is within a range.

    Args:
        price: The price to check
        low: The lower bound
        high: The upper bound
        exclusive: If True, use exclusive bounds (< and >)

    Returns:
        True if price is in range

    Examples:
        >>> is_price_in_range(50, 40, 60)
        True
        >>> is_price_in_range(40, 40, 60, exclusive=True)
        False
    """
    try:
        price_dec = Decimal(str(price))
        low_dec = Decimal(str(low))
        high_dec = Decimal(str(high))

        if exclusive:
            return low_dec < price_dec < high_dec
        return low_dec <= price_dec <= high_dec
    except Exception as e:
        logger.error(
            f"Error in is_price_in_range(price={price}, low={low}, high={high}): {type(e).__name__}: {e}"
        )
        raise


def basis_points_to_decimal(basis_points: Numeric) -> Decimal:
    """
    Convert basis points to decimal form.

    1 basis point = 0.0001 = 0.01%

    Args:
        basis_points: Value in basis points

    Returns:
        Decimal representation

    Examples:
        >>> basis_points_to_decimal(100)
        Decimal('0.01')  # 100 bps = 1%
        >>> basis_points_to_decimal(50)
        Decimal('0.005')  # 50 bps = 0.5%
    """
    try:
        return Decimal(str(basis_points)) / Decimal("10000")
    except Exception as e:
        logger.error(
            f"Error in basis_points_to_decimal(basis_points={basis_points}): {type(e).__name__}: {e}"
        )
        raise


def calculate_price_adjustment(
    base_price: Numeric,
    percentage: Numeric,
    is_positive: bool = True,
) -> Decimal:
    """
    Calculate a price adjustment based on percentage.

    Args:
        base_price: The starting price
        percentage: The percentage to adjust (as whole number, e.g., 5 for 5%)
        is_positive: If True, add percentage; if False, subtract

    Returns:
        The adjustment amount (not the new price)

    Examples:
        >>> calculate_price_adjustment(100, 5, True)
        Decimal('5')  # 5% of 100
        >>> calculate_price_adjustment(100, 5, False)
        Decimal('-5')  # -5% of 100
    """
    try:
        base_dec = Decimal(str(base_price))
        perc_dec = Decimal(str(percentage)) / Decimal("100")

        adjustment = base_dec * perc_dec
        return adjustment if is_positive else -adjustment
    except Exception as e:
        logger.error(
            f"Error in calculate_price_adjustment(base_price={base_price}, percentage={percentage}): {type(e).__name__}: {e}"
        )
        raise


def clamp_price(
    price: Numeric,
    min_price: Numeric,
    max_price: Numeric,
) -> Decimal:
    """
    Clamp a price to be within a min/max range.

    Args:
        price: The price to clamp
        min_price: The minimum allowed price
        max_price: The maximum allowed price

    Returns:
        The clamped price

    Examples:
        >>> clamp_price(50, 40, 60)
        Decimal('50')
        >>> clamp_price(30, 40, 60)
        Decimal('40')
        >>> clamp_price(70, 40, 60)
        Decimal('60')
    """
    try:
        price_dec = Decimal(str(price))
        min_dec = Decimal(str(min_price))
        max_dec = Decimal(str(max_price))

        return max(min_dec, min(max_dec, price_dec))
    except Exception as e:
        logger.error(
            f"Error in clamp_price(price={price}, min_price={min_price}, max_price={max_price}): {type(e).__name__}: {e}"
        )
        raise


def calculate_mid_price(bid: Numeric, ask: Numeric) -> Decimal:
    """
    Calculate the mid price between bid and ask.

    Args:
        bid: The best bid price
        ask: The best ask price

    Returns:
        The mid price
    """
    try:
        bid_dec = Decimal(str(bid))
        ask_dec = Decimal(str(ask))
        return (bid_dec + ask_dec) / Decimal("2")
    except Exception as e:
        logger.error(
            f"Error in calculate_mid_price(bid={bid}, ask={ask}): {type(e).__name__}: {e}"
        )
        raise


def calculate_price_change_percent(
    start_price: Numeric,
    end_price: Numeric,
) -> Decimal:
    """
    Calculate the percentage change between two prices.

    Args:
        start_price: The starting price
        end_price: The ending price

    Returns:
        The percentage change (can be negative)

    Examples:
        >>> calculate_price_change_percent(100, 110)
        Decimal('10')  # 10% increase
        >>> calculate_price_change_percent(100, 90)
        Decimal('-10')  # 10% decrease
    """
    try:
        start_dec = Decimal(str(start_price))
        end_dec = Decimal(str(end_price))

        if start_dec == 0:
            return Decimal("0")

        return ((end_dec - start_dec) / start_dec) * Decimal("100")
    except Exception as e:
        logger.error(
            f"Error in calculate_price_change_percent(start_price={start_price}, end_price={end_price}): {type(e).__name__}: {e}"
        )
        raise


def compare_numbers(num1: Numeric, operator: str, num2: Numeric) -> bool:
    """
    Safely compare two numbers that may be floats or Decimals.

    Converts both numbers to Decimal via string representation for
    accurate comparison (avoids float precision issues).

    Args:
        num1: First number (can be float, Decimal, int)
        operator: Comparison operator ("==", ">", "<", ">=", "<=")
        num2: Second number (can be float, Decimal, int)

    Returns:
        Result of the comparison

    Examples:
        >>> compare_numbers(0.1 + 0.2, "==", 0.3)
        True  # Works despite float precision issues
        >>> compare_numbers(Decimal("100"), ">", 99.5)
        True
    """
    try:
        dec1 = Decimal(str(num1))
        dec2 = Decimal(str(num2))

        if operator == "==":
            return dec1 == dec2
        elif operator == ">":
            return dec1 > dec2
        elif operator == "<":
            return dec1 < dec2
        elif operator == ">=":
            return dec1 >= dec2
        elif operator == "<=":
            return dec1 <= dec2
        else:
            raise ValueError(f"Unknown operator: {operator}")
    except Exception as e:
        logger.error(
            f"Error in compare_numbers(num1={num1}, operator={operator}, num2={num2}): {type(e).__name__}: {e}"
        )
        raise
