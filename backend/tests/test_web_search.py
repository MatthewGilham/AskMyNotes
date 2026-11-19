"""Tests for web search: the pages a reply cites, how they are saved and listed,
what each search costs, and the model running in OpenAI's Responses mode.

Everything is free: the fake model reports searches and citations the way the
real one's stream does, and the Responses tests replay events recorded from the
real API (`fixtures/responses_events.json`) to a pretend OpenAI server.
"""

import asyncio
import base64
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from helpers import (
    BIG_BUDGET,
    TEST_CONFIG,
    TEST_PRICES,
    TEST_WEB_SEARCH,
    build_app,
    document_reader,
    send,
    upload,
    usage_ledger,
    wait_until_updated,
)
from langchain_core.messages import AIMessageChunk, HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from askmynotes.agent.agent import (
    Agent,
    NotesSearchStarted,
    WebSearchStarted,
    create_chat_model,
)
from askmynotes.calculator.tools import ToolRuns
from askmynotes.chats import repository
from askmynotes.chats.conversation import Conversation
from askmynotes.chats.history import ModelHistory
from askmynotes.chats.images import message_content
from askmynotes.chats.models import SendRequest
from askmynotes.database import Database
from askmynotes.evaluation.agent_run import ask_agent
from askmynotes.fake_model import (
    FAKE_WEB_PAGES,
    FakeChatModel,
    FakeEmbeddings,
    FakeReply,
    text_of,
)
from askmynotes.interpreter.reply import PythonReply
from askmynotes.notes.chunking import Chunk
from askmynotes.notes.search import FoundNotes, NotesSearch
from askmynotes.notes.store import NotesStore
from askmynotes.settings import EnvSettings, Module, load_app_settings
from askmynotes.usage.log import UsageEntry, UsageLog
from askmynotes.web.search import (
    FoundWeb,
    WatchedStream,
    site_name,
    watch_web_searches,
    web_search_tool,
)

FIXTURE = Path(__file__).parent / "fixtures" / "responses_events.json"
# Two fake web searches at the test price of $0.50 each.
TWO_SEARCHES = 2 * TEST_PRICES.web_search_call
# One fake model call: (800 x 1.0 + 200 x 0.1 + 500 x 2.0) / 1,000,000.
FAKE_CALL = 0.00182


def chat_id_of(events: list[dict]) -> str:
    return events[0]["chat"]["id"]


def done_message(events: list[dict]) -> dict:
    return next(e for e in events if e["type"] == "done")["message"]


# What a reply that searched the web saves


def test_a_web_reply_streams_two_web_searching_events(tmp_path: Path) -> None:
    with TestClient(build_app(tmp_path / "data")) as client:
        wait_until_updated(client)
        events = send(client, "What is the rate? Use the web")

    searching = [e for e in events if e["type"] == "searching"]
    assert [e["kind"] for e in searching] == ["web", "web"]


def test_a_notes_search_event_says_it_is_for_the_notes(tmp_path: Path) -> None:
    with TestClient(build_app(tmp_path / "data")) as client:
        wait_until_updated(client)
        events = send(client, "Explain it from my notes")

    assert [e["kind"] for e in events if e["type"] == "searching"] == ["notes"]


def test_the_pages_a_reply_cites_are_saved_and_come_back_when_reopened(
    tmp_path: Path,
) -> None:
    with TestClient(build_app(tmp_path / "data")) as client:
        wait_until_updated(client)
        events = send(client, "What is the rate? Use the web")
        reopened = client.get(f"/api/chats/{chat_id_of(events)}").json()

    saved = done_message(events)["webSources"]
    assert saved == [
        {
            "title": "Bank Rate | Example Bank",
            "site": "example-bank.test",
            "url": "https://www.example-bank.test/rate",
            "cited": True,
        },
        {
            "title": "Rates explained",
            "site": "news.example.test",
            "url": "https://news.example.test/rates",
            "cited": True,
        },
        # The pages the searches read and the answer didn't cite, listed by
        # their addresses. The two cited pages, which the searches also read,
        # are not listed again.
        {
            "title": "regulator.example.test/policy/statement",
            "site": "regulator.example.test",
            "url": "https://regulator.example.test/policy/statement",
            "cited": False,
        },
        {
            "title": "data.example.test/series/rate",
            "site": "data.example.test",
            "url": "https://data.example.test/series/rate",
            "cited": False,
        },
        {
            "title": "blog.example.test/2026/10/rates-roundup",
            "site": "blog.example.test",
            "url": "https://blog.example.test/2026/10/rates-roundup",
            "cited": False,
        },
    ]
    assert done_message(events)["webSearches"] == ["fake search 1", "fake search 2"]
    assert reopened["messages"][-1]["webSources"] == saved
    assert reopened["messages"][-1]["webSearches"] == ["fake search 1", "fake search 2"]
    assert ":::web" in reopened["messages"][-1]["content"]


