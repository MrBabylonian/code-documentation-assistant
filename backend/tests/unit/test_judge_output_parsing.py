from codedoc.evals.eval_runner import parse_judge_output


def test_parses_clean_judge_json() -> None:
    judge_scores = parse_judge_output(
        '{"faithfulness": 4, "correctness": 5, "justification": "ok"}'
    )
    assert judge_scores is not None
    assert judge_scores.faithfulness == 4 and judge_scores.correctness == 5


def test_parses_json_wrapped_in_prose_or_fences() -> None:
    judge_scores = parse_judge_output(
        'Here you go:\n```json\n{"faithfulness": 2, "correctness": 3, "justification": "x"}\n```'
    )
    assert judge_scores is not None and judge_scores.faithfulness == 2


def test_returns_none_for_garbage() -> None:
    assert parse_judge_output("I cannot grade this.") is None
    assert parse_judge_output('{"faithfulness": "high"}') is None
