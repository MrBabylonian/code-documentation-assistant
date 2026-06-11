import argparse
import asyncio
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import yaml
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from codedoc.domain.chat import AnswerMode
from codedoc.domain.code_repository import IngestionStatus
from codedoc.domain.streaming import AnswerCompletedEvent, ErrorEvent
from codedoc.evals.eval_report_builder import QuestionResult, build_report
from codedoc.main import ApplicationContainer, build_default_container
from codedoc.settings import AppSettings

GOLDEN_QUESTIONS_PATH = Path(__file__).resolve().parent / "golden_questions.yaml"
JUDGE_RUBRIC_PATH = Path(__file__).resolve().parent / "judge_rubric.md"
DEFAULT_REPOSITORY_URL = "https://github.com/fastapi/full-stack-fastapi-template"
RETRIEVAL_TOP_K = 5
REFUSAL_MARKER = "only answer questions about the ingested repository"
JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)

QuestionCategory = Literal[
    "symbol_location", "multi_hop", "api_endpoints", "dependencies", "adversarial"
]


class GoldenQuestion(BaseModel):
    id: str
    category: QuestionCategory
    question: str
    expected_files: list[str] = []
    reference_answer: str = ""
    expects_refusal: bool = False


@dataclass(frozen=True)
class JudgeScores:
    faithfulness: int
    correctness: int
    justification: str


def load_golden_questions() -> list[GoldenQuestion]:
    raw_dataset = yaml.safe_load(GOLDEN_QUESTIONS_PATH.read_text(encoding="utf-8"))
    return [GoldenQuestion(**entry) for entry in raw_dataset["questions"]]