def test_a_reply_that_did_not_search_the_web_has_no_web_sources(
    tmp_path: Path,
) -> None:
    with TestClient(build_app(tmp_path / "data")) as client:
        wait_until_updated(client)
        events = send(client, "Hello")

    assert done_message(events)["webSources"] is None


def test_a_page_cited_twice_is_listed_once_in_the_order_first_cited() -> None:
    found = FoundWeb()
    cited = [
        {"type": "url_citation", "title": "B", "url": "https://b.test/x"},
        {"type": "url_citation", "title": "A", "url": "https://www.a.test/y"},
        {"type": "url_citation", "title": "B again", "url": "https://b.test/x"},
    ]

    found.read(AIMessageChunk(content=[{"type": "text", "annotations": cited}]))

    assert [(s.title, s.site) for s in found.sources] == [
        ("B", "b.test"),
        ("A", "a.test"),
    ]


def test_the_same_search_reported_twice_counts_once() -> None:
    found = FoundWeb()
    search = {"type": "web_search_call", "id": "ws_1", "status": "in_progress"}

    first = found.read(AIMessageChunk(content=[search]))
    again = found.read(AIMessageChunk(content=[{**search, "status": "completed"}]))

    assert (first, again, found.search_count) == (1, 0, 1)


def test_a_page_without_a_title_is_listed_by_its_site() -> None:
    found = FoundWeb()
    annotation = {"type": "url_citation", "url": "https://www.s.test/p"}

    found.read(AIMessageChunk(content=[{"type": "text", "annotations": [annotation]}]))

    assert found.sources[0].title == "s.test"


def test_a_stopped_reply_counts_its_searches_but_has_no_pages_yet(
    tmp_path: Path,
) -> None:
    model = FakeChatModel(
        responder=lambda m: FakeReply(
            ":::web\nOne two three four five\n:::",
            delay_seconds=0.01,
            web_searches=1,
            web_citations=FAKE_WEB_PAGES,
        )
    )
    database = Database(tmp_path / "app.db")
    repository.create_tables(database)
    ledger = usage_ledger(database)
    agent = Agent(
        model, NotesSearch(empty_store(tmp_path), [], 8), web_search=TEST_WEB_SEARCH
    )
    conversation = Conversation(
        database,
        agent,
        model,
        tmp_path / "uploads",
        TEST_CONFIG,
        ModelHistory(database, model, tmp_path / "uploads", BIG_BUDGET, ledger),
        document_reader(tmp_path),
        ledger,
    )
    prepared = conversation.start_message(SendRequest(text="Search the web"))

    async def stop_after_two_pieces() -> None:
        stream = conversation.stream(prepared)
        tokens = 0
        async for event in stream:
            tokens += event.type == "token"
            if tokens == 2:
                break
        await stream.aclose()  # what happens when the browser disconnects

    asyncio.run(stop_after_two_pieces())

    with database.connection() as connection:
        saved = repository.get_chat(connection, prepared.chat_id).messages[-1]
        searches = connection.execute(
            "SELECT COUNT(*) FROM api_usage WHERE kind = 'web_search'"
        ).fetchone()[0]
    assert saved.status == "stopped"
    # OpenAI reports a search before the text, but cites pages after it, so a
    # reply stopped part-way has paid for its search and has no pages to list.
    assert searches == 1
    assert saved.web_sources is None


