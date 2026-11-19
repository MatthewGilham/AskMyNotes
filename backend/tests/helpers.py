"""Shared helpers for the backend tests."""

import base64
import json
import time
from pathlib import Path

import httpx
import openai
import pymupdf
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel

from askmynotes.app import create_app
from askmynotes.chats.documents import DocumentReader
from askmynotes.client_config import client_config_from
from askmynotes.database import Database
from askmynotes.fake_model import FakeChatModel, FakeEmbeddings, FakeSandbox
from askmynotes.notes.libreoffice import default_soffice_path
from askmynotes.settings import AppSettings, Module, Prices, WebSearch
from askmynotes.usage.ledger import UsageLedger

# Big enough that ordinary tests never reach it.
BIG_BUDGET = 1_000_000

# Round numbers, so a test can work out a cost by hand.
TEST_PRICES = Prices(
    chat_input=1.0,
    chat_cached_input=0.1,
    chat_output=2.0,
    embedding_input=0.5,
    web_search_call=0.5,
    python_session=0.25,
)

TEST_WEB_SEARCH = WebSearch(country="GB", timezone="Europe/London")

TEST_SETTINGS = AppSettings(
    user_name="Matt",
    port=8000,
    libreoffice_path=default_soffice_path(),
    max_images_per_message=2,
    max_image_size_mb=1,
    max_documents_per_message=2,
    max_document_size_mb=1,
    max_document_tokens=1000,
    max_generated_files_per_reply=2,
    max_generated_file_mb=1,
    context_budget_tokens=BIG_BUDGET,
    max_chunk_characters=3000,
    notes_search_results=8,
    example_prompts=["Hello"],
    prices=TEST_PRICES,
    web_search=TEST_WEB_SEARCH,
    modules=[],
)
TEST_CONFIG = client_config_from(TEST_SETTINGS)


def document_reader(data_dir: Path) -> DocumentReader:
    """A reader with the test settings' document limits."""
    return DocumentReader(
        TEST_SETTINGS.max_documents_per_message,
        TEST_SETTINGS.max_document_size_mb,
        TEST_SETTINGS.max_document_tokens,
        TEST_SETTINGS.libreoffice_path,
        data_dir,
    )


def usage_ledger(database: Database) -> UsageLedger:
    """A ledger with the test prices, its tables created."""
    ledger = UsageLedger(database, TEST_PRICES)
    ledger.create_tables()
    return ledger


def build_app(
    data_dir: Path,
    model: BaseChatModel | None = None,
    context_budget_tokens: int = BIG_BUDGET,
    modules: list[Module] | None = None,
    embeddings: Embeddings | None = None,
    frontend_dist: Path | None = None,
    sandbox: FakeSandbox | None = None,
) -> FastAPI:
    """The real app, with fake models unless a test supplies its own.

    The notes sync only starts when the app does, which happens when a test
    uses the client in a `with` block.
    """
    settings = TEST_SETTINGS.model_copy(
        update={
            "context_budget_tokens": context_budget_tokens,
            "modules": modules or [],
        }
    )
    return create_app(
        settings,
        data_dir,
        model or FakeChatModel(),
        embeddings or FakeEmbeddings(),
        "fake-embeddings",
        frontend_dist,
        sandbox or FakeSandbox(),
    )


def read_events(response_text: str) -> list[dict]:
    """Parse a streamed reply (one JSON object per line) into events."""
    return [json.loads(line) for line in response_text.splitlines() if line]


def send(client: TestClient, text: str, chat_id: str | None = None) -> list[dict]:
    """Send a message and return the events that stream back."""
    response = client.post("/api/chats/send", json={"chatId": chat_id, "text": text})
    assert response.status_code == 200, response.text
    return read_events(response.text)


def make_pdf(path: Path, page_texts: list[str]) -> None:
    """A made-up PDF with one page per text, so no lecture content is needed."""
    document = pymupdf.open()
    for text in page_texts:
        document.new_page().insert_text((72, 72), text)
    document.save(path)
    document.close()


def wait_until_updated(client: TestClient) -> dict:
    """Wait for the notes update to finish, and return its final status."""
    for _ in range(100):
        status = client.get("/api/notes/status").json()
        if not status["updating"]:
            return status
        time.sleep(0.1)
    raise AssertionError("the notes update never finished")


def lost_connection() -> openai.APIConnectionError:
    """The error OpenAI's library raises when the internet drops."""
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return openai.APIConnectionError(request=request)


# A real 1x1 pixel PNG.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def upload(
    name: str = "screenshot.png", data: bytes = PNG, media_type: str = "image/png"
) -> dict:
    """An image as the browser sends it: base64 text inside the JSON."""
    return {
        "name": name,
        "mediaType": media_type,
        "data": base64.b64encode(data).decode(),
    }


def send_with_images(
    client: TestClient, text: str, images: list[dict], chat_id: str | None = None
):
    """Send a message with images attached, returning the raw response."""
    return client.post(
        "/api/chats/send", json={"chatId": chat_id, "text": text, "images": images}
    )
