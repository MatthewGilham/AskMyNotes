"""Tests for the API cost and context indicators: recording what each model call
used, adding it up, and the context readout.

Every price and token count is made up, and the models are fakes, so nothing is
paid for. The fake model reports 1,000 input tokens (200 of them cached) and 500
output tokens for every call, and the fake embeddings 10 tokens per text. With
the test prices (see `helpers.TEST_PRICES`) one fake call costs
(800 x 1.0 + 200 x 0.1 + 500 x 2.0) / 1,000,000 = $0.00182, and one embedded
text costs 10 x 0.5 / 1,000,000 = $0.000005.
"""

import asyncio
import base64
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from helpers import (
    BIG_BUDGET,
    TEST_CONFIG,
    TEST_PRICES,
    build_app,
    document_reader,
    make_pdf,
    read_events,
    send,
    usage_ledger,
    wait_until_updated,
)
from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI

from askmynotes.agent.agent import Agent, create_chat_model
from askmynotes.chats import repository
from askmynotes.chats.conversation import Conversation
from askmynotes.chats.history import ModelHistory, estimate_tokens
from askmynotes.chats.models import SendRequest
from askmynotes.database import Database
from askmynotes.e2e_setup import make_docx
from askmynotes.fake_model import FakeChatModel, FakeEmbeddings, FakeReply, text_of
from askmynotes.notes.embeddings import CountingOpenAIEmbeddings
from askmynotes.notes.search import FoundNotes, NotesSearch
from askmynotes.notes.store import NotesStore
from askmynotes.settings import EnvSettings, Module
from askmynotes.usage.ledger import UsageLedger, cost_of
from askmynotes.usage.log import (
    UsageEntry,
    UsageLog,
    entry_from_reply,
    logging_usage,
)

FAKE_CALL = 0.00182
FAKE_TEXT = 0.000005


def chat_usage(client: TestClient, chat_id: str) -> dict:
    response = client.get(f"/api/chats/{chat_id}/usage")
    assert response.status_code == 200, response.text
    return response.json()


def total_usage(client: TestClient) -> dict:
    response = client.get("/api/usage")
    assert response.status_code == 200, response.text
    return response.json()


def chat_id_of(events: list[dict]) -> str:
    return events[0]["chat"]["id"]


@pytest.fixture
def notes_module(tmp_path: Path) -> Module:
    """A module of three one-page lectures."""
    folder = tmp_path / "notes"
    folder.mkdir()
    make_pdf(folder / "a.pdf", ["Depreciation spreads the cost of an asset."])
    make_pdf(folder / "b.pdf", ["Goodwill is tested for impairment every year."])
    make_pdf(folder / "c.pdf", ["Leases are shown on the balance sheet."])
    return Module(name="Testing Module", short_name="TM", folder=folder)


def search_then_answer(messages: list[BaseMessage]) -> str | FakeReply:
    """Search the notes, then answer from the results."""
    if "short title" in text_of(messages[0]):
        return "A title"
    if isinstance(messages[-1], ToolMessage):
        return "From your notes.\n\nSources used: S1"
    return FakeReply(tool_call={"name": "search_notes", "args": {"query": "lease"}})


# Recording


def test_a_reply_and_its_title_are_recorded_against_the_chat(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path))

    chat_id = chat_id_of(send(client, "Hi"))

    usage = chat_usage(client, chat_id)
    assert usage["breakdown"]["replies"] == pytest.approx(FAKE_CALL)
    assert usage["breakdown"]["titles"] == pytest.approx(FAKE_CALL)
    assert usage["breakdown"]["summaries"] == 0
    assert usage["breakdown"]["searches"] == 0
    assert usage["cost"] == pytest.approx(2 * FAKE_CALL)
    assert usage["includesEstimate"] is False


