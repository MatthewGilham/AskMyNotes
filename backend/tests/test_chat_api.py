"""Tests for the chat routes, as the browser calls them."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from helpers import build_app

from askmynotes.chats import repository
from askmynotes.database import Database


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def client(data_dir: Path) -> TestClient:
    return TestClient(build_app(data_dir))


def make_chat(data_dir: Path, title: str, *messages: str) -> str:
    """Save a chat straight into the database, as the chat feature will."""
    database = Database(data_dir / "app.db")
    with database.connection() as connection:
        chat = repository.create_chat(connection, title)
        for text in messages:
            repository.add_message(connection, chat.id, "user", text)
    return chat.id


def test_starting_the_app_creates_the_database_file(data_dir: Path) -> None:
    build_app(data_dir / "fresh")

    assert (data_dir / "fresh" / "app.db").exists()


def test_a_chat_is_listed_opened_renamed_and_pinned(
    client: TestClient, data_dir: Path
) -> None:
    chat_id = make_chat(data_dir, "Leases", "How is a lease measured?")

    listed = client.get("/api/chats").json()
    opened = client.get(f"/api/chats/{chat_id}").json()
    changed = client.patch(
        f"/api/chats/{chat_id}", json={"title": "  IFRS 16  ", "pinned": True}
    ).json()

    assert [chat["title"] for chat in listed] == ["Leases"]
    assert opened["messages"][0]["content"] == "How is a lease measured?"
    assert "lastUsedAt" in opened  # the frontend reads camelCase names
    assert changed["title"] == "IFRS 16"
    assert changed["pinned"] is True


def test_a_chat_cannot_be_renamed_to_nothing(
    client: TestClient, data_dir: Path
) -> None:
    chat_id = make_chat(data_dir, "Leases")

    response = client.patch(f"/api/chats/{chat_id}", json={"title": "   "})

    assert response.status_code == 422
    assert client.get(f"/api/chats/{chat_id}").json()["title"] == "Leases"


def test_a_deleted_chat_is_gone_and_missing_chats_give_404(
    client: TestClient, data_dir: Path
) -> None:
    chat_id = make_chat(data_dir, "Leases", "hello")

    assert client.delete(f"/api/chats/{chat_id}").status_code == 204

    assert client.get(f"/api/chats/{chat_id}").status_code == 404
    assert client.delete(f"/api/chats/{chat_id}").status_code == 404
    assert (
        client.patch(f"/api/chats/{chat_id}", json={"pinned": True}).status_code == 404
    )
    assert client.get("/api/chats").json() == []


def test_search_route_finds_chats_by_message_text(
    client: TestClient, data_dir: Path
) -> None:
    chat_id = make_chat(data_dir, "Revision", "Explain goodwill impairment")
    make_chat(data_dir, "Other", "Something else")

    hits = client.get("/api/chats/search", params={"q": "goodw"}).json()

    assert [hit["chatId"] for hit in hits] == [chat_id]
    assert client.get("/api/chats/search", params={"q": ""}).json() == []