def test_regenerating_a_web_reply_replaces_its_web_sources(tmp_path: Path) -> None:
    answers = iter(
        [
            FakeReply(
                ":::web\nOld.\n:::", web_searches=1, web_citations=FAKE_WEB_PAGES
            ),
            FakeReply("A reply without the web."),
        ]
    )
    model = FakeChatModel(
        responder=lambda m: (
            "A title" if "short title" in text_of(m[0]) else next(answers)
        )
    )
    with TestClient(build_app(tmp_path / "data", model)) as client:
        wait_until_updated(client)
        events = send(client, "Question")
        chat_id = chat_id_of(events)
        assert done_message(events)["webSources"] is not None
        regenerated = client.post(f"/api/chats/{chat_id}/regenerate")
        messages = client.get(f"/api/chats/{chat_id}").json()["messages"]

    assert regenerated.status_code == 200
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[-1]["webSources"] is None


def test_editing_the_latest_question_removes_the_old_answers_web_sources(
    tmp_path: Path,
) -> None:
    with TestClient(build_app(tmp_path / "data")) as client:
        wait_until_updated(client)
        events = send(client, "First question about the web")
        chat_id = chat_id_of(events)
        question = events[0]["userMessage"]
        edited = client.post(
            f"/api/chats/{chat_id}/messages/{question['id']}/edit",
            json={
                "text": "Now a plain question",
                "expectedLatestMessageId": question["id"],
                "expectedOriginalText": question["content"],
            },
        )
        messages = client.get(f"/api/chats/{chat_id}").json()["messages"]

    assert edited.status_code == 200, edited.text
    assert messages[-1]["webSources"] is None
    assert ":::web" not in messages[-1]["content"]


def test_an_older_database_gets_the_web_sources_column_and_keeps_its_messages(
    tmp_path: Path,
) -> None:
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
            created_at TEXT NOT NULL, quoted_context TEXT);
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
    assert chat.messages[0].web_sources is None


# Costs


def test_each_web_search_is_a_ledger_row_at_the_settings_price(tmp_path: Path) -> None:
    with TestClient(build_app(tmp_path / "data")) as client:
        wait_until_updated(client)
        events = send(client, "What is the rate? Use the web")
        chat_id = chat_id_of(events)
        usage = client.get(f"/api/chats/{chat_id}/usage").json()
        total = client.get("/api/usage").json()
    with sqlite3.connect(tmp_path / "data" / "app.db") as connection:
        rows = connection.execute(
            "SELECT cost FROM api_usage WHERE kind = 'web_search'"
        ).fetchall()

    assert [cost for (cost,) in rows] == [0.5, 0.5]
    assert usage["breakdown"]["webSearches"] == pytest.approx(TWO_SEARCHES)
    # The reply, the title and two searches.
    assert usage["cost"] == pytest.approx(2 * FAKE_CALL + TWO_SEARCHES)
    assert total["cost"] == pytest.approx(usage["cost"])


def test_an_older_ledger_is_rebuilt_to_allow_web_searches(tmp_path: Path) -> None:
    path = tmp_path / "app.db"
    old = sqlite3.connect(path)
    old.executescript(
        """
        CREATE TABLE api_usage (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT,
            kind TEXT NOT NULL CHECK (kind IN ('reply', 'title', 'summary',
                'search', 'notes_update')),
            model TEXT NOT NULL, input_tokens INTEGER NOT NULL,
            cached_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL,
            cost REAL NOT NULL, estimated INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL);
        CREATE INDEX api_usage_by_chat ON api_usage(chat_id);
        INSERT INTO api_usage (chat_id, kind, model, input_tokens, cached_tokens,
            output_tokens, cost, created_at)
            VALUES ('c', 'reply', 'm', 1, 0, 1, 0.25, 'x');
        """
    )
    old.commit()
    old.close()
    database = Database(path)

    ledger = usage_ledger(database)
    ledger.record([UsageEntry("web_search", "m", 0, 0, 0)], "c")

    with database.connection() as connection:
        rows = connection.execute(
            "SELECT kind, cost FROM api_usage ORDER BY id"
        ).fetchall()
    assert [(r["kind"], r["cost"]) for r in rows] == [
        ("reply", 0.25),
        ("web_search", 0.5),
    ]
    # Starting again changes nothing.
    usage_ledger(database)
    with database.connection() as connection:
        count = connection.execute("SELECT COUNT(*) FROM api_usage").fetchone()[0]
    assert count == 2