def parse_judge_output(judge_text: str) -> JudgeScores | None:
    json_match = JSON_OBJECT_PATTERN.search(judge_text)
    if json_match is None:
        return None
    try:
        parsed = json.loads(json_match.group(0))
        return JudgeScores(
            faithfulness=int(parsed["faithfulness"]),
            correctness=int(parsed["correctness"]),
            justification=str(parsed.get("justification", "")),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        # judge output is model-generated; malformed JSON means "no score", not a crash
        return None


async def _judge(
    judge_chat_model: BaseChatModel,
    question: GoldenQuestion,
    answer_text: str,
    cited_files: list[str],
) -> JudgeScores | None:
    rubric_text = JUDGE_RUBRIC_PATH.read_text(encoding="utf-8")
    judge_request = (
        f"Question: {question.question}\n"
        f"Reference answer: {question.reference_answer}\n"
        f"Assistant answer: {answer_text}\n"
        f"Cited files: {', '.join(cited_files) or 'none'}"
    )
    judge_messages = [SystemMessage(content=rubric_text), HumanMessage(content=judge_request)]
    first_response = await judge_chat_model.ainvoke(judge_messages)
    judge_scores = parse_judge_output(str(first_response.content))
    if judge_scores is not None:
        return judge_scores
    # one retry: judge output is model-generated and occasionally malformed
    retry_response = await judge_chat_model.ainvoke(judge_messages)
    return parse_judge_output(str(retry_response.content))


async def _evaluate_question(
    container: ApplicationContainer,
    repository_id: str,
    question: GoldenQuestion,
    mode: AnswerMode,
) -> QuestionResult:
    question_answering_service = container.question_answering_service
    chunk_searcher = container.chunk_searcher
    embeddings = container.embeddings
    judge_chat_model = container.judge_chat_model
    if (
        question_answering_service is None
        or chunk_searcher is None
        or embeddings is None
        or judge_chat_model is None
    ):
        raise RuntimeError("the default container must provide answering and retrieval services")

    started_at_seconds = time.monotonic()
    completed_answer = None
    error_message = None
    async for event in question_answering_service.answer_stream(
        repository_id, question.question, mode, history=()
    ):
        if isinstance(event, AnswerCompletedEvent):
            completed_answer = event.answer
        elif isinstance(event, ErrorEvent):
            error_message = event.message
    latency_ms = int((time.monotonic() - started_at_seconds) * 1000)

    if question.expects_refusal:
        was_refused = error_message is not None or (
            completed_answer is not None and REFUSAL_MARKER in completed_answer.text.lower()
        )
        return QuestionResult(
            question_id=question.id, category=question.category, hit_at_5=None,
            reciprocal_rank=None, faithfulness=None, correctness=None, is_grounded=None,
            refused_ok=was_refused, latency_ms=latency_ms,
            cost_usd=completed_answer.estimated_cost_usd if completed_answer else 0.0,
        )

    query_embedding = await embeddings.aembed_query(question.question)
    retrieved_hits = await chunk_searcher.search(
        repository_id, question.question, query_embedding, RETRIEVAL_TOP_K
    )
    reciprocal_rank = 0.0
    for hit_rank, hit in enumerate(retrieved_hits, start=1):
        if any(hit.chunk.file_path.startswith(expected) for expected in question.expected_files):
            reciprocal_rank = 1.0 / hit_rank
            break

    answer_text = completed_answer.text if completed_answer else (error_message or "")
    cited_files = (
        [citation.file_path for citation in completed_answer.citations]
        if completed_answer
        else []
    )
    judge_scores = await _judge(judge_chat_model, question, answer_text, cited_files)
    return QuestionResult(
        question_id=question.id, category=question.category,
        hit_at_5=reciprocal_rank > 0.0, reciprocal_rank=reciprocal_rank,
        faithfulness=judge_scores.faithfulness if judge_scores else None,
        correctness=judge_scores.correctness if judge_scores else None,
        is_grounded=completed_answer.is_grounded if completed_answer else False,
        refused_ok=None, latency_ms=latency_ms,
        cost_usd=completed_answer.estimated_cost_usd if completed_answer else 0.0,
    )


async def _evaluate_question_resiliently(
    container: ApplicationContainer,
    repository_id: str,
    question: GoldenQuestion,
    mode: AnswerMode,
) -> QuestionResult:
    """One retry per question, then a metrics-empty row — a transient provider error
    (431s were observed in the wild) must degrade the report, not kill the run."""
    for attempt_number in (1, 2):
        try:
            return await _evaluate_question(container, repository_id, question, mode)
        except Exception as evaluation_error:  # noqa: BLE001
            print(f"  {question.id} attempt {attempt_number} failed: {evaluation_error}")
            if attempt_number == 1:
                await asyncio.sleep(2)
    return QuestionResult(
        question_id=question.id, category=question.category, hit_at_5=None,
        reciprocal_rank=None, faithfulness=None, correctness=None, is_grounded=None,
        refused_ok=None, latency_ms=0, cost_usd=0.0,
    )


async def run_evals(
    repository_url: str,
    modes: list[AnswerMode],
    embedding_model_override: str | None,
) -> str:
    # pyright lacks mypy's pydantic-settings plugin: openai_api_key arrives from the env
    if embedding_model_override is None:
        settings = AppSettings()  # pyright: ignore[reportCallIssue]
    else:
        settings = AppSettings(  # pyright: ignore[reportCallIssue]
            embedding_model_name=embedding_model_override
        )
    container = build_default_container(settings)
    if container.index_bootstrapper is not None:
        # the runner bypasses the FastAPI lifespan, so it must create the indices itself
        await container.index_bootstrapper.bootstrap()
    repository_ingestion_service = container.repository_ingestion_service
    if repository_ingestion_service is None:
        raise RuntimeError("the default container must provide the ingestion service")
    print(f"ingesting {repository_url} (embedder: {settings.embedding_model_name}) …")
    repository_id = await repository_ingestion_service.ingest(repository_url)
    repository = await container.repository_store.get(repository_id)
    if repository is None or repository.status is not IngestionStatus.READY:
        failure_reason = repository.error_message if repository else "missing"
        raise SystemExit(f"ingestion failed: {failure_reason}")

    questions = load_golden_questions()
    mode_results: dict[str, list[QuestionResult]] = {}
    for mode in modes:
        print(f"running {len(questions)} questions in mode={mode.value} …")
        mode_results[mode.value] = [
            await _evaluate_question_resiliently(container, repository_id, question, mode)
            for question in questions
        ]

    report_markdown = build_report(mode_results, header_facts={
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "repository": repository.name,
        "chat_model": settings.chat_model_name,
        "embedding_model": settings.embedding_model_name,
    })
    if container.opensearch_client is not None:
        await container.opensearch_client.close()
    return report_markdown


def _write_report(report_markdown: str, output_directory: Path) -> Path:
    output_directory.mkdir(parents=True, exist_ok=True)
    report_path = output_directory / f"{datetime.now(UTC).date().isoformat()}-eval-report.md"
    report_path.write_text(report_markdown, encoding="utf-8")
    return report_path


def main() -> None:
    argument_parser = argparse.ArgumentParser(description="Run the golden-dataset evals.")
    argument_parser.add_argument("--repository-url", default=DEFAULT_REPOSITORY_URL)
    argument_parser.add_argument(
        "--mode", choices=["agentic", "single_shot", "both"], default="both"
    )
    argument_parser.add_argument("--embedding-model", default=None,
                                 help="override the embedder (forces a fresh ingest)")
    argument_parser.add_argument("--output-dir", default="evals/reports", type=Path)
    arguments = argument_parser.parse_args()
    selected_modes = (
        [AnswerMode.AGENTIC, AnswerMode.SINGLE_SHOT]
        if arguments.mode == "both"
        else [AnswerMode(arguments.mode)]
    )
    report_markdown = asyncio.run(run_evals(
        arguments.repository_url, selected_modes, arguments.embedding_model
    ))
    report_path = _write_report(report_markdown, arguments.output_dir)
    print(f"report written: {report_path}")


if __name__ == "__main__":
    main()
