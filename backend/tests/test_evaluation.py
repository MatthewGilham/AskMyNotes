"""Tests for the evaluation: its measures, its checks, its test sets and its
results files.

Nothing here calls a model. The measures use fixed inputs, and the runs use a
fake model that follows a script, with fake embeddings and made-up slides.
"""

import asyncio
import csv
import json
import math
from collections import Counter
from pathlib import Path

import pytest
from helpers import TEST_SETTINGS, lost_connection
from langchain_core.messages import BaseMessage, ToolMessage

from askmynotes.agent.agent import Agent
from askmynotes.chats.models import Source
from askmynotes.evaluation.agent_run import AgentRun, ask_agent
from askmynotes.evaluation.cases import (
    BehaviourCase,
    Expectation,
    QuestionCase,
    load_behaviour_cases,
    load_question_cases,
)
from askmynotes.evaluation.judge import judge_answer
from askmynotes.evaluation.metrics import (
    check_behaviour,
    keyword_coverage,
    mean_reciprocal_rank,
    ndcg,
    says_not_covered,
)
from askmynotes.evaluation.report import format_report
from askmynotes.evaluation.results import RunResults, last_run, save_run
from askmynotes.evaluation.runner import evaluate
from askmynotes.fake_model import (
    FakeChatModel,
    FakeEmbeddings,
    FakeReply,
    last_human_text,
    text_of,
)
from askmynotes.notes.chunking import Chunk
from askmynotes.notes.search import NotesSearch
from askmynotes.notes.store import NotesStore
from askmynotes.settings import Module

# The measures, with fixed inputs


def test_mrr_and_ndcg_on_a_known_ranking() -> None:
    # Keywords held by each result, best-ranked first: the first result has
    # none, the second has two, the third has one.
    gains = [0, 2, 1]

    assert mean_reciprocal_rank(gains) == 0.5
    found = 2 / math.log2(3) + 1 / math.log2(4)
    best_possible = 2 / math.log2(2) + 1 / math.log2(3)
    assert ndcg(gains) == pytest.approx(found / best_possible)


def test_mrr_and_ndcg_are_perfect_when_the_best_result_is_first() -> None:
    assert mean_reciprocal_rank([3, 1, 0]) == 1.0
    assert ndcg([3, 1, 0]) == pytest.approx(1.0)


def test_mrr_and_ndcg_are_zero_when_nothing_is_relevant() -> None:
    assert mean_reciprocal_rank([0, 0, 0]) == 0.0
    assert ndcg([0, 0, 0]) == 0.0


def test_keyword_coverage() -> None:
    texts = ["Depreciation spreads the cost", "The straight-line method"]

    # Ignores case, and counts a keyword found in any result.
    assert keyword_coverage(texts, ["depreciation", "STRAIGHT-LINE", "goodwill"]) == (
        pytest.approx(2 / 3)
    )
    assert keyword_coverage([], ["goodwill"]) == 0.0


@pytest.mark.parametrize(
    "answer",
    [
        "Your notes don't cover this.",
        "your notes don’t cover this. Here is a general answer.",
    ],
)
def test_not_covered_is_recognised_with_either_apostrophe(answer: str) -> None:
    assert says_not_covered(answer)
    assert not says_not_covered("Your notes explain this.")


def source(module: str) -> Source:
    return Source(file_name="a.pdf", module=module, location="page", number=1)