# The tool, the instructions and the settings


class ToolRecordingModel(FakeChatModel):
    """A fake model that remembers which tools the agent offered it."""

    offered: list[Any] = []

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        self.offered.extend(tools)
        return super().bind_tools(tools, **kwargs)


def empty_store(tmp_path: Path) -> NotesStore:
    return NotesStore(tmp_path / "chroma", FakeEmbeddings(), "fake")


def run_agent(agent: Agent) -> None:
    async def run() -> None:
        async for _piece in agent.stream_reply(
            [HumanMessage(content="Hi")], FoundNotes()
        ):
            pass

    asyncio.run(run())


def test_the_agent_offers_web_search_with_the_settings_location(tmp_path: Path) -> None:
    model = ToolRecordingModel(responder=lambda m: "Hello", offered=[])
    agent = Agent(
        model, NotesSearch(empty_store(tmp_path), [], 8), web_search=TEST_WEB_SEARCH
    )

    run_agent(agent)

    hosted = [t for t in model.offered if isinstance(t, dict)]
    assert hosted == [
        {
            "type": "web_search",
            "user_location": {
                "type": "approximate",
                "country": "GB",
                "timezone": "Europe/London",
            },
        }
    ]
    assert web_search_tool(TEST_WEB_SEARCH) == hosted[0]


def test_without_a_location_the_agent_has_no_web_search(tmp_path: Path) -> None:
    model = ToolRecordingModel(responder=lambda m: "Hello", offered=[])

    run_agent(Agent(model, NotesSearch(empty_store(tmp_path), [], 8)))

    # Only the calculator, which is always there.
    assert [t.name for t in model.offered] == ["calculate", "solve_equation"]


def test_the_instructions_contain_the_web_rules(tmp_path: Path) -> None:
    model = FakeChatModel(responder=lambda m: "Hello")
    with TestClient(build_app(tmp_path / "data", model)) as client:
        wait_until_updated(client)
        send(client, "Hi")

    answer_call = [m for m in model.received if "short title" not in text_of(m[0])][0]
    instructions = " ".join(text_of(answer_call[0]).split())
    assert "## Searching the web" in instructions
    assert "starts with a line that is exactly `:::web`" in instructions
    assert "Always search the web when the student asks you to" in instructions
    assert "Never put web content in a" in instructions
    assert "Don't search the web, unless the student asks" in instructions


def example_settings_without(tmp_path: Path, line: str) -> Path:
    text = (Path(__file__).parents[2] / "settings.example.toml").read_text(
        encoding="utf-8"
    )
    assert line in text
    path = tmp_path / "settings.toml"
    path.write_text(text.replace(line, ""), encoding="utf-8")
    return path


def test_a_missing_location_setting_stops_start_up_naming_it(tmp_path: Path) -> None:
    path = example_settings_without(tmp_path, 'country = "GB"\n')

    with pytest.raises(ValidationError, match="country"):
        load_app_settings(path)


def test_a_missing_search_price_stops_start_up_naming_it(tmp_path: Path) -> None:
    path = example_settings_without(tmp_path, "web_search_call = 0.01\n")

    with pytest.raises(ValidationError, match="web_search_call"):
        load_app_settings(path)


def test_a_site_is_shown_without_www() -> None:
    assert site_name("https://www.example.test/a?b=c") == "example.test"
    assert site_name("https://docs.example.test/") == "docs.example.test"


# The evaluation's agent run


def test_an_evaluation_run_records_whether_the_agent_searched_the_web(
    tmp_path: Path,
) -> None:
    agent = Agent(
        FakeChatModel(),
        NotesSearch(empty_store(tmp_path), [], 8),
        web_search=TEST_WEB_SEARCH,
    )

    searched = asyncio.run(ask_agent(agent, "What is the rate on the web?"))
    plain = asyncio.run(ask_agent(agent, "Give me a pancake recipe"))

    assert (searched.web_searched, searched.searched) == (True, False)
    assert (plain.web_searched, plain.searched) == (False, False)


