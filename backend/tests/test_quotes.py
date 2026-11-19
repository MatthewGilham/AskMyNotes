"""Quote snapshots survive validation, restarts and long-chat summaries."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from helpers import build_app, lost_connection, read_events, send
from langchain_core.messages import HumanMessage

from askmynotes.chats import repository
from askmynotes.chats.history import conversational_text, estimate_tokens
from askmynotes.chats.models import Source
from askmynotes.database import Database
from askmynotes.fake_model import FakeChatModel, text_of


def seed(
    database: Database, status: str = "complete", content: str = "Original answer"
) -> tuple[str, int]:
    """Create an eligible source without a model call."""
    with database.connection() as connection:
        chat = repository.create_chat(connection, "Quote testing")
        repository.add_message(connection, chat.id, "user", "Original question")
        source = repository.add_message(
            connection, chat.id, "assistant", content, status=status
        )
    return chat.id, source


def quoted_send(
    client: TestClient,
    chat_id: str | None,
    source: int,
    excerpt: str = "A precise passage",
    text: str = "Why?",
):
    """Send a quote through the public validation boundary."""
    return client.post(
        "/api/chats/send",
        json={
            "chatId": chat_id,
            "text": text,
            "quotedContext": {"sourceMessageId": source, "excerpt": excerpt},
        },
    )


def test_legacy_database_upgrades_twice_without_losing_any_chat_data(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "app.db")
    database.create_schema(repository.SCHEMA_FILE)
    # The schema file is the pre-quote schema, so insert exactly what an old app saved.
    with database.connection() as connection:
        chat = repository.create_chat(connection, "Legacy")
        cursor = connection.execute(
            "INSERT INTO messages(chat_id, role, content, sources, created_at) "
            "VALUES (?, 'assistant', 'searchable legacy', ?, ?)",
            (
                chat.id,
                json.dumps(
                    [
                        {
                            "file_name": "made-up.pdf",
                            "module": "TEST",
                            "location": "page",
                            "number": 1,
                        }
                    ]
                ),
                chat.created_at.isoformat(),
            ),
        )
        message_id = cursor.lastrowid
        repository.add_images(connection, message_id, [f"{chat.id}/image.png"])
        repository.save_summary(connection, chat.id, "Saved summary", message_id)
        before = [tuple(row) for row in connection.execute("SELECT * FROM chat_search")]
    repository.create_tables(database)
    repository.create_tables(database)
    with database.connection() as connection:
        saved = repository.get_chat(connection, chat.id).messages[0]
        assert saved.quoted_context is None
        assert saved.content == "searchable legacy"
        assert saved.images == [f"/api/uploads/{chat.id}/image.png"]
        assert saved.sources == [
            Source(file_name="made-up.pdf", module="TEST", location="page", number=1)
        ]
        assert repository.get_summary(connection, chat.id) == (
            "Saved summary",
            message_id,
        )
        assert [
            tuple(row) for row in connection.execute("SELECT * FROM chat_search")
        ] == before


@pytest.mark.parametrize(
    "invalid",
    [
        "cross-chat",
        "missing",
        "user",
        "failed",
        "empty-answer",
        "empty-excerpt",
        "oversized",
        "new-chat",
        "quote-only",
    ],
)
def test_invalid_quotes_save_nothing_and_make_no_model_call(
    tmp_path: Path, invalid: str
) -> None:
    model = FakeChatModel()
    client = TestClient(build_app(tmp_path, model))
    database = Database(tmp_path / "app.db")
    chat_id, source = seed(
        database,
        status="error" if invalid == "failed" else "complete",
        content="" if invalid == "empty-answer" else "Original answer",
    )
    if invalid == "cross-chat":
        _, source = seed(database)
    elif invalid == "missing":
        source = 99999
    elif invalid == "user":
        source -= 1
    with database.connection() as connection:
        before = connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    response = quoted_send(
        client,
        None if invalid == "new-chat" else chat_id,
        source,
        excerpt=" "
        if invalid == "empty-excerpt"
        else "x" * 8001
        if invalid == "oversized"
        else "A passage",
        text="" if invalid == "quote-only" else "Why?",
    )
    assert response.status_code == 422
    if invalid == "oversized":
        assert "select a shorter passage" in response.text
    assert not model.received
    with database.connection() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == before
        )
        assert len(repository.list_chats(connection)) == (
            2 if invalid == "cross-chat" else 1
        )


def test_quote_survives_restart_and_source_removal_then_deletes_with_chat(
    tmp_path: Path,
) -> None:
    client = TestClient(build_app(tmp_path))
    database = Database(tmp_path / "app.db")
    chat_id, source = seed(database, status="stopped")
    excerpt = "A snapshot with \\(\\frac{1}{2}\\)"
    response = quoted_send(client, chat_id, source, excerpt)
    assert response.status_code == 200
    question = read_events(response.text)[0]["userMessage"]
    expected = {"sourceMessageId": source, "excerpt": excerpt}
    assert question["quotedContext"] == expected
    with database.connection() as connection:
        connection.execute("DELETE FROM messages WHERE id = ?", (source,))
    restarted = TestClient(build_app(tmp_path))
    saved = restarted.get(f"/api/chats/{chat_id}").json()["messages"]
    assert saved[-2]["quotedContext"] == expected
    assert saved[-2]["content"] == "Why?"
    assert restarted.delete(f"/api/chats/{chat_id}").status_code == 204
    with database.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0


def test_summarised_source_still_supplies_exact_quote_and_counts_it_in_summaries(
    tmp_path: Path,
) -> None:
    model = FakeChatModel(
        responder=lambda messages: (
            "A short summary"
            if "running summary" in text_of(messages[0])
            else "An answer"
        )
    )
    client = TestClient(build_app(tmp_path, model, context_budget_tokens=100))
    database = Database(tmp_path / "app.db")
    chat_id, source = seed(database)
    with database.connection() as connection:
        repository.save_summary(
            connection, chat_id, "Original answer already summarised", source
        )
    excerpt = "Exact excerpt: \\(\\frac{1}{2}\\)\n" + "quoted context " * 60
    assert quoted_send(client, chat_id, source, excerpt).status_code == 200
    reply_call = model.received[-1]
    assert isinstance(reply_call[-1], HumanMessage)
    assert excerpt in text_of(reply_call[-1])
    assert "Question:\nWhy?" in text_of(reply_call[-1])
    with database.connection() as connection:
        question = repository.get_chat(connection, chat_id).messages[-2]
    assert estimate_tokens(question) >= len(excerpt) // 4
    assert conversational_text(question) == text_of(reply_call[-1])
    send(client, "Next question " + "x" * 300, chat_id)
    summaries = [
        call for call in model.received if "running summary" in text_of(call[0])
    ]
    assert any(excerpt in text_of(call[-1]) for call in summaries)


def test_failure_retry_and_regenerate_reconstruct_the_saved_quote(
    tmp_path: Path,
) -> None:
    fail = True

    def respond(messages):
        if fail:
            raise lost_connection()
        return "Recovered answer"

    model = FakeChatModel(responder=respond)
    client = TestClient(build_app(tmp_path, model))
    chat_id, source = seed(Database(tmp_path / "app.db"))
    assert read_events(quoted_send(client, chat_id, source).text)[-1]["type"] == "error"
    fail = False
    for _ in range(2):
        response = client.post(f"/api/chats/{chat_id}/regenerate")
        assert read_events(response.text)[-1]["type"] == "done"
        assert "A precise passage" in text_of(model.received[-1][-1])
        saved = client.get(f"/api/chats/{chat_id}").json()["messages"]
        assert len(saved) == 4
        assert saved[-2]["quotedContext"]["sourceMessageId"] == source


def test_quote_does_not_add_fts_matches_or_inherit_sources(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path))
    database = Database(tmp_path / "app.db")
    chat_id, source = seed(database)
    with database.connection() as connection:
        connection.execute(
            "UPDATE messages SET sources = ? WHERE id = ?",
            (
                json.dumps(
                    [
                        {
                            "file_name": "old.pdf",
                            "module": "OLD",
                            "location": "page",
                            "number": 2,
                        }
                    ]
                ),
                source,
            ),
        )
    # A fixed responder avoids echoing the quote into an answer, which *is* searchable.
    client = TestClient(
        build_app(tmp_path, FakeChatModel(responder=lambda messages: "New answer"))
    )
    response = quoted_send(client, chat_id, source, "uniquesnapshotword")
    events = read_events(response.text)
    assert events[-1]["message"]["sources"] is None
    assert client.get("/api/chats/search?q=uniquesnapshotword").json() == []


def test_quoted_follow_up_still_searches_and_saves_its_own_sources(
    tmp_path: Path,
) -> None:
    """The quote is context; only this turn's actual tool results become sources."""
    from helpers import make_pdf, wait_until_updated
    from langchain_core.messages import ToolMessage

    from askmynotes.fake_model import FakeReply
    from askmynotes.settings import Module

    notes = tmp_path / "notes"
    notes.mkdir()
    make_pdf(notes / "new.pdf", ["Depreciation spreads asset cost over useful life."])
    data = tmp_path / "data"

    def respond(messages):
        if isinstance(messages[-1], ToolMessage):
            return (
                "Depreciation spreads cost.\n\n:::beyond\n"
                "A general example.\n:::\nSources used: S1"
            )
        return FakeReply(
            tool_call={"name": "search_notes", "args": {"query": "depreciation"}}
        )

    model = FakeChatModel(responder=respond)
    with TestClient(
        build_app(
            data, model, modules=[Module(name="Test", short_name="TM", folder=notes)]
        )
    ) as client:
        wait_until_updated(client)
        chat_id, source = seed(Database(data / "app.db"))
        events = read_events(quoted_send(client, chat_id, source).text)
        assert "searching" in [event["type"] for event in events]
        answer = events[-1]["message"]
        assert answer["sources"] == [
            {"fileName": "new.pdf", "module": "TM", "location": "page", "number": 1}
        ]
        assert ":::beyond" in answer["content"]
        assert (
            client.get(f"/api/chats/{chat_id}").json()["messages"][-1]["sources"]
            == answer["sources"]
        )
