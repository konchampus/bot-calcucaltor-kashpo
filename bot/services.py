from __future__ import annotations

from typing import Iterable

PI = 3.14


def parse_positive_float(raw_value: str) -> float:
    normalized = raw_value.strip().replace(",", ".")
    value = float(normalized)
    if value <= 0:
        raise ValueError("Value must be greater than zero")
    return value


def parse_positive_int(raw_value: str) -> int:
    value = int(raw_value.strip())
    if value <= 0:
        raise ValueError("Value must be greater than zero")
    return value


def compute_base_length(
    rack_length: float,
    rattan_width: float,
    basket_diameter: float,
    harness_count: int,
) -> float:
    return (rack_length / rattan_width) * PI * basket_diameter / harness_count


def compute_final_length(base_length: float, pattern_values: Iterable[float]) -> float:
    return round(base_length + sum(pattern_values), 3)