def test_behaviour_checks_pass_and_fail() -> None:
    good = AgentRun(
        answer="Notes answer.\n\n:::beyond\nExtra.\n:::",
        sources=[source("AFA")],
        searched=True,
        web_searched=False,
        searches=[],
        sources_line_found=True,
    )
    plain = AgentRun(
        answer="Pasta.",
        sources=None,
        searched=False,
        web_searched=False,
        searches=[],
        sources_line_found=False,
    )
    everything = Expectation(
        searches=True,
        sources_listed=True,
        source_modules=["AFA", "FR"],
        beyond_label=True,
        not_covered=False,
    )

    # Passing.
    assert check_behaviour(everything, good) == []
    assert check_behaviour(Expectation(searches=False), plain) == []
    assert check_behaviour(Expectation(), good) == []  # nothing expected

    # Each expectation can fail on its own.
    assert check_behaviour(Expectation(searches=False), good)
    assert check_behaviour(Expectation(searches=True), plain)
    assert check_behaviour(Expectation(sources_listed=False), good)
    assert check_behaviour(Expectation(beyond_label=False), good)
    assert check_behaviour(Expectation(beyond_label=True), plain)
    assert check_behaviour(Expectation(not_covered=True), good)
    # A search of the web is checked separately from a search of the notes.
    searched_web = AgentRun(**{**good.__dict__, "web_searched": True})
    assert check_behaviour(Expectation(web_searches=True), searched_web) == []
    assert check_behaviour(Expectation(web_searches=False), searched_web)
    assert check_behaviour(Expectation(web_searches=True), good)
    assert check_behaviour(Expectation(web_searches=False), good) == []
    # A source from another module, or no sources at all, breaks the filter.
    assert check_behaviour(Expectation(source_modules=["FR"]), good)
    assert check_behaviour(Expectation(source_modules=["AFA"]), plain)
    # Sources from only some of the allowed modules are fine.
    assert check_behaviour(Expectation(source_modules=["AFA", "FR"]), good) == []


# The test sets


def test_the_small_test_set_has_ten_questions_per_module_and_a_not_covered_each() -> (
    None
):
    questions = load_question_cases()

    assert len(questions) == 50
    assert set(Counter(q.module for q in questions).values()) == {10}
    assert len({q.module for q in questions}) == 5
    for module in {q.module for q in questions}:
        categories = {q.category for q in questions if q.module == module}
        assert "not_covered" in categories, module


def test_only_not_covered_questions_have_no_keywords() -> None:
    for question in load_question_cases():
        assert (question.keywords == []) == (question.category == "not_covered")


def test_the_behaviour_test_set_loads() -> None:
    cases = load_behaviour_cases()

    # The ten from the pilot, and three about the web added in phase 21.
    assert len(cases) == 13
    assert any(c.expect.web_searches is True for c in cases)
    assert any(c.expect.web_searches is False for c in cases)
    assert any(c.expect.searches is False for c in cases)
    assert any(c.expect.source_modules for c in cases)
    assert any(c.expect.beyond_label for c in cases)


def test_a_misspelled_field_in_a_test_set_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "tests.jsonl"
    path.write_text('{"question": "Q?", "expect": {"search": true}}\n')

    with pytest.raises(ValueError, match="search"):
        load_behaviour_cases(path)


# A run with a fake model


MODULE = Module(name="Testing Module", short_name="TM", folder=Path("unused"))
# Made-up slide text that must never appear in the results.
SLIDE_TEXTS = [
    "Quokka depreciation schedule for the zebra ledger",
    "Wombat straight-line method of the narwhal register",
]


def scripted_model(judge_error: Exception | None = None) -> FakeChatModel:
    """A fake model: the judge gives fixed scores, a recipe question isn't
    searched, an options question isn't covered, and anything else searches the
    notes then answers using the first result."""

    def responder(messages: list[BaseMessage]) -> str | FakeReply:
        if "marking an answer" in text_of(messages[0]):
            if judge_error is not None:
                raise judge_error
            return (
                '```json\n{"accuracy": 4, "completeness": 3, "relevance": 5, '
                '"explanation": "Mostly right."}\n```'
            )
        question = last_human_text(messages)
        if "recipe" in question:
            return "Fry the vegetables."
        if isinstance(messages[-1], ToolMessage):
            if "options" in question:
                return (
                    "Your notes don't cover this.\n\n:::beyond\nOptions are "
                    "contracts.\n:::\n\nSources used: none"
                )
            return "Depreciation is spread over time.\n\nSources used: S1"
        return FakeReply(
            tool_call={"name": "search_notes", "args": {"query": question}}
        )

    return FakeChatModel(responder=responder)