# The real chat model class in Responses mode, against a pretend OpenAI


def responses_model(handler: Any) -> ChatOpenAI:
    """The same settings as `create_chat_model`, talking to a pretend server."""
    return ChatOpenAI(
        model="m",
        api_key="key",
        use_responses_api=True,
        output_version="responses/v1",
        store=False,
        stream_usage=True,
        http_async_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def replay(name: str) -> httpx.Response:
    """A recorded stream of events, as the server-sent events OpenAI sends."""
    events = json.loads(FIXTURE.read_text(encoding="utf-8"))[name]
    body = "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events)
    return httpx.Response(
        200, content=body.encode(), headers={"content-type": "text/event-stream"}
    )


def stream_with(
    agent: Agent, content: Any, log: UsageLog, web: FoundWeb | None = None
) -> list:
    async def run() -> list:
        return [
            piece
            async for piece in agent.stream_reply(
                [HumanMessage(content=content)], FoundNotes(), log, web
            )
        ]

    return asyncio.run(run())


def test_responses_mode_streams_text_and_reports_usage(tmp_path: Path) -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return replay("text")

    agent = Agent(responses_model(handler), NotesSearch(empty_store(tmp_path), [], 8))
    log = UsageLog("m")

    pieces = stream_with(agent, "Hi", log)

    assert "".join(str(p) for p in pieces) == "Hello, nice to meet you."
    assert requests[0]["store"] is False
    assert requests[0]["stream"] is True
    assert log.entries == [UsageEntry("reply", "m", 12, 0, 11)]


def test_responses_mode_calls_search_notes_and_answers_with_the_results(
    tmp_path: Path,
) -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return replay("function_call" if len(requests) == 1 else "text")

    store = empty_store(tmp_path)
    store.add(
        [
            Chunk(
                id="TM/lecture.pdf#1#1",
                text="Depreciation spreads cost.",
                text_to_embed="Depreciation spreads cost.",
                metadata={
                    "file_id": "TM/lecture.pdf",
                    "module": "TM",
                    "file_name": "lecture.pdf",
                    "location": "slide",
                    "number": 1,
                    "part": 1,
                },
            )
        ]
    )
    module = Module(name="Testing Module", short_name="TM", folder=tmp_path)
    agent = Agent(responses_model(handler), NotesSearch(store, [module], 8))
    log = UsageLog("m")

    pieces = stream_with(agent, "Depreciation?", log)

    assert any(isinstance(p, NotesSearchStarted) for p in pieces)
    assert len(requests) == 2
    results = [
        item["output"]
        for item in requests[1]["input"]
        if item.get("type") == "function_call_output"
    ]
    assert "Depreciation spreads cost." in results[0]
    assert [t.get("name") for t in requests[0]["tools"]] == [
        "search_notes",
        "calculate",
        "solve_equation",
    ]
    # Both model calls were reported: 45 and 12 tokens in. The notes search
    # between them embedded its query.
    replies = [e.input_tokens for e in log.entries if e.kind == "reply"]
    assert replies == [45, 12]


def test_responses_mode_sends_an_attached_image_to_the_model(tmp_path: Path) -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return replay("text")

    uploads = tmp_path / "uploads"
    (uploads / "chat").mkdir(parents=True)
    (uploads / "chat" / "a.png").write_bytes(base64.b64decode(upload()["data"]))
    content = message_content(uploads, "What is this?", ["chat/a.png"])
    agent = Agent(responses_model(handler), NotesSearch(empty_store(tmp_path), [], 8))

    stream_with(agent, content, UsageLog("m"))

    parts = requests[0]["input"][-1]["content"]
    assert [p["type"] for p in parts] == ["input_text", "input_image"]
    assert parts[1]["image_url"].startswith("data:image/png;base64,")


def test_responses_mode_reports_a_web_search_its_pages_and_its_cost(
    tmp_path: Path,
) -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return replay("web_search")

    agent = Agent(
        responses_model(handler),
        NotesSearch(empty_store(tmp_path), [], 8),
        web_search=TEST_WEB_SEARCH,
    )
    log = UsageLog("m")
    web = FoundWeb()

    pieces = stream_with(agent, "Rate?", log, web)

    hosted = [t for t in requests[0]["tools"] if t["type"] == "web_search"]
    assert hosted[0]["user_location"]["country"] == "GB"
    assert sum(isinstance(p, WebSearchStarted) for p in pieces) == 1
    assert "3.75%" in "".join(p for p in pieces if isinstance(p, str))
    assert [s.site for s in web.sources] == ["bankofengland.co.uk"]
    assert [e.kind for e in log.entries] == ["web_search", "reply"]
    # The pages the search read are in the reply's own tokens.
    assert log.entries[1].input_tokens == 8424


def test_the_app_builds_its_model_in_responses_mode_without_storing_chats() -> None:
    model = create_chat_model(
        EnvSettings(openai_api_key="key", chat_model="m", embedding_model="e")
    )

    assert model.use_responses_api is True  # type: ignore[attr-defined]
    assert model.store is False  # type: ignore[attr-defined]
    assert model.output_version == "responses/v1"  # type: ignore[attr-defined]


# Phase 26: the status while a search runs, every searched page, and searching
# together with calculating


def test_a_search_is_announced_before_it_has_finished(tmp_path: Path) -> None:
    """OpenAI's own stream, with the installed LangChain: the start of the search
    is passed on while the finished search has not yet been read. If an upgrade
    of LangChain stopped the wrapper seeing the events, this would fail."""
    agent = Agent(
        watch_web_searches(responses_model(lambda request: replay("web_search"))),
        NotesSearch(empty_store(tmp_path), [], 8),
        web_search=TEST_WEB_SEARCH,
    )
    log = UsageLog("m")
    web = FoundWeb()
    searches_read_when_announced: list[int] = []

    async def run() -> None:
        async for piece in agent.stream_reply(
            [HumanMessage(content="Rate?")], FoundNotes(), log, web
        ):
            if isinstance(piece, WebSearchStarted):
                searches_read_when_announced.append(web.search_count)

    asyncio.run(run())

    assert searches_read_when_announced == [0]
    # Counted once for the cost, however many times it was reported.
    assert [e.kind for e in log.entries] == ["web_search", "reply"]


def test_every_event_passes_through_the_watched_stream_unchanged(monkeypatch) -> None:
    announced: list[bool] = []
    monkeypatch.setattr(
        "askmynotes.web.search.announce_search_started", lambda: announced.append(True)
    )

    def event(kind: str, item_kind: str | None = None) -> Any:
        item = None if item_kind is None else SimpleNamespace(type=item_kind)
        return SimpleNamespace(type=kind, item=item)

    events = [
        event("response.created"),
        event("response.output_item.added", "reasoning"),
        event("response.output_item.added", "web_search_call"),
        event("response.output_item.done", "web_search_call"),
        event("response.output_text.delta"),
    ]

    class Stream:
        async def __aenter__(self) -> "Stream":
            return self

        async def __aexit__(self, *error: Any) -> None:
            return None

        async def __aiter__(self) -> Any:
            for item in events:
                yield item

    async def run() -> list:
        async with WatchedStream(Stream()) as stream:
            return [item async for item in stream]

    assert asyncio.run(run()) == events
    # Only the start of a search is announced, not its finish or anything else.
    assert announced == [True]


def test_a_reply_announces_each_of_its_searches_once(tmp_path: Path) -> None:
    model = FakeChatModel(
        responder=lambda m: FakeReply("Done.", web_searches=2, search_seconds=0.05)
    )
    agent = Agent(
        model, NotesSearch(empty_store(tmp_path), [], 8), web_search=TEST_WEB_SEARCH
    )

    async def run() -> list:
        return [
            piece
            async for piece in agent.stream_reply(
                [HumanMessage(content="Rate?")], FoundNotes()
            )
        ]

    pieces = asyncio.run(run())

    assert [type(p).__name__ for p in pieces[:2]] == ["WebSearchStarted"] * 2
    assert sum(isinstance(p, WebSearchStarted) for p in pieces) == 2


def test_a_search_reported_only_when_it_finishes_still_counts() -> None:
    """If OpenAI sent no start event, the finished search is still seen."""
    found = FoundWeb()
    search = {"type": "web_search_call", "id": "ws_1", "status": "completed"}

    assert found.read(AIMessageChunk(content=[search])) == 1


def test_the_request_asks_for_every_page_a_search_reads(tmp_path: Path) -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return replay("text")

    agent = Agent(
        responses_model(handler),
        NotesSearch(empty_store(tmp_path), [], 8),
        web_search=TEST_WEB_SEARCH,
    )
    stream_with(agent, "Hi", UsageLog("m"))

    assert requests[0]["include"] == ["web_search_call.action.sources"]


def test_python_adds_its_include_without_replacing_the_web_one(tmp_path: Path) -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return replay("text")

    agent = Agent(
        responses_model(handler),
        NotesSearch(empty_store(tmp_path), [], 8),
        web_search=TEST_WEB_SEARCH,
    )

    async def run() -> None:
        async for _piece in agent.stream_reply(
            [HumanMessage(content="Hi")],
            FoundNotes(),
            python=PythonReply("cntr_1", [], ToolRuns()),
        ):
            pass

    asyncio.run(run())

    assert requests[0]["include"] == [
        "web_search_call.action.sources",
        "code_interpreter_call.outputs",
    ]


def search_block(sources: list[str], query: str = "bank rate") -> dict:
    """A finished search, as the real stream reports it."""
    return {
        "type": "web_search_call",
        "id": f"ws_{query}",
        "status": "completed",
        "action": {
            "type": "search",
            "queries": [query],
            "query": query,
            "sources": [{"type": "url", "url": url} for url in sources],
        },
    }


def test_a_search_records_what_it_asked_and_the_pages_it_read() -> None:
    found = FoundWeb()
    first = search_block(["https://a.test/x", "https://www.b.test/y/"], "first query")
    second = search_block(["https://b.test/y", "https://c.test/z"], "second query")

    found.read(AIMessageChunk(content=[first]))
    found.read(AIMessageChunk(content=[second]))
    # The same search reported again adds nothing.
    found.read(AIMessageChunk(content=[first]))

    assert found.queries == ["first query", "second query"]
    assert [p.url for p in found.pages()] == [
        "https://a.test/x",
        "https://www.b.test/y/",
        "https://c.test/z",
    ]
    assert not any(p.cited for p in found.pages())


def test_a_page_both_searched_and_cited_is_listed_once_as_cited() -> None:
    found = FoundWeb()
    citation = {
        "type": "url_citation",
        "title": "The story",
        # OpenAI adds this tracking to the links it cites.
        "url": "https://news.test/story?utm_source=openai",
    }
    found.read(
        AIMessageChunk(
            content=[
                search_block(
                    ["https://news.test/story/", "https://other.test/page"], "q"
                ),
                {"type": "text", "annotations": [citation]},
            ]
        )
    )

    pages = found.pages()

    assert [(p.title, p.cited) for p in pages] == [
        ("The story", True),
        ("other.test/page", False),
    ]


def test_an_uncited_page_without_a_title_is_listed_by_a_short_address() -> None:
    found = FoundWeb()
    long_path = "/".join(["section"] * 20)
    found.read(
        AIMessageChunk(content=[search_block([f"https://www.s.test/{long_path}"])])
    )

    page = found.pages()[0]

    assert page.site == "s.test"
    assert page.title.startswith("s.test/section/section")
    assert len(page.title) == 70
    assert page.title.endswith("…")


REPLY_WITH_LINKS = """\
A link outside any box: [outside](https://outside.test/a)

:::beyond
Not from the web: [beyond](https://beyond.test/b)
:::

:::web
Rate [one](https://one.test/rate), and in a callout:

:::formula
See [two](https://two.test/formula)
:::

```
[in code](https://code.test/c)
```
:::
"""


def test_links_inside_a_web_box_count_as_cited_and_others_do_not() -> None:
    found = FoundWeb()

    found.cite_links_in(REPLY_WITH_LINKS)

    # Not the link outside any box, nor the one in "Beyond your notes", nor the
    # one inside a code block, which is code and not a link.
    assert [s.url for s in found.sources] == [
        "https://one.test/rate",
        "https://two.test/formula",
    ]


def test_a_link_in_the_text_promotes_a_searched_page_and_keeps_url_citations() -> None:
    found = FoundWeb()
    citation = {
        "type": "url_citation",
        "title": "Two",
        "url": "https://two.test/formula",
    }
    found.read(
        AIMessageChunk(
            content=[
                search_block(["https://one.test/rate", "https://x.test/y"], "q"),
                {"type": "text", "annotations": [citation]},
            ]
        )
    )

    found.cite_links_in(REPLY_WITH_LINKS)

    assert [(p.url, p.cited) for p in found.pages()] == [
        ("https://two.test/formula", True),
        ("https://one.test/rate", True),
        ("https://x.test/y", False),
    ]


def test_a_search_with_no_pages_is_still_saved_with_its_query(tmp_path: Path) -> None:
    with TestClient(build_app(tmp_path / "data")) as client:
        wait_until_updated(client)
        events = send(client, "search the web, nopages please")
        reopened = client.get(f"/api/chats/{chat_id_of(events)}").json()

    message = reopened["messages"][-1]
    assert message["webSources"] is None
    assert message["webSearches"] == ["fake search 1"]


def test_an_answer_that_searched_but_cited_nothing_lists_what_it_read(
    tmp_path: Path,
) -> None:
    with TestClient(build_app(tmp_path / "data")) as client:
        wait_until_updated(client)
        events = send(client, "web rate, uncited")

    pages = done_message(events)["webSources"]
    assert len(pages) == 5
    assert not any(p["cited"] for p in pages)


def test_a_reply_that_did_not_search_has_no_web_searches(tmp_path: Path) -> None:
    with TestClient(build_app(tmp_path / "data")) as client:
        wait_until_updated(client)
        events = send(client, "Hello")

    assert done_message(events)["webSearches"] is None


def test_searching_then_calculating_keeps_both_panels_and_counts_the_link(
    tmp_path: Path,
) -> None:
    with TestClient(build_app(tmp_path / "data")) as client:
        wait_until_updated(client)
        events = send(client, "web rate then calc the interest")
        reopened = client.get(f"/api/chats/{chat_id_of(events)}").json()

    message = reopened["messages"][-1]
    assert [e["kind"] for e in events if e["type"] == "searching"] == [
        "web",
        "calculator",
    ]
    # The page came from a plain link: the fake sends no url_citation for it.
    assert (message["webSources"][0]["url"], message["webSources"][0]["cited"]) == (
        "https://www.example-bank.test/rate",
        True,
    )
    assert message["webSearches"] == ["fake search 1"]
    assert [run["tool"] for run in message["toolRuns"]] == ["calculate"]
    assert "£140.63" in message["content"]


def test_an_older_database_gets_the_web_searches_column(tmp_path: Path) -> None:
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
        INSERT INTO messages (chat_id, role, content, created_at, web_sources)
            VALUES ('c', 'assistant', 'An old web answer', '2026-01-01',
                '[{"title": "Old page", "site": "old.test", "url": "https://old.test/"}]');
        """
    )
    old.commit()
    old.close()
    database = Database(path)

    repository.create_tables(database)

    with database.connection() as connection:
        message = repository.get_chat(connection, "c").messages[0]
    # The answer was saved when only cited pages were recorded.
    assert message.web_searches is None
    assert message.web_sources is not None
    assert [(s.title, s.cited) for s in message.web_sources] == [("Old page", True)]


def test_the_instructions_say_to_search_first_and_link_every_page(
    tmp_path: Path,
) -> None:
    model = FakeChatModel(responder=lambda m: "Hello")
    with TestClient(build_app(tmp_path / "data", model)) as client:
        wait_until_updated(client)
        send(client, "Hi")

    answer_call = [m for m in model.received if "short title" not in text_of(m[0])][0]
    instructions = " ".join(text_of(answer_call[0]).split())
    assert "search the web for the figure first" in instructions
    assert "then use the calculator with the figure you found" in instructions
    assert "Never take such a figure from memory" in instructions
    assert (
        "Every answer that used the web must contain a `:::web` block" in instructions
    )
