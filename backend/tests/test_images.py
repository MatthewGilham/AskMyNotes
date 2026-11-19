"""Tests for images attached to messages."""

from pathlib import Path

from fastapi.testclient import TestClient
from helpers import PNG, build_app, read_events, send_with_images, upload
from langchain_core.messages import BaseMessage, HumanMessage

from askmynotes.chats import repository
from askmynotes.database import Database
from askmynotes.fake_model import FakeChatModel, count_images, text_of


def saved_chat_count(data_dir: Path) -> int:
    with Database(data_dir / "app.db").connection() as connection:
        return len(repository.list_chats(connection))


def test_image_is_saved_with_its_message(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path))

    response = send_with_images(client, "What is this?", [upload()])

    events = read_events(response.text)
    chat_id = events[0]["chat"]["id"]
    [url] = events[0]["userMessage"]["images"]
    assert url.startswith(f"/api/uploads/{chat_id}/")
    # The file is on disk, recorded in the database, and shown from its address.
    saved = list((tmp_path / "uploads" / chat_id).iterdir())
    assert [file.read_bytes() for file in saved] == [PNG]
    assert client.get(url).content == PNG
    reopened = client.get(f"/api/chats/{chat_id}").json()
    assert reopened["messages"][0]["images"] == [url]
    assert reopened["messages"][1]["images"] == []
    assert "I can see 1 image(s)." in "".join(
        e["text"] for e in events if e["type"] == "token"
    )


def test_the_model_is_sent_the_image_as_well_as_the_text(tmp_path: Path) -> None:
    model = FakeChatModel()
    client = TestClient(build_app(tmp_path, model))

    send_with_images(client, "What is this?", [upload()])

    sent = next(m for m in model.received if "short title" not in text_of(m[0]))
    human = sent[-1]
    assert isinstance(human, HumanMessage)
    assert text_of(human) == "What is this?"
    assert count_images(human) == 1
    assert human.content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_an_image_alone_is_a_valid_message_and_gets_a_title(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path))

    response = send_with_images(client, "", [upload()])

    events = read_events(response.text)
    assert events[-1]["type"] == "done"
    assert events[0]["chat"]["title"] == "Image"


def test_images_from_earlier_messages_are_sent_again(tmp_path: Path) -> None:
    model = FakeChatModel()
    client = TestClient(build_app(tmp_path, model))
    first = read_events(send_with_images(client, "Look at this", [upload()]).text)
    chat_id = first[0]["chat"]["id"]

    send_with_images(client, "And now?", [], chat_id)

    last_call: list[BaseMessage] = model.received[-1]
    humans = [m for m in last_call if isinstance(m, HumanMessage)]
    assert [count_images(m) for m in humans] == [1, 0]


def test_unsupported_image_type_is_refused(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path))

    response = send_with_images(client, "Hi", [upload("photo.bmp", PNG, "image/bmp")])

    assert response.status_code == 422
    assert saved_chat_count(tmp_path) == 0


def test_too_many_images_are_refused_and_nothing_is_saved(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path))  # the test limit is 2 images

    response = send_with_images(client, "Hi", [upload(), upload(), upload()])

    assert response.status_code == 422
    assert "up to 2 images" in response.json()["detail"]
    assert saved_chat_count(tmp_path) == 0
    assert list((tmp_path / "uploads").glob("*/*")) == []


def test_an_image_over_the_size_limit_is_refused(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path))  # the test limit is 1 MB
    too_big = b"\0" * (1024 * 1024 + 1)

    response = send_with_images(client, "Hi", [upload("huge.png", too_big)])

    assert response.status_code == 422
    assert "huge.png is larger than 1 MB" in response.json()["detail"]
    assert saved_chat_count(tmp_path) == 0


def test_an_image_that_is_not_valid_base64_is_refused(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path))
    broken = {"name": "broken.png", "mediaType": "image/png", "data": "!!not base64!!"}

    response = send_with_images(client, "Hi", [broken])

    assert response.status_code == 422
    assert "broken.png isn't a valid image" in response.json()["detail"]


def test_a_message_with_no_text_and_no_image_is_refused(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path))

    response = send_with_images(client, "  ", [])

    assert response.status_code == 422
    assert saved_chat_count(tmp_path) == 0


def test_deleting_a_chat_through_the_api_deletes_its_image_files(
    tmp_path: Path,
) -> None:
    client = TestClient(build_app(tmp_path))
    events = read_events(send_with_images(client, "Look", [upload()]).text)
    chat_id = events[0]["chat"]["id"]
    [url] = events[0]["userMessage"]["images"]

    assert client.delete(f"/api/chats/{chat_id}").status_code == 204

    assert not (tmp_path / "uploads" / chat_id).exists()
    assert client.get(url).status_code == 404