QUESTIONS = [
    QuestionCase(
        question="What is depreciation?",
        keywords=["depreciation", "zebra"],
        reference_answer="Spreading cost.",
        category="definition",
        module="Testing Module",
    ),
    QuestionCase(
        question="How are options priced?",
        keywords=[],
        reference_answer="The notes don't cover this.",
        category="not_covered",
        module="Testing Module",
    ),
]
BEHAVIOUR = [
    BehaviourCase(question="Give me a recipe", expect=Expectation(searches=False)),
    BehaviourCase(
        question="Explain straight-line",
        expect=Expectation(searches=True, source_modules=["TM"]),
    ),
    # Fails on purpose: this question is searched.
    BehaviourCase(question="Explain depreciation", expect=Expectation(searches=False)),
]


def run_evaluation(
    tmp_path: Path, model: FakeChatModel, note: str = "a test"
) -> RunResults:
    store = NotesStore(tmp_path / "chroma", FakeEmbeddings(), "fake")
    store.add(
        [
            Chunk(
                id=f"TM/a.pdf#{number}#1",
                text=text,
                text_to_embed=text,
                metadata={
                    "file_id": "TM/a.pdf",
                    "module": "TM",
                    "file_name": "a.pdf",
                    "location": "page",
                    "number": number,
                    "part": 1,
                },
            )
            for number, text in enumerate(SLIDE_TEXTS, start=1)
        ]
    )
    settings = TEST_SETTINGS.model_copy(update={"modules": [MODULE]})
    return asyncio.run(
        evaluate(
            settings=settings,
            store=store,
            agent=Agent(model, NotesSearch(store, [MODULE], 8)),
            judge_model=model,
            chat_model_name="fake-chat",
            embedding_model_name="fake-embeddings",
            questions=QUESTIONS,
            behaviour_cases=BEHAVIOUR,
            note=note,
            concurrency=2,
        )
    )


def test_a_fake_run_writes_a_results_file_and_a_history_row_and_prints_a_report(
    tmp_path: Path,
) -> None:
    results_dir = tmp_path / "results"
    results = run_evaluation(tmp_path, scripted_model(), note="first try")

    # As the command does: the last run is read before this one is saved.
    previous = last_run(results_dir)
    detail_file = save_run(results, results_dir)
    report = format_report(results, previous)

    detail = json.loads(detail_file.read_text(encoding="utf-8"))
    assert detail_file.name.startswith("run_")
    first = detail["questions"][0]
    assert first["answer"] == "Depreciation is spread over time."
    assert first["sources"] == [
        {"file_name": "a.pdf", "module": "TM", "location": "page", "number": 1}
    ]
    assert first["scores"]["accuracy"] == 4
    # What the agent really searched for, and the slides it got (no text).
    assert first["searches"] == [
        {
            "query": "What is depreciation?",
            "modules": [],
            "results": [
                {"file_name": "a.pdf", "module": "TM", "location": "page", "number": n}
                for n in first_search_pages(first)
            ],
        }
    ]
    assert first["sources_line_found"] is True
    assert detail["questions"][1]["says_not_covered"] is True

    with (results_dir / "history.csv").open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 1
    assert rows[0]["note"] == "first try"
    assert rows[0]["chat_model"] == "fake-chat"
    assert rows[0]["embedding_model"] == "fake-embeddings"
    assert float(rows[0]["accuracy"]) == 4.0
    assert float(rows[0]["not_covered_rate"]) == 1.0
    # One of the three behaviour checks fails on purpose.
    # (history.csv keeps four decimal places)
    assert float(rows[0]["behaviour_pass_rate"]) == pytest.approx(2 / 3, abs=1e-4)

    for heading in ("OVERALL", "BY CATEGORY", "BY MODULE", "BEHAVIOUR"):
        assert heading in report
    assert "first run" in report
    assert "definition" in report
    assert "TM" in report
    assert "FAIL   Explain depreciation" in report
    assert "searched=True, expected False" in report
    assert "AGENT SEARCHES" in report
    assert "4 answers searched the notes, 4 searches in all (1.00 each)" in report
    assert "4 of 4 ended with a sources line" in report


