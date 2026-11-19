"""The edit endpoint replaces only a guarded latest turn."""

import asyncio
import time
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from helpers import (
    BIG_BUDGET,
    PNG,
    TEST_CONFIG,
    build_app,
    document_reader,
    lost_connection,
    make_pdf,
    read_events,
    send,
    upload,
    usage_ledger,
    wait_until_updated,
)
from langchain_core.messages import BaseMessage

from askmynotes.agent.agent import Agent
from askmynotes.chats import repository
from askmynotes.chats.conversation import Conversation
from askmynotes.chats.history import ModelHistory
from askmynotes.chats.models import EditRequest, SendRequest
from askmynotes.database import Database
from askmynotes.fake_model import (
    FakeChatModel,
    FakeEmbeddings,
    last_human_text,
    text_of,
)
from askmynotes.notes.search import NotesSearch
from askmynotes.notes.store import NotesStore
from askmynotes.settings import Module


def test_edit_latest_question_preserves_quote_and_never_sends_old_answer(
    tmp_path: Path,
) -> None:
    model = FakeChatModel()
    client = TestClient(build_app(tmp_path, model))
    with client:
        wait_until_updated(client)
        chat_id = send(client, "Earlier question")[0]["chat"]["id"]
        send(client, "Original wording", chat_id)
        with Database(tmp_path / "app.db").connection() as connection:
            messages = repository.get_chat(connection, chat_id).messages
            _, earlier_answer, question, answer = messages
            original_last_used = repository.get_chat_summary(
                connection, chat_id
            ).last_used_at
            connection.execute(
                "UPDATE messages SET quoted_context = ? WHERE id = ?",
                ('{"source_message_id":2,"excerpt":"Earlier excerpt"}', question.id),
            )
            connection.execute(
                "UPDATE chats SET title = 'Pinned title', pinned = 1, summary = ?, "
                "summarised_up_to = ? WHERE id = ?",
                ("summary of earlier turn", earlier_answer.id, chat_id),
            )
        prior_model_calls = len(model.received)

        response = client.post(
            f"/api/chats/{chat_id}/messages/{question.id}/edit",
            json={
                "text": "Corrected wording",
                "expectedLatestMessageId": question.id,
                "expectedOriginalText": "Original wording",
            },
        )
        assert response.status_code == 200, response.text
        result = read_events(response.text)
        assert result[0]["type"] == "accepted"
        assert result[0]["userMessage"]["content"] == "Corrected wording"
        assert result[-1]["type"] == "done"

        with Database(tmp_path / "app.db").connection() as connection:
            chat = repository.get_chat(connection, chat_id)
            summary, boundary = repository.get_summary(connection, chat_id)
            assert (chat.title, chat.pinned) == ("Pinned title", True)
            assert chat.last_used_at > original_last_used
            assert [message.id for message in chat.messages] == [
                messages[0].id,
                earlier_answer.id,
                question.id,
                chat.messages[-1].id,
            ]
            assert chat.messages[2].content == "Corrected wording"
            assert chat.messages[2].quoted_context.excerpt == "Earlier excerpt"
            assert chat.messages[2].quoted_context.source_message_id == 2
            assert answer.id not in [message.id for message in chat.messages]
            assert summary == "summary of earlier turn"
            assert boundary == earlier_answer.id
            assert repository.search_chats(connection, "Original wording") == []
            assert repository.search_chats(connection, "Corrected wording")

        sent_to_model = "\n".join(
            text_of(message)
            for call in model.received[prior_model_calls:]
            for message in call
        )
        assert "Corrected wording" in sent_to_model
        assert "You said: Original wording" not in sent_to_model
        assert "summary of earlier turn" in sent_to_model


