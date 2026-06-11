TOKENS_PER_MILLION = 1_000_000


class TokenCostCalculator:
    def __init__(self, input_cost_per_mtok_usd: float, output_cost_per_mtok_usd: float) -> None:
        self._input_cost_per_mtok_usd = input_cost_per_mtok_usd
        self._output_cost_per_mtok_usd = output_cost_per_mtok_usd

    def estimate_cost_usd(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens / TOKENS_PER_MILLION * self._input_cost_per_mtok_usd
            + output_tokens / TOKENS_PER_MILLION * self._output_cost_per_mtok_usd
        )
