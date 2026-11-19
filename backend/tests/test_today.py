"""Tests for the agent knowing today's date: it is put in the instructions for
each reply, from a clock the tests can fix."""

import asyncio
from datetime import date
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from askmynotes.agent.agent import Agent
from askmynotes.fake_model import FakeChatModel, FakeEmbeddings, text_of
from askmynotes.notes.search import FoundNotes, NotesSearch
from askmynotes.notes.store import NotesStore
from askmynotes.settings import Module


def ask(agent: Agent) -> None:
    """Run one reply to completion."""

    async def run() -> None:
        async for _piece in agent.stream_reply(
            [HumanMessage(content="Hi")], FoundNotes()
        ):
            pass

    asyncio.run(run())


def system_prompt(model: FakeChatModel, reply_number: int = 0) -> str:
    """The instructions the model was given for one reply."""
    instructions = model.received[reply_number][0]
    assert isinstance(instructions, SystemMessage)
    return text_of(instructions)


def make_agent(
    tmp_path: Path, model: FakeChatModel, clock, modules: list[Module] | None = None
) -> Agent:
    store = NotesStore(tmp_path / "chroma", FakeEmbeddings(), "fake")
    return Agent(model, NotesSearch(store, modules or [], 8), clock)


def test_the_instructions_give_todays_date_and_weekday(tmp_path: Path) -> None:
    model = FakeChatModel(responder=lambda messages: "Hello.")
    agent = make_agent(tmp_path, model, lambda: date(2026, 10, 29))

    ask(agent)

    assert "Today is Thursday 29 October 2026." in system_prompt(model)
    assert "{today}" not in system_prompt(model)


def test_a_day_of_the_month_below_ten_has_no_leading_zero(tmp_path: Path) -> None:
    model = FakeChatModel(responder=lambda messages: "Hello.")
    agent = make_agent(tmp_path, model, lambda: date(2027, 1, 5))

    ask(agent)

    assert "Today is Tuesday 5 January 2027." in system_prompt(model)


def test_a_reply_started_after_midnight_uses_the_new_date(tmp_path: Path) -> None:
    model = FakeChatModel(responder=lambda messages: "Hello.")
    today = [date(2026, 10, 29)]
    agent = make_agent(tmp_path, model, lambda: today[0])

    ask(agent)
    today[0] = date(2026, 10, 30)
    ask(agent)

    assert "Today is Thursday 29 October 2026." in system_prompt(model, 0)
    assert "Today is Friday 30 October 2026." in system_prompt(model, 1)


def test_the_modules_are_still_listed_with_the_date(tmp_path: Path) -> None:
    model = FakeChatModel(responder=lambda messages: "Hello.")
    module = Module(name="Testing Module", short_name="TM", folder=tmp_path)
    agent = make_agent(tmp_path, model, lambda: date(2026, 10, 29), [module])

    ask(agent)

    assert "- Testing Module (TM)" in system_prompt(model)
    assert "{modules}" not in system_prompt(model)
