from codedoc.evals.eval_report_builder import QuestionResult, build_report


def _result(question_id: str, **overrides: object) -> QuestionResult:
    base = QuestionResult(
        question_id=question_id, category="symbol_location", hit_at_5=True,
        reciprocal_rank=1.0, faithfulness=5, correctness=4, is_grounded=True,
        refused_ok=None, latency_ms=1200, cost_usd=0.0021,
    )
    return QuestionResult(**{**base.__dict__, **overrides})  # type: ignore[arg-type]


def test_report_contains_per_mode_tables_and_aggregates() -> None:
    report_markdown = build_report(
        mode_results={
            "agentic": [_result("sl-01"), _result("ad-01", category="adversarial",
                                                  hit_at_5=None, reciprocal_rank=None,
                                                  faithfulness=None, correctness=None,
                                                  is_grounded=None, refused_ok=True)],
            "single_shot": [_result("sl-01", faithfulness=3)],
        },
        header_facts={"chat_model": "gpt-5.4-mini", "embedding_model": "text-embedding-3-large",
                      "repository": "fastapi/full-stack-fastapi-template"},
    )
    assert "## Mode: agentic" in report_markdown
    assert "## Mode: single_shot" in report_markdown
    assert "sl-01" in report_markdown and "ad-01" in report_markdown
    assert "hit@5" in report_markdown
    assert "## Comparison" in report_markdown
    assert "gpt-5.4-mini" in report_markdown
