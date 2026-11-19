"""Tests for long chats: summarising the older part so the model isn't sent
everything, while the full chat is kept."""

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from helpers import build_app, send
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from askmynotes.chats import repository
from askmynotes.chats.history import IMAGE_TOKENS, estimate_tokens
from askmynotes.chats.models import Message
from askmynotes.database import Database
from askmynotes.fake_model import FakeChatModel, text_of

# 100 tokens is about 400 characters, so a few 150-character messages overflow it.
BUDGET = 100


def is_summary_request(messages: list[BaseMessage]) -> bool:
    return "running summary" in text_of(messages[0])


def is_title_request(messages: list[BaseMessage]) -> bool:
    return "short title" in text_of(messages[0])


class Recorder:
    """A fake model that records which calls were summaries and which were replies."""

    def __init__(self) -> None:
        self.summaries = 0
        self.model = FakeChatModel(responder=self.respond)

    def respond(self, messages: list[BaseMessage]) -> str:
        if is_summary_request(messages):
            self.summaries += 1
            return f"SUMMARY {self.summaries}"
        if is_title_request(messages):
            return "A title"
        return "An answer"

    def reply_calls(self) -> list[list[BaseMessage]]:
        return [
            call
            for call in self.model.received
            if not is_summary_request(call) and not is_title_request(call)
        ]


def start_long_chat(data_dir: Path, count: int) -> str:
    """Save a chat of `count` alternating messages, each about 150 characters."""
    with Database(data_dir / "app.db").connection() as connection:
        chat = repository.create_chat(connection, "A long chat")
        for number in range(count):
            role = "user" if number % 2 == 0 else "assistant"
            text = f"message {number} " + "x" * 140
            repository.add_message(connection, chat.id, role, text)
        return chat.id


def sent_texts(call: list[BaseMessage]) -> list[str]:
    """What the model was sent, after the agent's own instructions."""
    return [text_of(m) for m in call[1:]]


def test_long_chat_sends_summary_plus_recent_messages(tmp_path: Path) -> None:
    recorder = Recorder()
    client = TestClient(build_app(tmp_path, recorder.model, BUDGET))
    chat_id = start_long_chat(tmp_path, 8)

    events = send(client, "And the next question?", chat_id)

    assert events[-1]["type"] == "done"
    assert recorder.summaries == 1
    sent = recorder.reply_calls()[-1]
    assert isinstance(sent[1], SystemMessage)
    assert "SUMMARY 1" in text_of(sent[1])
    texts = sent_texts(sent)
    # The oldest messages are only in the summary now; the newest are sent whole.
    assert not any("message 0 " in t for t in texts)
    assert any("message 7 " in t for t in texts)
    assert texts[-1] == "And the next question?"
    assert isinstance(sent[-1], HumanMessage)


def test_the_full_chat_is_still_kept_and_shown(tmp_path: Path) -> None:
    recorder = Recorder()
    client = TestClient(build_app(tmp_path, recorder.model, BUDGET))
    chat_id = start_long_chat(tmp_path, 8)

    send(client, "And the next question?", chat_id)

    shown = client.get(f"/api/chats/{chat_id}").json()["messages"]
    assert len(shown) == 8 + 2
    assert shown[0]["content"].startswith("message 0 ")
    assert shown[-1]["content"] == "An answer"


def test_summary_is_reused_until_the_budget_is_reached_again(tmp_path: Path) -> None:
    recorder = Recorder()
    client = TestClient(build_app(tmp_path, recorder.model, BUDGET))
    chat_id = start_long_chat(tmp_path, 8)
    send(client, "First follow-up", chat_id)
    assert recorder.summaries == 1

    send(client, "ok", chat_id)

    assert recorder.summaries == 1  # still within budget, so no new summary
    reused = recorder.reply_calls()[-1]
    assert "SUMMARY 1" in text_of(reused[1])

    # Now the recent part grows past the budget again.
    for number in range(4):
        send(client, f"another long question {number} " + "y" * 140, chat_id)

    assert recorder.summaries >= 2
    requests = [c for c in recorder.model.received if is_summary_request(c)]
    # Each update starts from the previous summary, so nothing is lost.
    for number, request in enumerate(requests[1:], start=1):
        assert f"SUMMARY {number}" in text_of(request[1])


