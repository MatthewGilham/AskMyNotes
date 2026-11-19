"""Tests for the calculator: the numbers (checked against values worked out by
hand), what it refuses, and how a calculation is saved with an answer.

No model is called, so everything here is free.
"""

import asyncio
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from helpers import build_app, send, wait_until_updated
from langchain_core.messages import HumanMessage

from askmynotes.agent.agent import Agent, CalculationStarted
from askmynotes.calculator.evaluate import (
    MAX_EXPRESSION_CHARACTERS,
    CalculationError,
    calculate,
    solve_equation,
)
from askmynotes.calculator.latex import to_latex
from askmynotes.calculator.tools import ToolRuns, calculator_tools
from askmynotes.chats import repository
from askmynotes.database import Database
from askmynotes.fake_model import FakeChatModel, FakeEmbeddings
from askmynotes.notes.search import FoundNotes, NotesSearch
from askmynotes.notes.store import NotesStore


def number(expression: str) -> float:
    return float(calculate(expression).value)


# The numbers


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("1 + 2 * 3", 7),
        ("(1 + 2) * 3", 9),
        ("2^10", 1024),
        # `^` is a power, and binds tighter than + and *.
        ("1 + 2^3 * 2", 17),
        ("2^3^2", 512),
        ("-3^2", -9),
        ("100 * 0.05", 5),
        ("sqrt(144)", 12),
        ("abs(-7.5)", 7.5),
        ("min(4, 2, 9)", 2),
        ("max(4, 2, 9)", 9),
        ("sum([1, 2, 3, 4])", 10),
        ("round(3.14159, 2)", 3.14),
        ("round(2.5)", 3),
        ("log(1000)", 3),
        ("ln(e)", 1),
        ("exp(0)", 1),
        ("1000 * (1 + 0.05)^2", 1102.5),
    ],
)
def test_arithmetic(expression: str, expected: float) -> None:
    assert number(expression) == pytest.approx(expected)


def test_a_fraction_is_kept_exact_and_a_decimal_is_shown() -> None:
    result = calculate("1/3 + 1/6")

    assert result.text == "0.5 (exact 1/2)"
    # A tenth is a tenth, not the nearest binary fraction.
    assert calculate("0.1 * 3").text == "0.3 (exact 3/10)"
    assert calculate("0.1 + 0.2").text == "0.3 (exact 3/10)"


def test_a_whole_number_result_is_just_the_number() -> None:
    assert calculate("12 * 12").text == "144"


def test_a_very_long_exact_fraction_is_left_out_of_the_text() -> None:
    result = calculate("pmt(0.005, 360, 200000)")

    assert "exact" not in result.text
    assert result.text.startswith("1199.1010503")


def test_npv_does_not_discount_the_first_cash_flow() -> None:
    # -100 + 60/1.1 + 60/1.21 = 4.1322314...
    assert number("npv(0.1, [-100, 60, 60])") == pytest.approx(4.132231405)
    assert calculate("npv(0.1, [-100, 60, 60])").text.endswith("(exact 500/121)")


def test_irr() -> None:
    assert number("irr([-100, 110])") == pytest.approx(0.1)
    # -1000 + 300/(1+r) + 400/(1+r)^2 + 500/(1+r)^3 = 0 at r = 8.896%
    assert number("irr([-1000, 300, 400, 500])") == pytest.approx(0.08896339, abs=1e-7)


def test_a_set_of_cash_flows_with_no_irr_is_refused() -> None:
    with pytest.raises(CalculationError, match="no internal rate"):
        calculate("irr([100, 100])")


def test_present_value_future_value_and_payment() -> None:
    # Ten end-of-year payments of 100 at 5%.
    assert number("pv(0.05, 10, 100)") == pytest.approx(772.1734929)
    assert number("fv(0.05, 10, 100)") == pytest.approx(1257.789254)
    # A 200,000 loan over 360 months at 0.5% a month.
    assert number("pmt(0.005, 360, 200000)") == pytest.approx(1199.101050)
    # With a lump sum as well, and at a rate of zero.
    assert number("pv(0.1, 2, 0, 121)") == pytest.approx(100)
    assert number("pv(0, 4, 25)") == 100
    assert number("pmt(0, 4, 100)") == 25


def test_sample_statistics() -> None:
    # 2, 4, 4, 4, 5, 5, 7, 9: mean 5, sum of squares 32, so a sample variance
    # of 32 / 7.
    assert number("mean([2, 4, 4, 4, 5, 5, 7, 9])") == 5
    assert number("variance([2, 4, 4, 4, 5, 5, 7, 9])") == pytest.approx(32 / 7)
    assert number("stdev([2, 4, 4, 4, 5, 5, 7, 9])") == pytest.approx(2.13808994)


def test_an_equation_is_solved_for_a_rate() -> None:
    # A two-year bond: 1000 = 80/(1+r) + 1080/(1+r)^2 has r = 0.08 (and a
    # negative root that makes no financial sense).
    results = solve_equation("1000 = 80/(1+r) + 1080/(1+r)^2", "r")

    assert [float(r.value) for r in results] == pytest.approx([-2, 0.08])
    assert results[1].text == "0.08 (exact 2/25)"