def test_the_report_shows_the_change_since_the_last_run(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    save_run(run_evaluation(tmp_path / "one", scripted_model()), results_dir)
    second = run_evaluation(tmp_path / "two", scripted_model())

    report = format_report(second, last_run(results_dir))

    # Same fake answers, so every score is unchanged.
    assert "Judge: accuracy (1-5)" in report
    assert "+0.00" in report
    assert "first run" not in report


def test_results_never_contain_slide_text(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results = run_evaluation(tmp_path, scripted_model())

    detail_file = save_run(results, results_dir)
    report = format_report(results, None)

    saved = detail_file.read_text(encoding="utf-8") + (
        (results_dir / "history.csv").read_text(encoding="utf-8")
    )
    for text in SLIDE_TEXTS:
        assert text not in saved
        assert text not in report
    # Which slides were found is kept, just not what they said.
    assert '"keywords_matched"' in saved


def test_a_failed_question_is_reported_and_left_out_of_the_scores(
    tmp_path: Path,
) -> None:
    results = run_evaluation(tmp_path, scripted_model(judge_error=lost_connection()))

    assert [q.error is not None for q in results.questions] == [True, True]
    assert "Couldn't reach OpenAI" in str(results.questions[0].error)
    assert results.headline.accuracy is None
    assert results.headline.mrr is None  # measured, but dropped with the failure
    report = format_report(results, None)
    assert "2 question(s) failed" in report


def test_a_module_missing_from_settings_is_refused(tmp_path: Path) -> None:
    stray = QUESTIONS[0].model_copy(update={"module": "Some Other Module"})
    store = NotesStore(tmp_path / "chroma", FakeEmbeddings(), "fake")
    model = scripted_model()

    with pytest.raises(ValueError, match="Some Other Module"):
        asyncio.run(
            evaluate(
                settings=TEST_SETTINGS.model_copy(update={"modules": [MODULE]}),
                store=store,
                agent=Agent(model, NotesSearch(store, [MODULE], 8)),
                judge_model=model,
                chat_model_name="x",
                embedding_model_name="y",
                questions=[stray],
                behaviour_cases=[],
                note="",
                concurrency=1,
            )
        )


def test_the_judge_rejects_scores_outside_one_to_five() -> None:
    model = FakeChatModel(
        responder=lambda messages: (
            '{"accuracy": 9, "completeness": 3, "relevance": 5, "explanation": "x"}'
        )
    )

    with pytest.raises(ValueError, match="accuracy"):
        asyncio.run(judge_answer(model, "Q?", "Reference", "Answer"))


def first_search_pages(question: dict) -> list[int]:
    """The page numbers the first search returned (the fake embeddings decide
    the order), so the test checks the shape of the record without depending on it."""
    return [r["number"] for r in question["searches"][0]["results"]]


def test_a_missing_sources_line_is_flagged_and_reported(tmp_path: Path) -> None:
    def responder(messages: list[BaseMessage]) -> str | FakeReply:
        if isinstance(messages[-1], ToolMessage):
            return "An answer that forgot its sources line."
        return FakeReply(tool_call={"name": "search_notes", "args": {"query": "q"}})

    store = NotesStore(tmp_path / "chroma", FakeEmbeddings(), "fake")
    agent = Agent(FakeChatModel(responder=responder), NotesSearch(store, [MODULE], 8))

    run = asyncio.run(ask_agent(agent, "A question"))

    assert run.searched
    assert run.sources_line_found is False
    assert [s.query for s in run.searches] == ["q"]
