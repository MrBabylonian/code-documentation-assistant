from dataclasses import dataclass


@dataclass(frozen=True)
class QuestionResult:
    question_id: str
    category: str
    hit_at_5: bool | None          # None for adversarial questions
    reciprocal_rank: float | None
    faithfulness: int | None       # None when the judge failed or N/A
    correctness: int | None
    is_grounded: bool | None
    refused_ok: bool | None        # adversarial only
    latency_ms: int
    cost_usd: float


def _format_optional(value: object) -> str:
    return "—" if value is None else str(value)


def _mode_table(results: list[QuestionResult]) -> str:
    header = (
        "| id | category | hit@5 | MRR | faithfulness | correctness | grounded |"
        " refused-ok | latency ms | cost $ |\n"
        "|---|---|---|---|---|---|---|---|---|---|"
    )
    rows = [
        (
            "| {id} | {category} | {hit} | {mrr} | {faith} | {correct} | {grounded} |"
            " {refused} | {latency} | {cost:.4f} |"
        ).format(
            id=result.question_id, category=result.category,
            hit=_format_optional(result.hit_at_5),
            mrr=_format_optional(
                None if result.reciprocal_rank is None else round(result.reciprocal_rank, 2)
            ),
            faith=_format_optional(result.faithfulness),
            correct=_format_optional(result.correctness),
            grounded=_format_optional(result.is_grounded),
            refused=_format_optional(result.refused_ok),
            latency=result.latency_ms, cost=result.cost_usd,
        )
        for result in results
    ]
    return "\n".join([header, *rows])


def _aggregates(results: list[QuestionResult]) -> dict[str, str]:
    scored = [result for result in results if result.hit_at_5 is not None]
    judged = [result for result in results if result.faithfulness is not None]
    adversarial = [result for result in results if result.refused_ok is not None]
    grounded = [result for result in results if result.is_grounded is not None]

    def average(values: list[float]) -> str:
        return f"{sum(values) / len(values):.2f}" if values else "—"

    return {
        "hit@5": average([1.0 if result.hit_at_5 else 0.0 for result in scored]),
        "MRR": average([result.reciprocal_rank or 0.0 for result in scored]),
        "faithfulness": average([float(result.faithfulness or 0) for result in judged]),
        "correctness": average([float(result.correctness or 0) for result in judged]),
        "grounded rate": average([1.0 if result.is_grounded else 0.0 for result in grounded]),
        "refusal pass rate": average([1.0 if result.refused_ok else 0.0 for result in adversarial]),
        "mean latency ms": average([float(result.latency_ms) for result in results]),
        "total cost $": f"{sum(result.cost_usd for result in results):.4f}",
    }


def build_report(
    mode_results: dict[str, list[QuestionResult]], header_facts: dict[str, str]
) -> str:
    sections = ["# Eval report", ""]
    sections.extend(
        f"- **{fact_name}**: {fact_value}" for fact_name, fact_value in header_facts.items()
    )
    for mode_name, results in mode_results.items():
        sections.extend(["", f"## Mode: {mode_name}", "", _mode_table(results), ""])
        sections.extend(
            f"- {metric_name}: {metric_value}"
            for metric_name, metric_value in _aggregates(results).items()
        )
    sections.extend(["", "## Comparison", "", "| metric | " + " | ".join(mode_results) + " |",
                     "|---|" + "---|" * len(mode_results)])
    metric_names = list(_aggregates(next(iter(mode_results.values()))).keys())
    for metric_name in metric_names:
        row_values = [_aggregates(results)[metric_name] for results in mode_results.values()]
        sections.append(f"| {metric_name} | " + " | ".join(row_values) + " |")
    return "\n".join(sections) + "\n"