def test_stale_and_invalid_edits_leave_the_turn_untouched(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path, FakeChatModel()))
    with client:
        wait_until_updated(client)
        events = send(client, "Keep this question")
        chat_id = events[0]["chat"]["id"]
        with Database(tmp_path / "app.db").connection() as connection:
            question_id = repository.get_chat(connection, chat_id).messages[0].id

        stale = client.post(
            f"/api/chats/{chat_id}/messages/{question_id}/edit",
            json={
                "text": "Stale correction",
                "expectedLatestMessageId": question_id,
                "expectedOriginalText": "Different original",
            },
        )
        empty = client.post(
            f"/api/chats/{chat_id}/messages/{question_id}/edit",
            json={
                "text": "   ",
                "expectedLatestMessageId": question_id,
                "expectedOriginalText": "Keep this question",
            },
        )
        assert stale.status_code == 409
        assert "reload" in stale.json()["detail"].lower()
        assert empty.status_code == 422
        with Database(tmp_path / "app.db").connection() as connection:
            chat = repository.get_chat(connection, chat_id)
        assert [message.content for message in chat.messages] == [
            "Keep this question",
            chat.messages[1].content,
        ]


def test_edit_clears_a_summary_that_covers_the_replaced_answer(tmp_path: Path) -> None:
    model = FakeChatModel()
    client = TestClient(build_app(tmp_path, model))
    with client:
        wait_until_updated(client)
        chat_id = send(client, "Original wording")[0]["chat"]["id"]
        with Database(tmp_path / "app.db").connection() as connection:
            question, answer = repository.get_chat(connection, chat_id).messages
            connection.execute(
                "UPDATE chats SET summary = ?, summarised_up_to = ? WHERE id = ?",
                ("obsolete summary sentinel", answer.id, chat_id),
            )
        previous_calls = len(model.received)
        response = client.post(
            f"/api/chats/{chat_id}/messages/{question.id}/edit",
            json={
                "text": "Corrected wording",
                "expectedLatestMessageId": question.id,
                "expectedOriginalText": question.content,
            },
        )
        assert read_events(response.text)[-1]["type"] == "done"
        with Database(tmp_path / "app.db").connection() as connection:
            summary, boundary = repository.get_summary(connection, chat_id)
        assert summary is None and boundary == 0
        model_input = "\n".join(
            text_of(message)
            for call in model.received[previous_calls:]
            for message in call
        )
        assert "Corrected wording" in model_input
        assert "obsolete summary sentinel" not in model_input
        assert answer.content not in model_input
        reopened = TestClient(build_app(tmp_path, FakeChatModel())).get(
            f"/api/chats/{chat_id}"
        )
        assert reopened.status_code == 200
        assert reopened.json()["messages"][0]["content"] == "Corrected wording"


def test_empty_edit_is_allowed_with_an_existing_image(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path, FakeChatModel()))
    with client:
        wait_until_updated(client)
        started = client.post(
            "/api/chats/send",
            json={"text": "Question with image", "images": [upload()]},
        )
        events = read_events(started.text)
        chat_id = events[0]["chat"]["id"]
        question = events[0]["userMessage"]
        image_path = (
            tmp_path / "uploads" / question["images"][0].removeprefix("/api/uploads/")
        )
        original_image_bytes = image_path.read_bytes()
        response = client.post(
            f"/api/chats/{chat_id}/messages/{question['id']}/edit",
            json={
                "text": "",
                "expectedLatestMessageId": question["id"],
                "expectedOriginalText": "Question with image",
            },
        )
        assert response.status_code == 200, response.text
        saved = read_events(response.text)[0]["userMessage"]
        assert saved["content"] == ""
        assert saved["images"] == question["images"]
        assert original_image_bytes == PNG
        assert image_path.read_bytes() == original_image_bytes


