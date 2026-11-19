"""The report printed when a run finishes: overall, by category and by module,
with the change in each headline score since the last run."""

from collections.abc import Callable
from typing import get_args

from askmynotes.evaluation.cases import Category
from askmynotes.evaluation.results import (
    Headline,
    QuestionResult,
    RunResults,
    summarise,
)

# name in Headline -> (label, how to show it)
Format = Callable[[float], str]


def _score(value: float) -> str:
    return f"{value:.3f}"


def _mark(value: float) -> str:  # the judge's 1 to 5
    return f"{value:.2f}"


def _percent(value: float) -> str:
    return f"{value:.0%}"


HEADLINES: list[tuple[str, str, Format]] = [
    ("mrr", "Retrieval MRR", _score),
    ("ndcg", "Retrieval nDCG", _score),
    ("keyword_coverage", "Keyword coverage", _score),
    ("accuracy", "Judge: accuracy (1-5)", _mark),
    ("completeness", "Judge: completeness (1-5)", _mark),
    ("relevance", "Judge: relevance (1-5)", _mark),
    ("not_covered_rate", "Says 'not covered' when it should", _percent),
    ("behaviour_pass_rate", "Behaviour checks passed", _percent),
]


def _shown(value: float | None, show: Format) -> str:
    return "-" if value is None else show(value)


def _change(now: float | None, before: str | None, show: Format) -> str:
    """The signed change since the last run, in the score's own units."""
    if now is None or not before:
        return ""
    difference = now - float(before)
    return f"{'+' if difference >= 0 else '-'}{show(abs(difference))}"


def overall_section(headline: Headline, previous: dict[str, str] | None) -> list[str]:
    """The headline scores, each with its change since the last run."""
    lines = ["OVERALL" + " " * 29 + "now   change"]
    for name, label, show in HEADLINES:
        value = getattr(headline, name)
        before = previous.get(name) if previous else None
        lines.append(
            f"  {label:<36}{_shown(value, show):>7}  {_change(value, before, show)}"
        )
    return lines


def searches_section(results: RunResults) -> list[str]:
    """How the agent used the search: how often, and whether it named its sources."""
    searched = [r for r in [*results.questions, *results.behaviour] if r.searches]
    if not searched:
        return []
    total = sum(len(r.searches or []) for r in searched)
    missing = [r for r in searched if r.sources_line_found is False]
    lines = [
        "",
        "AGENT SEARCHES",
        f"  {len(searched)} answers searched the notes, {total} searches in all "
        f"({total / len(searched):.2f} each).",
        f"  {len(searched) - len(missing)} of {len(searched)} ended with a sources "
        "line.",
    ]
    lines += [f"    no sources line: {r.question}" for r in missing]
    return lines


def breakdown_section(title: str, groups: dict[str, list[QuestionResult]]) -> list[str]:
    """One row of scores for each group of questions."""
    columns = "  {:<28}{:>3}{:>7}{:>7}{:>7}{:>6}{:>6}{:>6}{:>8}"
    lines = [
        "",
        title.upper(),
        columns.format("", "n", "MRR", "nDCG", "Cover", "Acc", "Comp", "Rel", "NotCov"),
    ]
    for name, questions in groups.items():
        h = summarise(questions)
        lines.append(
            columns.format(
                name,
                len(questions),
                _shown(h.mrr, _score),
                _shown(h.ndcg, _score),
                _shown(h.keyword_coverage, _score),
                _shown(h.accuracy, _mark),
                _shown(h.completeness, _mark),
                _shown(h.relevance, _mark),
                _shown(h.not_covered_rate, _percent),
            )
        )
    return lines


def format_report(results: RunResults, previous: dict[str, str] | None) -> str:
    """The whole report as text. `previous` is the last row of history.csv."""
    when = results.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    header = f"Evaluation run {when}" + (f" - {results.note}" if results.note else "")
    lines = [
        header,
        f"Models: {results.chat_model}, {results.embedding_model}. "
        f"Time taken: {results.seconds:.0f}s.",
        "",
        *overall_section(results.headline, previous),
    ]
    if previous is None:
        lines.append("  (first run, so there is nothing to compare with)")

    categories = {
        category: [q for q in results.questions if q.category == category]
        for category in get_args(Category)
    }
    modules: dict[str, list[QuestionResult]] = {}
    for question in results.questions:
        modules.setdefault(question.module, []).append(question)
    lines += searches_section(results)
    lines += breakdown_section("By category", categories)
    lines += breakdown_section("By module", modules)

    lines += ["", "BEHAVIOUR"]
    for case in results.behaviour:
        if case.error:
            lines.append(f"  ERROR  {case.question}: {case.error}")
        elif case.passed:
            lines.append(f"  pass   {case.question}")
        else:
            lines.append(f"  FAIL   {case.question}")
            lines += [f"           {problem}" for problem in case.problems]

    failed = [q for q in results.questions if q.error]
    if failed:
        lines += [
            "",
            f"{len(failed)} question(s) failed and are left out of the scores:",
        ]
        lines += [f"  {q.module}: {q.question}: {q.error}" for q in failed]
    return "\n".join(lines)