def test_a_notes_answer_records_both_model_calls_and_the_search(
    tmp_path: Path, notes_module: Module
) -> None:
    model = FakeChatModel(responder=search_then_answer)
    with TestClient(build_app(tmp_path, model, modules=[notes_module])) as client:
        wait_until_updated(client)

        chat_id = chat_id_of(send(client, "What do my notes say about leases?"))

        usage = chat_usage(client, chat_id)
    # One call to decide to search, one to answer; one query embedded.
    assert usage["breakdown"]["replies"] == pytest.approx(2 * FAKE_CALL)
    assert usage["breakdown"]["searches"] == pytest.approx(FAKE_TEXT)
    assert usage["breakdown"]["titles"] == pytest.approx(FAKE_CALL)


def test_a_long_chat_summary_is_recorded_against_the_chat(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path, context_budget_tokens=100))
    with Database(tmp_path / "app.db").connection() as connection:
        chat = repository.create_chat(connection, "A long chat")
        for number in range(8):
            role = "user" if number % 2 == 0 else "assistant"
            repository.add_message(
                connection, chat.id, role, f"message {number} " + "x" * 140
            )

    send(client, "And the next question?", chat.id)

    usage = chat_usage(client, chat.id)
    assert usage["breakdown"]["summaries"] == pytest.approx(FAKE_CALL)
    assert usage["breakdown"]["replies"] == pytest.approx(FAKE_CALL)


def test_a_reply_without_an_openai_report_is_estimated(tmp_path: Path) -> None:
    model = FakeChatModel(responder=lambda m: FakeReply("x" * 40, reports_usage=False))
    client = TestClient(build_app(tmp_path, model))

    chat_id = chat_id_of(send(client, "Hi"))

    usage = chat_usage(client, chat_id)
    assert usage["includesEstimate"] is True
    assert usage["breakdown"]["replies"] > 0
    with Database(tmp_path / "app.db").connection() as connection:
        rows = connection.execute(
            "SELECT output_tokens FROM api_usage WHERE kind = 'reply' AND estimated"
        ).fetchall()
    assert [row["output_tokens"] for row in rows] == [10]  # 40 characters


def build_conversation(tmp_path: Path, responder):
    """A Conversation on a fake model, with its database."""
    model = FakeChatModel(responder=responder)
    database = Database(tmp_path / "app.db")
    repository.create_tables(database)
    ledger = usage_ledger(database)
    history = ModelHistory(database, model, tmp_path / "uploads", BIG_BUDGET, ledger)
    store = NotesStore(tmp_path / "chroma", FakeEmbeddings(), "fake")
    conversation = Conversation(
        database,
        Agent(model, NotesSearch(store, [], results_per_search=8)),
        model,
        tmp_path / "uploads",
        TEST_CONFIG,
        history,
        document_reader(tmp_path),
        ledger,
    )
    return conversation, database


