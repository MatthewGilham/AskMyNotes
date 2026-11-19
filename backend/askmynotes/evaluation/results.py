"""What a run produces: per-question results, the headline scores, and saving.

A run is saved as a detailed JSON file named with its date and time, plus one
row in `history.csv`. Results hold scores, answers and references to slides
(file, module, slide or page number), never slide text.
"""

import csv
from datetime import datetime
from pathlib import Path
from statistics import mean

from pydantic import BaseModel

from askmynotes.chats.models import Source
from askmynotes.evaluation.cases import Category, Expectation
from askmynotes.evaluation.judge import JudgeScores
from askmynotes.notes.search import SearchMade

HISTORY_FILE = "history.csv"
HISTORY_COLUMNS = [
    "timestamp",
    "note",
    "chat_model",
    "embedding_model",
    "mrr",
    "ndcg",
    "keyword_coverage",
    "accuracy",
    "completeness",
    "relevance",
    "not_covered_rate",
    "behaviour_pass_rate",
    "seconds",
]


class RetrievedSlide(Source):
    """A search result: which slide or page, and how many keywords it held."""

    keywords_matched: int


class RetrievalScores(BaseModel):
    """How well the notes search found slides containing the keywords."""

    mrr: float
    ndcg: float
    keyword_coverage: float
    results: list[RetrievedSlide]


class QuestionResult(BaseModel):
    """Everything about one notes question."""

    question: str
    category: Category
    module: str  # short name
    # Set if something failed; the question is then left out of every average.
    error: str | None = None
    searched: bool | None = None
    searches: list[SearchMade] | None = None
    sources_line_found: bool | None = None
    answer: str | None = None
    sources: list[Source] | None = None
    retrieval: RetrievalScores | None = None
    scores: JudgeScores | None = None
    says_not_covered: bool | None = None


class BehaviourResult(BaseModel):
    """Everything about one behaviour question."""

    question: str
    expect: Expectation
    error: str | None = None
    searched: bool | None = None
    web_searched: bool | None = None
    searches: list[SearchMade] | None = None
    sources_line_found: bool | None = None
    answer: str | None = None
    sources: list[Source] | None = None
    problems: list[str] = []
    passed: bool = False


class Headline(BaseModel):
    """The headline scores. A score is None when nothing could be measured."""

    mrr: float | None = None
    ndcg: float | None = None
    keyword_coverage: float | None = None
    accuracy: float | None = None
    completeness: float | None = None
    relevance: float | None = None
    not_covered_rate: float | None = None
    behaviour_pass_rate: float | None = None


class RunResults(BaseModel):
    """A whole run."""

    timestamp: datetime
    note: str
    chat_model: str
    embedding_model: str
    seconds: float
    headline: Headline
    questions: list[QuestionResult]
    behaviour: list[BehaviourResult]


def _mean(values: list[float]) -> float | None:
    return mean(values) if values else None


def summarise(
    questions: list[QuestionResult], behaviour: list[BehaviourResult] | None = None
) -> Headline:
    """Average the scores of these questions (and behaviour results, if given)."""
    retrieval = [q.retrieval for q in questions if q.retrieval]
    judged = [q.scores for q in questions if q.scores]
    not_covered = [
        q.says_not_covered
        for q in questions
        if q.category == "not_covered" and q.says_not_covered is not None
    ]
    checked = [b.passed for b in behaviour or [] if b.error is None]
    return Headline(
        mrr=_mean([r.mrr for r in retrieval]),
        ndcg=_mean([r.ndcg for r in retrieval]),
        keyword_coverage=_mean([r.keyword_coverage for r in retrieval]),
        accuracy=_mean([s.accuracy for s in judged]),
        completeness=_mean([s.completeness for s in judged]),
        relevance=_mean([s.relevance for s in judged]),
        not_covered_rate=_mean([float(says) for says in not_covered]),
        behaviour_pass_rate=_mean([float(passed) for passed in checked]),
    )


def last_run(results_dir: Path) -> dict[str, str] | None:
    """The most recent row of history.csv, or None before the first run."""
    history = results_dir / HISTORY_FILE
    if not history.exists():
        return None
    with history.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    return rows[-1] if rows else None


def save_run(results: RunResults, results_dir: Path) -> Path:
    """Write the detailed results file and add the run to history.csv."""
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp = results.timestamp.strftime("%Y-%m-%d_%H%M%S")
    detail_file = results_dir / f"run_{stamp}.json"
    detail_file.write_text(results.model_dump_json(indent=2), encoding="utf-8")

    history = results_dir / HISTORY_FILE
    is_new = not history.exists()
    row = {
        "timestamp": results.timestamp.isoformat(timespec="seconds"),
        "note": results.note,
        "chat_model": results.chat_model,
        "embedding_model": results.embedding_model,
        "seconds": round(results.seconds),
        **{
            name: "" if score is None else round(score, 4)
            for name, score in results.headline.model_dump().items()
        },
    }
    with history.open("a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=HISTORY_COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)
    return detail_file
