from codedoc.evals.eval_runner import load_golden_questions


def test_dataset_loads_and_satisfies_schema_invariants() -> None:
    questions = load_golden_questions()
    assert len(questions) == 25
    assert len({question.id for question in questions}) == 25
    for question in questions:
        if question.category == "adversarial":
            assert question.expects_refusal is True
        else:
            assert question.expected_files, f"{question.id} needs expected_files"
            assert question.reference_answer, f"{question.id} needs a reference answer"
    categories = {question.category for question in questions}
    assert categories == {
        "symbol_location",
        "multi_hop",
        "api_endpoints",
        "dependencies",
        "adversarial",
    }