def test_an_equation_with_an_irrational_solution() -> None:
    results = solve_equation("x^2 = 2", "x")

    assert [float(r.value) for r in results] == pytest.approx([-(2**0.5), 2**0.5])


def test_an_equation_with_no_real_solution_is_refused() -> None:
    with pytest.raises(CalculationError, match="no real solutions"):
        solve_equation("x^2 = -1", "x")


def test_an_equation_without_its_unknown_is_refused() -> None:
    with pytest.raises(CalculationError, match="doesn't contain"):
        solve_equation("1 = 1 + 0*2", "x")


# What it refuses


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('echo hi')",
        "open('x')",
        "(1).real",
        "().__class__",
        "[x for x in [1]]",
        "lambda: 1",
        "'abc'",
        "True",
        "1 if 1 else 2",
        "sum([1, 2], 3, start=4)",
        "x + 1",
        "foo(1)",
        "print(1)",
        "eval('1')",
        "1; 2",
        "1 +",
        "",
        "   ",
        "1 << 4",
        "5 % 3",
        "5 // 2",
        "2 ** 1001",
        "2 ^ 100000",
        "9 ^ 9 ^ 9",
    ],
)
def test_anything_else_is_refused(expression: str) -> None:
    with pytest.raises(CalculationError):
        calculate(expression)


def test_nothing_is_run_when_an_expression_is_refused(tmp_path: Path) -> None:
    marker = tmp_path / "ran"
    expression = f"__import__('pathlib').Path({str(marker)!r}).write_text('x')"

    with pytest.raises(CalculationError):
        calculate(expression)

    assert not marker.exists()


def test_an_over_long_expression_is_refused() -> None:
    with pytest.raises(CalculationError, match="limited to"):
        calculate("1+" * MAX_EXPRESSION_CHARACTERS + "1")


def test_an_expression_with_too_many_parts_is_refused() -> None:
    with pytest.raises(CalculationError, match="too long"):
        calculate("+".join(["1"] * 200))


def test_repeated_powers_that_grow_too_large_are_refused() -> None:
    with pytest.raises(CalculationError, match="too large"):
        calculate("((9^1000)^1000)^1000")


def test_the_wrong_number_of_arguments_is_refused() -> None:
    with pytest.raises(CalculationError, match="argument"):
        calculate("sqrt(1, 2)")


def test_division_by_zero_and_complex_results_are_refused() -> None:
    with pytest.raises(CalculationError, match="zero"):
        calculate("1 / 0")
    with pytest.raises(CalculationError, match="real number"):
        calculate("sqrt(-4)")


def test_a_list_must_be_used_inside_a_function() -> None:
    with pytest.raises(CalculationError):
        calculate("[1, 2, 3]")
    with pytest.raises(CalculationError, match="list of numbers"):
        calculate("sum(5)")


def test_only_the_simple_functions_can_be_used_in_an_equation() -> None:
    with pytest.raises(CalculationError, match="can't be used inside an equation"):
        solve_equation("npv(r, [1, 2]) = 3", "r")


# Written as maths


def test_an_expression_is_written_as_latex() -> None:
    assert to_latex("1000 * (1 + 0.05)^2") == (r"1000 \times \left(1 + 0.05\right)^{2}")
    assert to_latex("80/(1+r)") == r"\frac{80}{1 + r}"
    assert to_latex("sqrt(2) - (3 - 1)") == r"\sqrt{2} - \left(3 - 1\right)"
    assert to_latex("npv(0.1, [-100, 60])") == (
        r"\operatorname{npv}\left(0.1, \left[-100, 60\right]\right)"
    )
    assert to_latex("1100 = 1000 * (1 + r)") == (
        r"1100 = 1000 \times \left(1 + r\right)"
    )


# The tools the agent uses


def test_a_calculation_is_recorded_and_a_refused_one_goes_back_to_the_model() -> None:
    runs = ToolRuns()
    calculate_tool, solve_tool = calculator_tools(runs)

    ok = calculate_tool.invoke({"expression": "1000 * (1 + 0.05)^2"})
    refused = calculate_tool.invoke({"expression": "1 / 0"})
    solved = solve_tool.invoke({"equation": "1100 = 1000 * (1 + r)", "unknown": "r"})

    assert ok == "= 1102.5 (exact 2205/2)"
    assert refused == "Error: Division by zero."
    assert solved == "r = 0.1 (exact 1/10)"
    assert [(r.tool, r.ok) for r in runs.runs] == [
        ("calculate", True),
        ("calculate", False),
        ("solve_equation", True),
    ]
    assert runs.runs[0].input_latex == r"1000 \times \left(1 + 0.05\right)^{2}"
    assert runs.runs[0].result_latex == r"\frac{2205}{2} \approx 1102.5"
    assert runs.runs[1].result == "Division by zero."
    assert runs.runs[2].result_latex == r"r = \frac{1}{10} \approx 0.1"


