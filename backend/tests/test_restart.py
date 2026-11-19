"""The spec's promise that restarting the app keeps every chat exactly as it was.

One app makes chats in every state a chat can be in; a second app, started on
the same data folder as after a restart, must show them identically.
"""

from pathlib import Path

from fastapi.testclient import TestClient
from helpers import (
    build_app,
    make_pdf,
    read_events,
    send,
    send_with_images,
    upload,
    wait_until_updated,
)

from askmynotes.chats import repository
from askmynotes.database import Database
from askmynotes.settings import Module


def everything_shown(client: TestClient) -> dict:
    """What the browser can see: the sidebar list and every chat in full."""
    chats = client.get("/api/chats").json()
    return {
        "sidebar": chats,
        "chats": {c["id"]: client.get(f"/api/chats/{c['id']}").json() for c in chats},
    }


def test_restarting_keeps_every_chat_exactly_as_it_was(tmp_path: Path) -> None:
    notes = tmp_path / "notes"
    notes.mkdir()
    make_pdf(notes / "Lecture 1.pdf", ["Depreciation spreads the cost of an asset."])
    module = Module(name="Testing Module", short_name="TM", folder=notes)
    data_dir = tmp_path / "data"

    with TestClient(build_app(data_dir, modules=[module])) as first_run:
        wait_until_updated(first_run)
        send(first_run, "Hello there")
        image_chat = read_events(
            send_with_images(first_run, "What is this?", [upload()]).text
        )[0]["chat"]["id"]
        notes_chat = send(first_run, "What do my notes say about depreciation?")
        error_chat = send(first_run, "please fail")
        stopped_chat = send(first_run, "Count to ten")[0]["chat"]["id"]
        first_run.patch(
            f"/api/chats/{image_chat}", json={"title": "Renamed", "pinned": True}
        )
        # A stopped reply is made by the browser disconnecting, which the tests
        # in test_conversation.py cover; here it only needs to exist.
        with Database(data_dir / "app.db").connection() as connection:
            repository.add_message(connection, stopped_chat, "user", "Go on")
            repository.add_message(
                connection, stopped_chat, "assistant", "One, two", status="stopped"
            )
        before = everything_shown(first_run)
        image_url = before["chats"][image_chat]["messages"][0]["images"][0]
        image_bytes = first_run.get(image_url).content

    # Every state is really there before the restart.
    assert notes_chat[-1]["message"]["sources"]
    assert error_chat[-1]["type"] == "error"
    assert before["sidebar"][0]["pinned"] is True

    with TestClient(build_app(data_dir, modules=[module])) as second_run:
        wait_until_updated(second_run)
        after = everything_shown(second_run)
        image_after = second_run.get(image_url).content

    assert after == before
    assert image_after == image_bytes
