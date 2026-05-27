from bot.services import (
    compute_base_length,
    compute_final_length,
    parse_positive_float,
    parse_positive_int,
)


def test_compute_formula_and_rounding() -> None:
    base = compute_base_length(
        rack_length=100.0,
        rattan_width=2.0,
        basket_diameter=30.0,
        harness_count=10,
    )
    final = compute_final_length(base, [1.1114, 0.2222])
    assert round(base, 3) == 471.0
    assert final == 472.334


def test_parsing_with_comma_and_dot() -> None:
    assert parse_positive_float("10,5") == 10.5
    assert parse_positive_float("10.5") == 10.5
    assert parse_positive_int("7") == 7


def test_parsing_rejects_non_positive() -> None:
    for value in ["0", "-1", "-2.2"]:
        try:
            parse_positive_float(value)
            assert False, "Expected ValueError"
        except ValueError:
            pass