def calculator_chat(tmp_path: Path, text: str) -> tuple[TestClient, list[dict]]:
    client = TestClient(build_app(tmp_path / "data"))
    client.__enter__()
    wait_until_updated(client)
    return client, send(client, text)


def test_a_reply_that_calculated_saves_its_working_and_reopens_with_it(
    tmp_path: Path,
) -> None:
    client, events = calculator_chat(tmp_path, "calc please")
    with client:
        chat_id = events[0]["chat"]["id"]
        saved = events[-1]["message"]["toolRuns"]
        reopened = client.get(f"/api/chats/{chat_id}").json()["messages"][-1]

    assert [(r["tool"], r["ok"]) for r in saved] == [
        ("calculate", True),
        ("solve_equation", True),
    ]
    assert saved[0]["result"] == "1102.5 (exact 2205/2)"
    assert reopened["toolRuns"] == saved
    assert [e["kind"] for e in events if e["type"] == "searching"] == [
        "calculator",
        "calculator",
    ]


def test_a_refused_calculation_is_saved_in_the_working_and_the_reply_carries_on(
    tmp_path: Path,
) -> None:
    client, events = calculator_chat(tmp_path, "calc wrong")
    with client:
        saved = events[-1]["message"]["toolRuns"]

    assert [r["ok"] for r in saved] == [False, True, True]
    assert events[-1]["type"] == "done"
    assert "1102.5" in events[-1]["message"]["content"]


def test_a_reply_without_a_calculation_has_no_working(tmp_path: Path) -> None:
    client, events = calculator_chat(tmp_path, "hello there")
    with client:
        assert events[-1]["message"]["toolRuns"] is None


def test_regenerating_removes_the_old_working_and_the_new_reply_has_its_own(
    tmp_path: Path,
) -> None:
    client, events = calculator_chat(tmp_path, "calc please")
    with client:
        chat_id = events[0]["chat"]["id"]
        client.post(f"/api/chats/{chat_id}/regenerate")
        messages = client.get(f"/api/chats/{chat_id}").json()["messages"]

    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert len(messages[-1]["toolRuns"]) == 2


def test_editing_the_question_removes_the_old_working(tmp_path: Path) -> None:
    client, events = calculator_chat(tmp_path, "calc please")
    with client:
        chat_id = events[0]["chat"]["id"]
        question = events[0]["userMessage"]
        edited = client.post(
            f"/api/chats/{chat_id}/messages/{question['id']}/edit",
            json={
                "text": "Just say hello",
                "expectedLatestMessageId": question["id"],
                "expectedOriginalText": question["content"],
            },
        )
        messages = client.get(f"/api/chats/{chat_id}").json()["messages"]

    assert edited.status_code == 200, edited.text
    assert messages[-1]["toolRuns"] is None


def test_an_older_database_gets_the_tool_runs_column(tmp_path: Path) -> None:
    path = tmp_path / "app.db"
    old = sqlite3.connect(path)
    old.executescript(
        """
        CREATE TABLE chats (id TEXT PRIMARY KEY, title TEXT NOT NULL,
            pinned INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
            last_used_at TEXT NOT NULL, summary TEXT,
            summarised_up_to INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'complete', error TEXT, sources TEXT,
            created_at TEXT NOT NULL, quoted_context TEXT, web_sources TEXT);
        INSERT INTO chats
            VALUES ('c', 'Old chat', 0, '2026-01-01', '2026-01-01', NULL, 0);
        INSERT INTO messages (chat_id, role, content, created_at)
            VALUES ('c', 'assistant', 'An old answer', '2026-01-01');
        """
    )
    old.commit()
    old.close()
    database = Database(path)

    repository.create_tables(database)

    with database.connection() as connection:
        chat = repository.get_chat(connection, "c")
    assert chat.messages[0].content == "An old answer"
    assert chat.messages[0].tool_runs is None


def test_the_agent_announces_each_calculation(tmp_path: Path) -> None:
    model = FakeChatModel()
    store = NotesStore(tmp_path / "chroma", FakeEmbeddings(), "fake")
    agent = Agent(model, NotesSearch(store, [], 8))
    runs = ToolRuns()

    async def run() -> list:
        return [
            piece
            async for piece in agent.stream_reply(
                [HumanMessage(content="calc please")],
                FoundNotes(),
                runs=runs,
            )
        ]

    pieces = asyncio.run(run())

    assert sum(isinstance(p, CalculationStarted) for p in pieces) == 2
    assert len(runs.runs) == 2


def test_the_instructions_describe_the_calculator_and_who_owns_the_formula(
    tmp_path: Path,
) -> None:
    model = FakeChatModel(responder=lambda m: "Hello")
    with TestClient(build_app(tmp_path / "data", model)) as client:
        wait_until_updated(client)
        send(client, "Hi")

    answer = [m for m in model.received if "short title" not in str(m[0].content)][0]
    text = " ".join(str(answer[0].content).split())
    assert "## Calculations" in text
    assert "is not outside knowledge" in text
    assert "still outside knowledge" in text