def test_a_chat_under_the_budget_is_sent_whole_with_no_summary(tmp_path: Path) -> None:
    recorder = Recorder()
    client = TestClient(build_app(tmp_path, recorder.model, BUDGET))
    chat_id = start_long_chat(tmp_path, 2)

    send(client, "Short follow-up", chat_id)

    assert recorder.summaries == 0
    texts = sent_texts(recorder.reply_calls()[-1])
    assert len(texts) == 3
    assert not any("Summary" in t for t in texts)


def test_a_single_huge_message_is_sent_even_though_it_is_over_budget(
    tmp_path: Path,
) -> None:
    recorder = Recorder()
    client = TestClient(build_app(tmp_path, recorder.model, BUDGET))

    events = send(client, "z" * 2000)

    assert events[-1]["type"] == "done"
    assert recorder.summaries == 0  # nothing older to fold into a summary


def test_a_failed_summary_is_reported_and_the_message_is_kept(tmp_path: Path) -> None:
    def responder(messages: list[BaseMessage]) -> str:
        if is_summary_request(messages):
            raise RuntimeError("summary failed")
        return "An answer"

    client = TestClient(build_app(tmp_path, FakeChatModel(responder=responder), BUDGET))
    chat_id = start_long_chat(tmp_path, 8)

    events = send(client, "Please carry on", chat_id)

    assert events[-1]["type"] == "error"
    shown = client.get(f"/api/chats/{chat_id}").json()["messages"]
    assert shown[8]["content"] == "Please carry on"
    assert shown[9]["status"] == "error"
    with Database(tmp_path / "app.db").connection() as connection:
        assert repository.get_summary(connection, chat_id) == (None, 0)


def test_images_count_towards_the_budget() -> None:
    message = Message(
        id=1,
        role="user",
        content="",
        status="complete",
        error=None,
        sources=None,
        images=["/api/uploads/a/b.png", "/api/uploads/a/c.png"],
        created_at="2026-10-27T12:00:00+00:00",  # type: ignore[arg-type]
    )

    assert estimate_tokens(message) == 2 * IMAGE_TOKENS


def test_summaries_leave_images_out_but_note_that_they_existed(tmp_path: Path) -> None:
    recorder = Recorder()
    client = TestClient(build_app(tmp_path, recorder.model, BUDGET))
    with Database(tmp_path / "app.db").connection() as connection:
        chat = repository.create_chat(connection, "With image")
        message_id = repository.add_message(connection, chat.id, "user", "Look at this")
        (tmp_path / "uploads" / chat.id).mkdir(parents=True)
        (tmp_path / "uploads" / chat.id / "a.png").write_bytes(b"png")
        repository.add_images(connection, message_id, [f"{chat.id}/a.png"])
        for number in range(6):
            role = "assistant" if number % 2 == 0 else "user"
            repository.add_message(connection, chat.id, role, "w" * 150)

    send(client, "Next", chat.id)

    request = next(c for c in recorder.model.received if is_summary_request(c))
    assert "[attached image]" in text_of(request[1])
    assert not isinstance(request[1].content, list)  # no image data was sent


def test_an_older_database_gains_the_summary_columns(tmp_path: Path) -> None:
    path = tmp_path / "app.db"
    old = sqlite3.connect(path)
    old.executescript(
        "CREATE TABLE chats (id TEXT PRIMARY KEY, title TEXT NOT NULL, "
        "pinned INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, "
        "last_used_at TEXT NOT NULL);"
        "INSERT INTO chats VALUES ('old', 'Old chat', 0, 'x', 'x');"
    )
    old.commit()
    old.close()

    repository.create_tables(Database(path))

    with Database(path).connection() as connection:
        assert repository.get_summary(connection, "old") == (None, 0)
