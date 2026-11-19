"""Tests for sending messages and streaming replies, with a fake model."""

import asyncio
import contextlib
from pathlib import Path

import httpx
import openai
import pytest
from fastapi.testclient import TestClient
from helpers import (
    BIG_BUDGET,
    TEST_CONFIG,
    build_app,
    document_reader,
    lost_connection,
    send,
    usage_ledger,
)
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from askmynotes.agent.agent import Agent
from askmynotes.chats import repository
from askmynotes.chats.conversation import Conversation
from askmynotes.chats.errors import friendly_error
from askmynotes.chats.history import ModelHistory
from askmynotes.chats.models import SendRequest
from askmynotes.database import Database
from askmynotes.fake_model import FakeChatModel, FakeEmbeddings, FakeReply, text_of
from askmynotes.notes.search import NotesSearch
from askmynotes.notes.store import NotesStore


def replies(*texts: str):
    """A responder that gives each text in turn, and answers title requests."""
    remaining = list(texts)

    def responder(messages: list[BaseMessage]) -> str:
        if "short title" in text_of(messages[0]):
            return "A Fake Title"
        return remaining.pop(0)

    return responder


def failing_then(*texts: str):
    """A responder whose first reply fails, like a lost internet connection."""
    remaining: list[str | None] = [None, *texts]

    def responder(messages: list[BaseMessage]) -> str:
        if "short title" in text_of(messages[0]):
            return "A Fake Title"
        text = remaining.pop(0)
        if text is None:
            raise lost_connection()
        return text

    return responder


def chat_messages(data_dir: Path, chat_id: str):
    with Database(data_dir / "app.db").connection() as connection:
        return repository.get_chat(connection, chat_id).messages


@pytest.fixture
def conversation_parts(tmp_path: Path):
    """A Conversation wired to a fake model, plus the database and model."""

    def build(responder):
        model = FakeChatModel(responder=responder)
        database = Database(tmp_path / "app.db")
        repository.create_tables(database)
        ledger = usage_ledger(database)
        history = ModelHistory(
            database, model, tmp_path / "uploads", BIG_BUDGET, ledger
        )
        store = NotesStore(tmp_path / "chroma", FakeEmbeddings(), "fake")
        agent = Agent(model, NotesSearch(store, [], results_per_search=8))
        conversation = Conversation(
            database,
            agent,
            model,
            tmp_path / "uploads",
            TEST_CONFIG,
            history,
            document_reader(tmp_path),
            ledger,
        )
        return conversation, database, model

    return build


def test_a_reply_streams_in_pieces_and_is_saved(tmp_path: Path) -> None:
    client = TestClient(
        build_app(tmp_path, FakeChatModel(responder=replies("Hello there friend")))
    )

    events = send(client, "Hi")

    kinds = [event["type"] for event in events]
    assert kinds[0] == "start"
    assert kinds[-1] == "done"
    assert kinds.count("token") > 1
    streamed = "".join(e["text"] for e in events if e["type"] == "token")
    assert streamed == "Hello there friend"
    chat_id = events[0]["chat"]["id"]
    saved = chat_messages(tmp_path, chat_id)
    assert [(m.role, m.content, m.status) for m in saved] == [
        ("user", "Hi", "complete"),
        ("assistant", "Hello there friend", "complete"),
    ]


def test_user_message_is_saved_when_the_model_fails(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path, FakeChatModel(responder=failing_then())))

    events = send(client, "Please help")

    assert events[-1]["type"] == "error"
    assert "Couldn't reach OpenAI" in events[-1]["message"]["error"]
    saved = chat_messages(tmp_path, events[0]["chat"]["id"])
    assert [(m.role, m.content, m.status) for m in saved] == [
        ("user", "Please help", "complete"),
        ("assistant", "", "error"),
    ]


def test_retry_after_an_error_replaces_the_error(tmp_path: Path) -> None:
    client = TestClient(
        build_app(tmp_path, FakeChatModel(responder=failing_then("Second time lucky")))
    )
    chat_id = send(client, "Please help")[0]["chat"]["id"]

    events = send_regenerate(client, chat_id)

    assert events[-1]["type"] == "done"
    saved = chat_messages(tmp_path, chat_id)
    assert [(m.role, m.content, m.status) for m in saved] == [
        ("user", "Please help", "complete"),
        ("assistant", "Second time lucky", "complete"),
    ]


def test_regenerate_replaces_the_latest_reply(tmp_path: Path) -> None:
    model = FakeChatModel(responder=replies("First answer", "Better answer"))
    client = TestClient(build_app(tmp_path, model))
    chat_id = send(client, "Question")[0]["chat"]["id"]

    send_regenerate(client, chat_id)

    saved = chat_messages(tmp_path, chat_id)
    assert [(m.role, m.content) for m in saved] == [
        ("user", "Question"),
        ("assistant", "Better answer"),
    ]


def test_regenerating_a_chat_with_no_messages_is_refused(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path))
    with Database(tmp_path / "app.db").connection() as connection:
        chat = repository.create_chat(connection, "Empty")

    response = client.post(f"/api/chats/{chat.id}/regenerate")

    assert response.status_code == 409
    assert client.post("/api/chats/nope/regenerate").status_code == 404