def test_a_stopped_reply_records_an_estimate_of_what_was_written(
    tmp_path: Path,
) -> None:
    conversation, database = build_conversation(
        tmp_path,
        lambda messages: FakeReply("one two three four five six", delay_seconds=0.01),
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
        rows = connection.execute(
            "SELECT * FROM api_usage WHERE kind = 'reply' AND chat_id = ?",
            (prepared.chat_id,),
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["estimated"] == 1
    assert rows[0]["output_tokens"] == 4  # "one two three " is 14 characters
    assert rows[0]["input_tokens"] > 0
    assert rows[0]["cost"] > 0


def test_a_failed_reply_that_wrote_nothing_costs_nothing(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path))

    events = send(client, "Please fail")

    assert events[-1]["type"] == "error"
    usage = chat_usage(client, chat_id_of(events))
    assert usage["breakdown"]["replies"] == 0


def test_a_failed_call_that_had_written_something_is_estimated() -> None:
    log = UsageLog("model")
    log.begin_call(sent_characters=400)
    log.note_output(40)

    log.finish(failed=True)

    assert log.entries == [UsageEntry("reply", "model", 100, 0, 10, estimated=True)]


def test_a_failed_call_that_wrote_nothing_is_not_counted() -> None:
    log = UsageLog("model")
    log.begin_call(sent_characters=400)

    log.finish(failed=True)

    assert log.entries == []


def test_a_search_whose_call_never_reported_is_estimated_before_the_next_call() -> None:
    log = UsageLog("model")
    log.begin_call(sent_characters=400)
    log.note_output(20)

    log.continue_after_search(result_characters=80)
    log.note_output(8)
    log.finish(failed=False)

    # The first call sent 400 characters; the second also got that call's own
    # output and the results.
    assert log.entries == [
        UsageEntry("reply", "model", 100, 0, 5, estimated=True),
        UsageEntry("reply", "model", 125, 0, 2, estimated=True),
    ]


def test_a_title_without_a_report_is_estimated() -> None:
    from langchain_core.messages import AIMessage

    entry = entry_from_reply("title", "model", AIMessage(content="x" * 8), 40)

    assert entry == UsageEntry("title", "model", 10, 0, 2, estimated=True)


def test_a_notes_update_records_its_embeddings_with_no_chat(
    tmp_path: Path, notes_module: Module
) -> None:
    with TestClient(build_app(tmp_path, modules=[notes_module])) as client:
        wait_until_updated(client)

        total = total_usage(client)

    assert total["notesUpdates"] == pytest.approx(3 * FAKE_TEXT)  # three slides
    assert total["chats"] == 0
    assert total["deletedChats"] == 0
    with Database(tmp_path / "app.db").connection() as connection:
        rows = connection.execute("SELECT chat_id, kind FROM api_usage").fetchall()
    assert {(row["chat_id"], row["kind"]) for row in rows} == {(None, "notes_update")}


def json_response(data: list[dict], tokens: int) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "object": "list",
            "data": data,
            "model": "m",
            "usage": {"prompt_tokens": tokens, "total_tokens": tokens},
        },
    )


