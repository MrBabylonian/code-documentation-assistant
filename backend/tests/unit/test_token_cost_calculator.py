import pytest

from codedoc.application.answering.token_cost_calculator import TokenCostCalculator


def test_cost_is_per_million_tokens() -> None:
    calculator = TokenCostCalculator(input_cost_per_mtok_usd=0.75, output_cost_per_mtok_usd=4.50)
    assert calculator.estimate_cost_usd(1_000_000, 0) == pytest.approx(0.75)
    assert calculator.estimate_cost_usd(0, 2_000_000) == pytest.approx(9.00)
    assert calculator.estimate_cost_usd(10_000, 2_000) == pytest.approx(0.0075 + 0.009)
    assert calculator.estimate_cost_usd(0, 0) == 0.0