def test_agent_is_given_the_earlier_messages(tmp_path: Path) -> None:
    model = FakeChatModel(responder=replies("It is 25p.", "Diluted is lower."))
    client = TestClient(build_app(tmp_path, model))
    chat_id = send(client, "What is basic EPS?")[0]["chat"]["id"]

    send(client, "And diluted?", chat_id)

    # The last model call that wasn't a title request is the second reply.
    answer_calls = [m for m in model.received if "short title" not in text_of(m[0])]
    sent = answer_calls[-1]
    assert [(type(m), text_of(m)) for m in sent[1:]] == [  # [0] is the instructions
        (HumanMessage, "What is basic EPS?"),
        (AIMessage, "It is 25p."),
        (HumanMessage, "And diluted?"),
    ]


def test_failed_replies_are_not_sent_to_the_model_later(tmp_path: Path) -> None:
    model = FakeChatModel(responder=failing_then("Fine now"))
    client = TestClient(build_app(tmp_path, model))
    chat_id = send(client, "First try")[0]["chat"]["id"]

    send(client, "Second try", chat_id)

    sent = [m for m in model.received if "short title" not in text_of(m[0])][-1]
    assert [type(m) for m in sent[1:]] == [HumanMessage, HumanMessage]


def test_stopping_saves_the_partial_reply_as_stopped(conversation_parts) -> None:
    conversation, database, _ = conversation_parts(
        lambda messages: FakeReply("one two three four five six", delay_seconds=0.01)
    )
    prepared = conversation.start_message(SendRequest(text="Count for me"))

    async def stop_after_three_pieces() -> None:
        stream = conversation.stream(prepared)
        tokens = 0
        async for event in stream:
            tokens += event.type == "token"
            if tokens == 3:
                break
        await stream.aclose()  # what happens when the browser disconnects

    asyncio.run(stop_after_three_pieces())

    with database.connection() as connection:
        messages = repository.get_chat(connection, prepared.chat_id).messages
    assert messages[-1].status == "stopped"
    assert messages[-1].content == "one two three "
    assert messages[0].content == "Count for me"


def test_cancelling_mid_wait_saves_the_partial_reply_as_stopped(
    conversation_parts,
) -> None:
    conversation, database, _ = conversation_parts(
        lambda messages: FakeReply("one two three four five six", delay_seconds=0.05)
    )
    prepared = conversation.start_message(SendRequest(text="Count slowly"))

    async def cancel_while_waiting() -> None:
        seen: list[str] = []

        async def consume() -> None:
            async for event in conversation.stream(prepared):
                if event.type == "token":
                    seen.append(event.text)

        task = asyncio.create_task(consume())
        while len(seen) < 2:
            await asyncio.sleep(0.01)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    asyncio.run(cancel_while_waiting())

    with database.connection() as connection:
        last = repository.get_chat(connection, prepared.chat_id).messages[-1]
    assert last.status == "stopped"
    assert last.content.startswith("one two")


def test_title_is_generated_from_the_first_message(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path, FakeChatModel(responder=replies("Hello"))))

    events = send(client, "Explain how basic EPS is calculated under IAS 33, please")

    assert events[0]["chat"]["title"] == "Explain how basic EPS is calculated unde..."
    title_events = [e for e in events if e["type"] == "title"]
    assert [e["title"] for e in title_events] == ["A Fake Title"]
    assert events.index(title_events[0]) < events.index(events[-1])
    assert (
        client.get(f"/api/chats/{events[0]['chat']['id']}").json()["title"]
        == "A Fake Title"
    )


def test_a_second_message_does_not_change_the_title(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path, FakeChatModel(responder=replies("a", "b"))))
    first = send(client, "First question")
    chat_id = first[0]["chat"]["id"]

    second = send(client, "Second question", chat_id)

    assert not [e for e in second if e["type"] == "title"]
    assert client.get(f"/api/chats/{chat_id}").json()["title"] == "A Fake Title"


def test_a_failed_title_leaves_the_placeholder_and_the_reply_works(
    tmp_path: Path,
) -> None:
    def responder(messages: list[BaseMessage]) -> str:
        if "short title" in text_of(messages[0]):
            raise lost_connection()
        return "The reply"

    client = TestClient(build_app(tmp_path, FakeChatModel(responder=responder)))

    events = send(client, "Hello world")

    assert events[-1]["type"] == "done"
    assert (
        client.get(f"/api/chats/{events[0]['chat']['id']}").json()["title"]
        == "Hello world"
    )


def test_empty_new_chat_is_not_saved(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path))

    response = client.post("/api/chats/send", json={"chatId": None, "text": "   "})

    assert response.status_code == 422
    assert client.get("/api/chats").json() == []


def test_sending_to_a_missing_chat_gives_404(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path))

    response = client.post("/api/chats/send", json={"chatId": "nope", "text": "Hi"})

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (lost_connection(), "Couldn't reach OpenAI"),
        (ValueError("secret detail"), "Something went wrong"),
    ],
)
def test_errors_are_explained_in_plain_english(error: Exception, expected: str) -> None:
    message = friendly_error(error)

    assert expected in message
    assert "secret detail" not in message


def test_authentication_errors_point_at_the_api_key() -> None:
    response = httpx.Response(
        401, request=httpx.Request("POST", "https://api.openai.com")
    )
    error = openai.AuthenticationError("bad key", response=response, body=None)

    assert ".env" in friendly_error(error)


def test_unknown_pages_get_the_app_but_unknown_api_paths_do_not(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<title>the app</title>")

    client = TestClient(build_app(tmp_path / "data", frontend_dist=dist))

    assert "the app" in client.get("/chat/abc123").text
    assert client.get("/api/nothing-here").status_code == 404


def send_regenerate(client: TestClient, chat_id: str) -> list[dict]:
    from helpers import read_events

    response = client.post(f"/api/chats/{chat_id}/regenerate")
    assert response.status_code == 200, response.text
    return read_events(response.text)