def test_the_embeddings_class_returns_the_vectors_in_order_and_reports_tokens() -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        # Answers out of order, to show each vector is matched to its text.
        data = [
            {"object": "embedding", "index": i, "embedding": [float(text[1:])]}
            for i, text in enumerate(body["input"])
        ]
        return json_response(data[::-1], tokens=len(body["input"]) * 7)

    import openai

    embeddings = CountingOpenAIEmbeddings("the-model", "key")
    embeddings._client = openai.OpenAI(
        api_key="key", http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    texts = [f"t{n}" for n in range(150)]
    log = UsageLog(embedding_kind="notes_update")

    with logging_usage(log):
        vectors = embeddings.embed_documents(texts)

    assert vectors == [[float(n)] for n in range(150)]
    assert [r["model"] for r in requests] == ["the-model", "the-model"]
    assert [len(r["input"]) for r in requests] == [100, 50]  # two batches
    assert log.entries == [
        UsageEntry("notes_update", "the-model", 700, 0, 0),
        UsageEntry("notes_update", "the-model", 350, 0, 0),
    ]


def sse(chunks: list[dict]) -> bytes:
    lines = [f"data: {json.dumps(chunk)}\n\n" for chunk in chunks]
    return ("".join(lines) + "data: [DONE]\n\n").encode()


def test_the_agent_reads_openais_streamed_usage_report(tmp_path: Path) -> None:
    """With the real chat model class talking to a pretend OpenAI, the agent
    picks up the usage OpenAI sends after the last piece of text."""
    requests: list[dict] = []
    base = {"id": "x", "object": "chat.completion.chunk", "created": 1, "model": "m"}

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        body = sse(
            [
                {
                    **base,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"role": "assistant", "content": "Hello"},
                        }
                    ],
                },
                {
                    **base,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                },
                {
                    **base,
                    "choices": [],
                    "usage": {
                        "prompt_tokens": 120,
                        "completion_tokens": 30,
                        "total_tokens": 150,
                        "prompt_tokens_details": {"cached_tokens": 100},
                    },
                },
            ]
        )
        return httpx.Response(
            200, content=body, headers={"content-type": "text/event-stream"}
        )

    model = ChatOpenAI(
        model="m",
        api_key="key",
        stream_usage=True,
        http_async_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    store = NotesStore(tmp_path / "chroma", FakeEmbeddings(), "fake")
    agent = Agent(model, NotesSearch(store, [], results_per_search=8))
    log = UsageLog("m")

    async def run() -> str:
        pieces = [
            piece
            async for piece in agent.stream_reply(
                [HumanMessage(content="Hi")], FoundNotes(), log
            )
        ]
        return "".join(str(p) for p in pieces)

    assert asyncio.run(run()) == "Hello"
    assert requests[0]["stream_options"] == {"include_usage": True}
    assert log.entries == [UsageEntry("reply", "m", 120, 100, 30)]


def test_the_real_chat_model_is_asked_for_usage_reports() -> None:
    env = EnvSettings(openai_api_key="key", chat_model="m", embedding_model="e")

    assert create_chat_model(env).stream_usage is True  # type: ignore[attr-defined]


# Prices


def test_the_cost_of_a_call_prices_cached_input_separately() -> None:
    call = UsageEntry(
        "reply", "m", input_tokens=1000, cached_tokens=200, output_tokens=500
    )
    embedded = UsageEntry(
        "search", "e", input_tokens=10, cached_tokens=0, output_tokens=0
    )

    assert cost_of(call, TEST_PRICES) == pytest.approx(FAKE_CALL)
    assert cost_of(embedded, TEST_PRICES) == pytest.approx(FAKE_TEXT)


def test_a_later_price_change_does_not_change_what_was_recorded(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "app.db")
    repository.create_tables(database)
    ledger = usage_ledger(database)
    entry = UsageEntry("reply", "m", 1000, 200, 500)
    ledger.record([entry], None)

    dearer = TEST_PRICES.model_copy(update={"chat_output": 200.0})
    later = UsageLedger(database, dearer)
    later.create_tables()
    later.record([entry], None)

    with database.connection() as connection:
        costs = [r["cost"] for r in connection.execute("SELECT cost FROM api_usage")]
    assert costs[0] == pytest.approx(FAKE_CALL)
    assert costs[1] > 50 * costs[0]


# Totals


def test_the_all_chats_total_keeps_deleted_chats_and_notes_updates_apart(
    tmp_path: Path, notes_module: Module
) -> None:
    with TestClient(build_app(tmp_path, modules=[notes_module])) as client:
        wait_until_updated(client)
        kept = chat_id_of(send(client, "Keep this"))
        deleted = chat_id_of(send(client, "Delete this"))
        kept_cost = chat_usage(client, kept)["cost"]
        deleted_cost = chat_usage(client, deleted)["cost"]

        assert client.delete(f"/api/chats/{deleted}").status_code == 204
        total = total_usage(client)

    assert client.get(f"/api/chats/{deleted}/usage").status_code == 404
    assert total["chats"] == pytest.approx(kept_cost)
    assert total["deletedChats"] == pytest.approx(deleted_cost)
    assert total["notesUpdates"] == pytest.approx(3 * FAKE_TEXT)
    assert total["cost"] == pytest.approx(kept_cost + deleted_cost + 3 * FAKE_TEXT)


def test_a_chats_total_is_the_sum_of_its_own_calls_only(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path))
    first = chat_id_of(send(client, "One"))
    second = chat_id_of(send(client, "Two"))

    send(client, "Another question", first)

    # First chat: reply + title, then a second reply. Second chat: reply + title.
    assert chat_usage(client, first)["cost"] == pytest.approx(3 * FAKE_CALL)
    assert chat_usage(client, second)["cost"] == pytest.approx(2 * FAKE_CALL)
    assert total_usage(client)["cost"] == pytest.approx(5 * FAKE_CALL)