def test_only_latest_user_target_in_the_same_chat_can_be_edited(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path, FakeChatModel()))
    with client:
        wait_until_updated(client)
        first_chat = send(client, "First turn")[0]["chat"]["id"]
        send(client, "Second turn", first_chat)
        second_chat = send(client, "Other chat")[0]["chat"]["id"]
        with Database(tmp_path / "app.db").connection() as connection:
            first_messages = repository.get_chat(connection, first_chat).messages
            other_question_id = (
                repository.get_chat(connection, second_chat).messages[0].id
            )

        targets = [
            first_messages[0],
            first_messages[1],
            other_question_id,
            max(message.id for message in first_messages) + 1000,
        ]
        for target in targets:
            message_id = target.id if hasattr(target, "id") else target
            response = client.post(
                f"/api/chats/{first_chat}/messages/{message_id}/edit",
                json={
                    "text": "Must be refused",
                    "expectedLatestMessageId": message_id,
                    "expectedOriginalText": "First turn",
                },
            )
            assert response.status_code == 409
        with Database(tmp_path / "app.db").connection() as connection:
            current = repository.get_chat(connection, first_chat).messages
        assert [message.content for message in current] == [
            message.content for message in first_messages
        ]


def test_generation_failure_after_acceptance_keeps_correction_for_retry(
    tmp_path: Path,
) -> None:
    failed_once = False

    def responder(messages: list[BaseMessage]) -> str:
        nonlocal failed_once
        if "short title" in text_of(messages[0]):
            return "Stable title"
        if last_human_text(messages) == "Corrected fail once" and not failed_once:
            failed_once = True
            raise lost_connection()
        return "Replacement answer"

    client = TestClient(build_app(tmp_path, FakeChatModel(responder=responder)))
    with client:
        wait_until_updated(client)
        chat_id = send(client, "Original question")[0]["chat"]["id"]
        with Database(tmp_path / "app.db").connection() as connection:
            question = repository.get_chat(connection, chat_id).messages[0]
        failed = client.post(
            f"/api/chats/{chat_id}/messages/{question.id}/edit",
            json={
                "text": "Corrected fail once",
                "expectedLatestMessageId": question.id,
                "expectedOriginalText": question.content,
            },
        )
        failure_events = read_events(failed.text)
        assert failure_events[0]["type"] == "accepted"
        assert failure_events[-1]["type"] == "error"
        retry = client.post(f"/api/chats/{chat_id}/regenerate")
        assert read_events(retry.text)[-1]["type"] == "done"
        with Database(tmp_path / "app.db").connection() as connection:
            messages = repository.get_chat(connection, chat_id).messages
        assert [message.content for message in messages] == [
            "Corrected fail once",
            "Replacement answer",
        ]


def test_edit_replaces_an_error_reply_and_its_error_details(tmp_path: Path) -> None:
    failed_original = False

    def responder(messages: list[BaseMessage]) -> str:
        nonlocal failed_original
        if "short title" in text_of(messages[0]):
            return "Stable title"
        if last_human_text(messages) == "Original failure" and not failed_original:
            failed_original = True
            raise lost_connection()
        return "Answer to correction"

    client = TestClient(build_app(tmp_path, FakeChatModel(responder=responder)))
    with client:
        wait_until_updated(client)
        chat_id = send(client, "Original failure")[0]["chat"]["id"]
        with Database(tmp_path / "app.db").connection() as connection:
            question = repository.get_chat(connection, chat_id).messages[0]
        response = client.post(
            f"/api/chats/{chat_id}/messages/{question.id}/edit",
            json={
                "text": "Corrected question",
                "expectedLatestMessageId": question.id,
                "expectedOriginalText": question.content,
            },
        )
        assert read_events(response.text)[-1]["type"] == "done"
        with Database(tmp_path / "app.db").connection() as connection:
            messages = repository.get_chat(connection, chat_id).messages
        assert [message.id for message in messages] == [question.id, messages[-1].id]
        assert messages[0].content == "Corrected question"
        assert messages[1].content == "Answer to correction"
        assert messages[1].status == "complete"
        assert messages[1].error is None
        assert messages[1].sources is None


