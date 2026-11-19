"""Tests for chat storage: saving, listing, searching and deleting chats."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from askmynotes.chats import repository
from askmynotes.chats.models import Source
from askmynotes.database import Database

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)


@pytest.fixture
def database(tmp_path: Path) -> Database:
    database = Database(tmp_path / "app.db")
    repository.create_tables(database)
    return database


def test_deleting_a_chat_deletes_its_messages_and_images(
    database: Database, tmp_path: Path
) -> None:
    uploads = tmp_path / "uploads"
    with database.connection() as connection:
        chat = repository.create_chat(connection, "Leases")
        message_id = repository.add_message(connection, chat.id, "user", "see image")
        repository.add_message(connection, chat.id, "assistant", "I see it")
        image = uploads / chat.id / "screenshot.png"
        image.parent.mkdir(parents=True)
        image.write_bytes(b"png")
        connection.execute(
            "INSERT INTO message_images (message_id, path) VALUES (?, ?)",
            (message_id, str(image)),
        )

    with database.connection() as connection:
        repository.delete_chat(connection, chat.id, uploads)

    with database.connection() as connection:
        for table in ("chats", "messages", "message_images", "chat_search"):
            assert (
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
            )
    assert not image.exists()


def test_deleting_a_chat_leaves_other_chats_alone(
    database: Database, tmp_path: Path
) -> None:
    with database.connection() as connection:
        doomed = repository.create_chat(connection, "Doomed")
        kept = repository.create_chat(connection, "Kept")
        repository.add_message(connection, kept.id, "user", "still here")

        repository.delete_chat(connection, doomed.id, tmp_path / "uploads")

        assert [chat.id for chat in repository.list_chats(connection)] == [kept.id]
        assert len(repository.get_chat(connection, kept.id).messages) == 1


def test_search_finds_chats_by_title_and_by_message_text(database: Database) -> None:
    with database.connection() as connection:
        by_title = repository.create_chat(connection, "Depreciation methods")
        by_message = repository.create_chat(connection, "Revision")
        repository.add_message(
            connection,
            by_message.id,
            "assistant",
            "Goodwill is impaired, not amortised.",
        )
        repository.create_chat(connection, "Unrelated recipe")

        title_hits = repository.search_chats(connection, "depreciation")
        message_hits = repository.search_chats(connection, "goodwill")

    assert [hit.chat_id for hit in title_hits] == [by_title.id]
    assert [hit.chat_id for hit in message_hits] == [by_message.id]
    assert "Goodwill" in message_hits[0].snippet
    assert message_hits[0].title == "Revision"


def test_search_matches_word_prefixes(database: Database) -> None:
    with database.connection() as connection:
        chat = repository.create_chat(connection, "Depreciation methods")

        hits = repository.search_chats(connection, "depre")

    assert [hit.chat_id for hit in hits] == [chat.id]


def test_search_lists_each_chat_once_and_needs_every_word(database: Database) -> None:
    with database.connection() as connection:
        chat = repository.create_chat(connection, "Leases")
        repository.add_message(connection, chat.id, "user", "lease liability")
        repository.add_message(
            connection, chat.id, "assistant", "lease liability is..."
        )

        both_words = repository.search_chats(connection, "lease liability")
        missing_word = repository.search_chats(connection, "lease banana")

    assert [hit.chat_id for hit in both_words] == [chat.id]
    assert missing_word == []


def test_search_treats_punctuation_as_plain_text(database: Database) -> None:
    with database.connection() as connection:
        repository.create_chat(connection, "Leases")

        assert repository.search_chats(connection, '"') == []
        assert [h.title for h in repository.search_chats(connection, "lease*(")] == [
            "Leases"
        ]
        # "OR" is just a word here, not search syntax, so nothing contains it.
        assert repository.search_chats(connection, "lease OR") == []


def test_renaming_a_chat_updates_search(database: Database) -> None:
    with database.connection() as connection:
        chat = repository.create_chat(connection, "Old title")

        repository.rename_chat(connection, chat.id, "Brand new title")

        assert repository.search_chats(connection, "old") == []
        assert [h.chat_id for h in repository.search_chats(connection, "brand")] == [
            chat.id
        ]


def test_chats_are_listed_by_last_used_with_pinned_first(database: Database) -> None:
    with database.connection() as connection:
        oldest = repository.create_chat(connection, "Oldest", at=NOW)
        pinned = repository.create_chat(connection, "Pinned", at=NOW)
        newest = repository.create_chat(connection, "Newest", at=NOW)
        repository.add_message(
            connection, oldest.id, "user", "hi", at=NOW + timedelta(minutes=1)
        )
        repository.add_message(
            connection, newest.id, "user", "hi", at=NOW + timedelta(minutes=2)
        )
        repository.set_pinned(connection, pinned.id, True)

        titles = [chat.title for chat in repository.list_chats(connection)]

    assert titles == ["Pinned", "Newest", "Oldest"]


def test_unpinning_returns_a_chat_to_its_place_by_date(database: Database) -> None:
    with database.connection() as connection:
        old = repository.create_chat(connection, "Old", at=NOW)
        new = repository.create_chat(connection, "New", at=NOW + timedelta(hours=1))
        repository.set_pinned(connection, old.id, True)
        repository.set_pinned(connection, old.id, False)

        ids = [chat.id for chat in repository.list_chats(connection)]

    assert ids == [new.id, old.id]


def test_messages_come_back_in_order_with_status_error_and_sources(
    database: Database,
) -> None:
    source = Source(
        file_name="Lecture 4.pptx", module="AFA", location="slide", number=6
    )
    with database.connection() as connection:
        chat = repository.create_chat(connection, "EPS")
        repository.add_message(connection, chat.id, "user", "What is EPS?")
        repository.add_message(
            connection, chat.id, "assistant", "Earnings per share.", sources=[source]
        )
        repository.add_message(connection, chat.id, "user", "And diluted?")
        repository.add_message(
            connection, chat.id, "assistant", "", status="error", error="No internet"
        )

        messages = repository.get_chat(connection, chat.id).messages

    assert [m.content for m in messages] == [
        "What is EPS?",
        "Earnings per share.",
        "And diluted?",
        "",
    ]
    assert messages[1].sources == [source]
    assert messages[3].status == "error"
    assert messages[3].error == "No internet"


def test_chats_saved_before_a_restart_are_there_after(tmp_path: Path) -> None:
    first_run = Database(tmp_path / "app.db")
    repository.create_tables(first_run)
    with first_run.connection() as connection:
        chat = repository.create_chat(connection, "Survivor")
        repository.add_message(connection, chat.id, "user", "Still here?")

    second_run = Database(tmp_path / "app.db")
    repository.create_tables(second_run)  # runs again on every start
    with second_run.connection() as connection:
        reopened = repository.get_chat(connection, chat.id)
        search = repository.search_chats(connection, "survivor")

    assert reopened.title == "Survivor"
    assert [m.content for m in reopened.messages] == ["Still here?"]
    assert [hit.chat_id for hit in search] == [chat.id]


def test_a_failed_unit_of_work_is_rolled_back(database: Database) -> None:
    with pytest.raises(RuntimeError):
        with database.connection() as connection:
            repository.create_chat(connection, "Never saved")
            raise RuntimeError("something went wrong")

    with database.connection() as connection:
        assert repository.list_chats(connection) == []


def test_a_message_cannot_be_added_to_a_missing_chat(database: Database) -> None:
    with database.connection() as connection:
        with pytest.raises(repository.ChatNotFound):
            repository.add_message(connection, "nope", "user", "hello")


def test_search_returns_message_target_and_title_fallback(database: Database) -> None:
    with database.connection() as connection:
        chat = repository.create_chat(connection, "titleneedle")
        first = repository.add_message(connection, chat.id, "user", "messageneedle")
        repository.add_message(connection, chat.id, "assistant", "messageneedle")
        hits = repository.search_chats(connection, "messageneedle")
        assert len(hits) == 1
        assert hits[0].message_id == first
        assert repository.search_chats(connection, "titleneedle")[0].message_id is None
