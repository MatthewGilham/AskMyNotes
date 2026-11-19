"""Regression coverage for leaked citations, persistence and model context."""

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from helpers import BIG_BUDGET, build_app, send, usage_ledger, wait_until_updated

from askmynotes.agent.agent import load_instructions
from askmynotes.chats import repository
from askmynotes.chats.citation_markers import CITATION_OPEN, without_citation_markers
from askmynotes.chats.history import ModelHistory, context_size
from askmynotes.chats.models import QuotedContext, Source, WebSource
from askmynotes.database import Database
from askmynotes.fake_model import FakeChatModel, FakeReply, text_of

MARKER = "\ue200cite\ue202turn0search0\ue201"
CASES = json.loads(
    (Path(__file__).parent / "fixtures/citation_markers.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize(("raw", "clean"), CASES)
def test_only_reserved_citations_are_removed(raw: str, clean: str) -> None:
    assert without_citation_markers(raw) == clean
    assert without_citation_markers(clean) == clean


def test_every_partial_opening_is_hidden_but_unrelated_text_is_released() -> None:
    for length in range(1, len(CITATION_OPEN)):
        partial = CITATION_OPEN[:length]
        assert without_citation_markers("A" + partial) == "A"
        assert without_citation_markers("A" + partial + "ordinary") == (
            "A" + partial + "ordinary"
        )


@pytest.mark.parametrize("fails", [False, True])
def test_final_event_and_saved_reply_are_clean_after_success_or_failure(
    tmp_path: Path, fails: bool
) -> None:
    model = FakeChatModel(
        responder=lambda _: FakeReply(
            "Before " + MARKER + "after " + CITATION_OPEN + "unfinished",
            fails_after_text=fails,
        )
    )
    with TestClient(build_app(tmp_path, model)) as client:
        wait_until_updated(client)
        events = send(client, "Hello")
        final = events[-1]
        assert final["type"] == ("error" if fails else "done")
        # The existing completed-answer path trims trailing whitespace; partial
        # failed answers preserve it. Citation cleanup preserves that behaviour.
        expected = "Before after " if fails else "Before after"
        assert final["message"]["content"] == expected
        saved = client.get(f"/api/chats/{events[0]['chat']['id']}").json()
        assert saved["messages"][-1]["content"] == expected
        assert saved["messages"][-1]["webSources"] is None
    with sqlite3.connect(tmp_path / "app.db") as connection:
        assert (
            MARKER
            not in connection.execute(
                "SELECT content FROM messages WHERE role='assistant'"
            ).fetchone()[0]
        )


def test_old_answers_clean_on_read_without_rewriting_rows_or_user_quotes(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "app.db")
    repository.create_tables(database)
    source = Source(file_name="Made up.pdf", module="TEST", location="page", number=1)
    page = WebSource(title="Page", site="example.test", url="https://example.test")
    raw = f"Before {MARKER}after [page](https://example.test)"
    with database.connection() as connection:
        chat = repository.create_chat(connection, "Old chat")
        answer_id = repository.add_message(
            connection,
            chat.id,
            "assistant",
            raw,
            sources=[source],
            web_sources=[page],
            web_searches=["made up query"],
        )
        quote = QuotedContext(source_message_id=answer_id, excerpt=raw)
        repository.add_message(
            connection, chat.id, "user", MARKER, quoted_context=quote
        )
        repository.save_summary(connection, chat.id, f"Summary {MARKER}text", 0)
    with database.connection() as connection:
        messages = repository.get_chat(connection, chat.id).messages
        assert messages[0].content == "Before after [page](https://example.test)"
        assert messages[0].sources == [source]
        assert messages[0].web_sources == [page]
        assert messages[0].web_searches == ["made up query"]
        assert messages[1].content == MARKER
        assert messages[1].quoted_context == quote
        assert (
            connection.execute(
                "SELECT content FROM messages WHERE id=?", (answer_id,)
            ).fetchone()[0]
            == raw
        )
    history = ModelHistory(
        database, FakeChatModel(), tmp_path, BIG_BUDGET, usage_ledger(database)
    )
    sent = asyncio.run(history.for_model(chat.id))
    assert text_of(sent[0]).endswith("Summary text")
    assert text_of(sent[1]) == messages[0].content
    assert MARKER in text_of(sent[2])  # The student's text and quote are preserved.
    assert history.context_usage(chat.id).tokens == context_size(
        messages, "Summary text"
    )
    with database.connection() as connection:
        assert MARKER in repository.get_summary(connection, chat.id)[0]


def test_new_summaries_and_their_assistant_input_are_clean(tmp_path: Path) -> None:
    model = FakeChatModel(responder=lambda _: f"Clean {MARKER}summary")
    database = Database(tmp_path / "app.db")
    repository.create_tables(database)
    with database.connection() as connection:
        chat = repository.create_chat(connection, "Long chat")
        for _ in range(6):
            repository.add_message(connection, chat.id, "assistant", "x" * 150 + MARKER)
    history = ModelHistory(database, model, tmp_path, 100, usage_ledger(database))
    asyncio.run(history.for_model(chat.id))
    assert all(MARKER not in text_of(m) for call in model.received for m in call)
    with database.connection() as connection:
        assert repository.get_summary(connection, chat.id)[0] == "Clean summary"


def test_instructions_require_supported_citations() -> None:
    instructions = load_instructions([])
    assert "Never write internal citation tokens" in instructions
    assert "Sources used:" in instructions
    assert "inside `:::web`" in instructions


def test_stopping_inside_a_marker_saves_clean_text(tmp_path: Path) -> None:
    from helpers import TEST_CONFIG, document_reader
    from test_web_search import empty_store

    from askmynotes.agent.agent import Agent
    from askmynotes.chats.conversation import Conversation
    from askmynotes.chats.models import SendRequest
    from askmynotes.notes.search import NotesSearch

    database = Database(tmp_path / "app.db")
    repository.create_tables(database)
    ledger = usage_ledger(database)
    model = FakeChatModel(
        responder=lambda _: FakeReply(
            "Before " + CITATION_OPEN + "partial", delay_seconds=0.01
        )
    )
    conversation = Conversation(
        database,
        Agent(model, NotesSearch(empty_store(tmp_path), [], 8)),
        model,
        tmp_path / "uploads",
        TEST_CONFIG,
        ModelHistory(database, model, tmp_path, BIG_BUDGET, ledger),
        document_reader(tmp_path),
        ledger,
    )
    prepared = conversation.start_message(SendRequest(text="Hello"))

    async def stop() -> None:
        stream = conversation.stream(prepared)
        async for event in stream:
            if event.type == "token" and CITATION_OPEN in event.text:
                break
        await stream.aclose()

    asyncio.run(stop())
    with database.connection() as connection:
        saved = repository.get_chat(connection, prepared.chat_id).messages[-1]
        assert saved.status == "stopped"
        assert saved.content == "Before "