def test_the_usage_endpoints_have_these_shapes_and_unknown_chats_are_404(
    tmp_path: Path,
) -> None:
    client = TestClient(build_app(tmp_path))
    chat_id = chat_id_of(send(client, "Hi"))

    assert set(chat_usage(client, chat_id)) == {
        "cost",
        "breakdown",
        "includesEstimate",
        "earlierCostsUnrecorded",
        "trackingStartedAt",
        "context",
    }
    assert set(chat_usage(client, chat_id)["context"]) == {
        "tokens",
        "budgetTokens",
        "summarised",
        "overBudget",
    }
    assert set(total_usage(client)) == {
        "cost",
        "chats",
        "deletedChats",
        "notesUpdates",
        "includesEstimate",
        "trackingStartedAt",
    }
    assert client.get("/api/chats/nope/usage").status_code == 404


# Chats from before cost tracking


def test_a_database_from_before_cost_tracking_opens_and_says_earlier_costs_are_missing(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "app.db")
    repository.create_tables(database)  # the tables as they were before phase 19
    with database.connection() as connection:
        old = repository.create_chat(
            connection, "Old chat", at=datetime(2025, 1, 1, tzinfo=UTC)
        )
        repository.add_message(connection, old.id, "user", "An old question")

    client = TestClient(build_app(tmp_path))
    new = chat_id_of(send(client, "A new question"))

    opened = client.get(f"/api/chats/{old.id}").json()
    assert opened["title"] == "Old chat"
    assert opened["messages"][0]["content"] == "An old question"
    old_usage = chat_usage(client, old.id)
    assert old_usage["cost"] == 0
    assert old_usage["earlierCostsUnrecorded"] is True
    assert chat_usage(client, new)["earlierCostsUnrecorded"] is False


def test_tracking_began_is_kept_across_restarts(tmp_path: Path) -> None:
    first = total_usage(TestClient(build_app(tmp_path)))["trackingStartedAt"]

    second = total_usage(TestClient(build_app(tmp_path)))["trackingStartedAt"]

    assert first == second


# The context readout


def test_the_context_estimate_is_what_the_long_chat_budget_measures(
    tmp_path: Path,
) -> None:
    client = TestClient(build_app(tmp_path, context_budget_tokens=200))
    with Database(tmp_path / "app.db").connection() as connection:
        chat = repository.create_chat(connection, "A chat")
        for number in range(2):
            role = "user" if number % 2 == 0 else "assistant"
            repository.add_message(connection, chat.id, role, "x" * 100)

    def measured() -> int:
        with Database(tmp_path / "app.db").connection() as connection:
            detail = repository.get_chat(connection, chat.id)
            summary, up_to = repository.get_summary(connection, chat.id)
        recent = [m for m in detail.messages if m.id > up_to]
        return sum(estimate_tokens(m) for m in recent) + len(summary or "") // 4

    before = chat_usage(client, chat.id)["context"]
    assert before["tokens"] == measured() == 50
    assert before["budgetTokens"] == 200
    assert before["summarised"] is False
    assert before["overBudget"] is False

    # Over the budget with nothing yet summarised: the next message summarises.
    with Database(tmp_path / "app.db").connection() as connection:
        repository.add_message(connection, chat.id, "user", "y" * 700)
    assert chat_usage(client, chat.id)["context"]["overBudget"] is True

    send(client, "And now?", chat.id)

    after = chat_usage(client, chat.id)["context"]
    assert after["summarised"] is True
    assert after["tokens"] == measured()
    assert after["tokens"] < 200


def test_an_attached_document_counts_in_the_context_estimate(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path))
    make_docx(tmp_path / "essay.docx", ["Goodwill " * 100])
    document = {
        "name": "essay.docx",
        "data": base64.b64encode((tmp_path / "essay.docx").read_bytes()).decode(),
    }

    response = client.post(
        "/api/chats/send",
        json={"chatId": None, "text": "Read it", "documents": [document]},
    )
    assert response.status_code == 200, response.text
    chat_id = chat_id_of(read_events(response.text))

    with Database(tmp_path / "app.db").connection() as connection:
        messages = repository.get_chat(connection, chat_id).messages
    expected = sum(estimate_tokens(m) for m in messages)
    context = chat_usage(client, chat_id)["context"]
    assert context["tokens"] == expected
    assert expected > 200  # the document's 900 characters are in there