def test_chat_reservation_rejects_overlap_and_releases_after_stream(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "app.db")
    repository.create_tables(database)
    model = FakeChatModel(responder=lambda messages: "Replacement answer")
    ledger = usage_ledger(database)
    history = ModelHistory(database, model, tmp_path / "uploads", BIG_BUDGET, ledger)
    agent = Agent(
        model,
        NotesSearch(NotesStore(tmp_path / "chroma", FakeEmbeddings(), "fake"), [], 8),
    )
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

    async def drain(prepared):
        return [event async for event in conversation.stream(prepared)]

    first_events = asyncio.run(
        drain(conversation.start_message(SendRequest(text="Original question")))
    )
    chat_id = first_events[0].chat.id
    question_id = first_events[0].user_message.id
    edit = conversation.start_edit(
        chat_id,
        question_id,
        EditRequest(
            text="Corrected question",
            expected_latest_message_id=question_id,
            expected_original_text="Original question",
        ),
    )
    with pytest.raises(HTTPException) as conflict:
        conversation.start_regeneration(chat_id)
    assert conflict.value.status_code == 409

    release_other_chat = conversation.reserve("different-chat")
    release_other_chat()
    assert asyncio.run(drain(edit))[-1].type == "done"

    retry = conversation.start_regeneration(chat_id)
    retry.release()


def test_disconnect_after_acceptance_before_first_token_saves_stopped_and_unlocks(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "app.db")
    repository.create_tables(database)
    model = FakeChatModel(responder=lambda messages: "Replacement answer")
    ledger = usage_ledger(database)
    history = ModelHistory(database, model, tmp_path / "uploads", BIG_BUDGET, ledger)
    agent = Agent(
        model,
        NotesSearch(NotesStore(tmp_path / "chroma", FakeEmbeddings(), "fake"), [], 8),
    )
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

    async def drain(prepared):
        return [event async for event in conversation.stream(prepared)]

    first_events = asyncio.run(
        drain(conversation.start_message(SendRequest(text="Original question")))
    )
    chat_id = first_events[0].chat.id
    question_id = first_events[0].user_message.id
    prepared = conversation.start_edit(
        chat_id,
        question_id,
        EditRequest(
            text="Corrected before disconnect",
            expected_latest_message_id=question_id,
            expected_original_text="Original question",
        ),
    )

    async def disconnect_before_tokens() -> None:
        stream = conversation.stream(prepared)
        event = await anext(stream)
        assert event.type == "accepted"
        await stream.aclose()

    asyncio.run(disconnect_before_tokens())
    with database.connection() as connection:
        messages = repository.get_chat(connection, chat_id).messages
    assert messages[-2].content == "Corrected before disconnect"
    assert messages[-1].content == ""
    assert messages[-1].status == "stopped"
    release = conversation.reserve(chat_id)
    release()


def test_edit_is_refused_without_mutation_during_notes_sync(tmp_path: Path) -> None:
    notes_folder = tmp_path / "notes"
    notes_folder.mkdir()
    make_pdf(notes_folder / "made-up.pdf", ["Made-up lecture content"])
    module = Module(name="Testing Module", short_name="TM", folder=notes_folder)

    class SlowEmbeddings(FakeEmbeddings):
        """Keep startup sync active long enough to test the API guard."""

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            time.sleep(1.5)
            return super().embed_documents(texts)

    data_dir = tmp_path / "data"
    database = Database(data_dir / "app.db")
    repository.create_tables(database)
    with database.connection() as connection:
        chat = repository.create_chat(connection, "Existing chat")
        question_id = repository.add_message(connection, chat.id, "user", "Original")
        repository.add_message(connection, chat.id, "assistant", "Old answer")

    client = TestClient(
        build_app(
            data_dir,
            FakeChatModel(),
            modules=[module],
            embeddings=SlowEmbeddings(),
        )
    )
    with client:
        assert client.get("/api/notes/status").json()["updating"] is True
        refused = client.post(
            f"/api/chats/{chat.id}/messages/{question_id}/edit",
            json={
                "text": "Must stay unsaved",
                "expectedLatestMessageId": question_id,
                "expectedOriginalText": "Original",
            },
        )
        assert refused.status_code == 409
        assert "notes are being updated" in refused.json()["detail"]
        wait_until_updated(client)

    with database.connection() as connection:
        messages = repository.get_chat(connection, chat.id).messages
    assert [message.content for message in messages] == ["Original", "Old answer"]
