"""Tests for documents (Word, Excel, PowerPoint, PDF) attached to messages."""

import base64
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from helpers import build_app, document_reader, make_pdf, read_events
from langchain_core.messages import HumanMessage
from pptx import Presentation

from askmynotes.chats import repository
from askmynotes.chats.documents import DocumentReader, InvalidDocument
from askmynotes.chats.history import estimate_tokens
from askmynotes.chats.models import DocumentUpload, Message, MessageDocument
from askmynotes.database import Database
from askmynotes.e2e_setup import make_docx, make_xlsx
from askmynotes.fake_model import FakeChatModel, text_of
from askmynotes.notes.libreoffice import default_soffice_path

LIBREOFFICE = default_soffice_path()
needs_libreoffice = pytest.mark.skipif(
    not LIBREOFFICE.exists(), reason="LibreOffice is not installed on this computer"
)


def make_pptx(path: Path) -> None:
    """Two made-up slides."""
    deck = Presentation()
    for title in ["Basic EPS", "Diluted EPS"]:
        slide = deck.slides.add_slide(deck.slide_layouts[5])
        slide.shapes.title.text = title
    deck.save(path)


def convert_with_libreoffice_to(source: Path, extension: str, outdir: Path) -> None:
    """Make a real old-format file: LibreOffice saves one from a new-format file."""
    subprocess.run(
        [
            str(LIBREOFFICE),
            f"-env:UserInstallation={(outdir / 'test_profile').as_uri()}",
            "--headless",
            "--convert-to",
            extension,
            "--outdir",
            str(outdir),
            str(source),
        ],
        check=True,
        capture_output=True,
        timeout=300,
    )


def as_upload(path: Path) -> DocumentUpload:
    return DocumentUpload(
        name=path.name, data=base64.b64encode(path.read_bytes()).decode()
    )


def as_json(name: str, data: bytes) -> dict:
    """A document as the browser sends it: base64 text inside the JSON."""
    return {"name": name, "data": base64.b64encode(data).decode()}


def send_with_documents(
    client: TestClient,
    text: str,
    documents: list[dict],
    chat_id: str | None = None,
):
    return client.post(
        "/api/chats/send",
        json={"chatId": chat_id, "text": text, "documents": documents},
    )


def stored_files(data_dir: Path) -> list[Path]:
    uploads = data_dir / "uploads"
    return [file for file in uploads.rglob("*") if file.is_file()]


def saved_chat_count(data_dir: Path) -> int:
    with Database(data_dir / "app.db").connection() as connection:
        return len(repository.list_chats(connection))


def question_sent_to_model(model: FakeChatModel) -> str:
    """The text of the student's message in the first (reply) model call."""
    call = next(m for m in model.received if "short title" not in text_of(m[0]))
    human = call[-1]
    assert isinstance(human, HumanMessage)
    return text_of(human)


# Reading each kind of file.


def test_each_kind_of_document_is_read_with_its_markers(tmp_path: Path) -> None:
    reader = DocumentReader(10, 1, 1000, LIBREOFFICE, tmp_path)
    make_pdf(tmp_path / "notes.pdf", ["Depreciation spreads cost.", "Straight line."])
    make_docx(tmp_path / "essay.docx", ["Goodwill is an intangible asset."])
    make_pptx(tmp_path / "deck.pptx")
    make_xlsx(tmp_path / "figures.xlsx")

    pdf, docx, pptx, xlsx = reader.read(
        [
            as_upload(tmp_path / name)
            for name in ["notes.pdf", "essay.docx", "deck.pptx", "figures.xlsx"]
        ]
    )

    assert (pdf.kind, pdf.count) == ("page", 2)
    assert "--- Page 2 ---\nStraight line." in pdf.text
    assert (docx.kind, docx.count) == ("document", None)
    assert docx.text == "Goodwill is an intangible asset."
    assert (pptx.kind, pptx.count) == ("slide", 2)
    assert "--- Slide 2 ---" in pptx.text and "Diluted EPS" in pptx.text
    assert (xlsx.kind, xlsx.count) == ("sheet", 2)
    assert "--- Sheet: Cash flow ---" in xlsx.text
    assert "| 2024 | 100.5 |" in xlsx.text
    assert "--- Sheet: Notes ---" in xlsx.text


@needs_libreoffice
def test_old_word_and_excel_files_are_read_through_libreoffice(
    tmp_path: Path,
) -> None:
    make_docx(tmp_path / "essay.docx", ["Goodwill is an intangible asset."])
    make_xlsx(tmp_path / "figures.xlsx")
    convert_with_libreoffice_to(tmp_path / "essay.docx", "doc", tmp_path)
    convert_with_libreoffice_to(tmp_path / "figures.xlsx", "xls", tmp_path)

    doc, xls = document_reader(tmp_path).read(
        [as_upload(tmp_path / "essay.doc"), as_upload(tmp_path / "figures.xls")]
    )

    assert "Goodwill is an intangible asset." in doc.text
    assert (xls.kind, xls.count) == ("sheet", 2)
    assert "| 2024 | 100.5 |" in xls.text


# Refusing documents.


def test_refused_documents_leave_nothing_saved(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path))
    make_pdf(tmp_path / "good.pdf", ["Some text"])
    make_pdf(tmp_path / "blank.pdf", [""])
    good = (tmp_path / "good.pdf").read_bytes()
    cases = {
        "not a document type": [as_json("script.exe", b"MZ")],
        "isn't a valid file": [{"name": "a.pdf", "data": "!!not base64!!"}],
        "larger than 1 MB": [as_json("big.pdf", b"x" * (1024 * 1024 + 1))],
        "up to 2 documents": [as_json(f"{i}.pdf", good) for i in range(3)],
        "can't be read": [as_json("blank.pdf", (tmp_path / "blank.pdf").read_bytes())],
        "can't be read: ": [as_json("broken.pdf", b"this is not really a pdf")],
    }

    for expected, documents in cases.items():
        response = send_with_documents(client, "Read this", documents)
        assert response.status_code == 422, expected
        detail = response.json()["detail"]
        assert expected.removesuffix(": ") in detail or "supported" in detail, detail

    assert saved_chat_count(tmp_path) == 0
    assert stored_files(tmp_path) == []


def test_documents_with_too_much_text_together_are_refused(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path))
    # About 3,000 characters each: 750 tokens, so two together pass 1,000.
    make_docx(tmp_path / "long.docx", ["word " * 600])
    data = (tmp_path / "long.docx").read_bytes()

    one = send_with_documents(client, "Read", [as_json("long.docx", data)])
    assert one.status_code == 200, one.text
    both = send_with_documents(
        client, "Read", [as_json("a.docx", data), as_json("b.docx", data)]
    )

    assert both.status_code == 422
    assert "more than the 1,000 allowed" in both.json()["detail"]


def test_a_document_with_no_text_is_refused_by_the_reader(tmp_path: Path) -> None:
    make_docx(tmp_path / "empty.docx", [""])

    with pytest.raises(InvalidDocument, match="no text to read"):
        document_reader(tmp_path).read([as_upload(tmp_path / "empty.docx")])


# What the model is sent.


def test_the_model_is_sent_the_documents_text_with_the_question(
    tmp_path: Path,
) -> None:
    model = FakeChatModel()
    client = TestClient(build_app(tmp_path, model))
    make_docx(tmp_path / "essay.docx", ["Goodwill is an intangible asset."])

    response = send_with_documents(
        client,
        "Summarise my essay",
        [as_json("essay.docx", (tmp_path / "essay.docx").read_bytes())],
    )

    assert response.status_code == 200, response.text
    sent = question_sent_to_model(model)
    assert 'Attached document "essay.docx" (user-provided material' in sent
    assert "Goodwill is an intangible asset." in sent
    assert sent.index("End of attached document.") < sent.index("Summarise my essay")


def test_a_documents_text_counts_towards_the_context_budget() -> None:
    document = MessageDocument(
        name="a.docx", kind="document", count=None, text="x" * 4000
    )
    base = {
        "id": 1,
        "role": "user",
        "content": "Hi",
        "status": "complete",
        "error": None,
        "sources": None,
        "images": [],
        "created_at": "2026-10-29T10:00:00Z",
    }

    without = estimate_tokens(Message.model_validate(base))
    with_document = estimate_tokens(
        Message.model_validate({**base, "documents": [document]})
    )

    assert with_document - without >= 1000


def test_the_title_is_written_from_the_file_name_not_its_text(tmp_path: Path) -> None:
    model = FakeChatModel()
    client = TestClient(build_app(tmp_path, model))
    make_docx(tmp_path / "essay.docx", ["Goodwill is an intangible asset."])

    response = send_with_documents(
        client,
        "",
        [as_json("essay.docx", (tmp_path / "essay.docx").read_bytes())],
    )

    events = read_events(response.text)
    assert events[0]["chat"]["title"] == "essay.docx"
    title_call = next(m for m in model.received if "short title" in text_of(m[0]))
    asked = text_of(title_call[-1])
    assert "essay.docx" in asked
    assert "Goodwill" not in asked


# Saving, reopening, editing, deleting.


def test_a_document_survives_a_restart_and_its_text_stays_private(
    tmp_path: Path,
) -> None:
    make_xlsx(tmp_path / "figures.xlsx")
    original = (tmp_path / "figures.xlsx").read_bytes()
    client = TestClient(build_app(tmp_path))
    events = read_events(
        send_with_documents(client, "Check", [as_json("figures.xlsx", original)]).text
    )
    chat_id = events[0]["chat"]["id"]
    expected = [{"name": "figures.xlsx", "kind": "sheet", "count": 2}]
    assert events[0]["userMessage"]["documents"] == expected

    reopened = TestClient(build_app(tmp_path)).get(f"/api/chats/{chat_id}").json()

    assert reopened["messages"][0]["documents"] == expected
    assert reopened["messages"][1]["documents"] == []
    assert "Cash flow" not in str(reopened["messages"][0])
    [saved] = stored_files(tmp_path)
    assert saved.suffix == ".xlsx" and saved.read_bytes() == original


def test_deleting_a_chat_deletes_its_saved_documents(tmp_path: Path) -> None:
    client = TestClient(build_app(tmp_path))
    make_docx(tmp_path / "essay.docx", ["Goodwill"])
    events = read_events(
        send_with_documents(
            client,
            "Read",
            [as_json("essay.docx", (tmp_path / "essay.docx").read_bytes())],
        ).text
    )
    chat_id = events[0]["chat"]["id"]
    assert len(stored_files(tmp_path)) == 1

    assert client.delete(f"/api/chats/{chat_id}").status_code == 204

    assert stored_files(tmp_path) == []


def test_editing_the_latest_question_keeps_its_documents(tmp_path: Path) -> None:
    model = FakeChatModel()
    client = TestClient(build_app(tmp_path, model))
    make_docx(tmp_path / "essay.docx", ["Goodwill is an intangible asset."])
    events = read_events(
        send_with_documents(
            client,
            "Original wording",
            [as_json("essay.docx", (tmp_path / "essay.docx").read_bytes())],
        ).text
    )
    chat_id = events[0]["chat"]["id"]
    question_id = events[0]["userMessage"]["id"]
    calls_before = len(model.received)

    response = client.post(
        f"/api/chats/{chat_id}/messages/{question_id}/edit",
        json={
            "text": "",
            "expectedLatestMessageId": question_id,
            "expectedOriginalText": "Original wording",
        },
    )

    # A document alone is enough, as an image alone is.
    assert response.status_code == 200, response.text
    accepted = read_events(response.text)[0]
    assert [d["name"] for d in accepted["userMessage"]["documents"]] == ["essay.docx"]
    resent = "\n".join(
        text_of(message) for call in model.received[calls_before:] for message in call
    )
    assert "Goodwill is an intangible asset." in resent


def test_an_upload_writes_nothing_to_the_notes_database(tmp_path: Path) -> None:
    from askmynotes.fake_model import FakeEmbeddings
    from askmynotes.notes.store import NotesStore

    client = TestClient(build_app(tmp_path))
    make_docx(tmp_path / "essay.docx", ["Goodwill"])

    send_with_documents(
        client, "Read", [as_json("essay.docx", (tmp_path / "essay.docx").read_bytes())]
    )

    store = NotesStore(tmp_path / "chroma", FakeEmbeddings(), "fake-embeddings")
    assert store.count() == 0
    with Database(tmp_path / "app.db").connection() as connection:
        tables = {
            row["name"] for row in connection.execute("SELECT name FROM sqlite_master")
        }
        if "notes_files" in tables:
            assert (
                connection.execute("SELECT COUNT(*) FROM notes_files").fetchone()[0]
                == 0
            )


def test_a_database_from_before_documents_opens_and_gains_the_table(
    tmp_path: Path,
) -> None:
    import sqlite3

    # An older database: chats and messages, but no message_documents table.
    with sqlite3.connect(tmp_path / "app.db") as connection:
        connection.executescript(
            "CREATE TABLE chats (id TEXT PRIMARY KEY, title TEXT NOT NULL, "
            "pinned INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, "
            "last_used_at TEXT NOT NULL, summary TEXT, "
            "summarised_up_to INTEGER NOT NULL DEFAULT 0);"
            "CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "chat_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, "
            "status TEXT NOT NULL DEFAULT 'complete', error TEXT, sources TEXT, "
            "created_at TEXT NOT NULL, quoted_context TEXT);"
            "CREATE TABLE message_images (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "message_id INTEGER NOT NULL, path TEXT NOT NULL);"
            "INSERT INTO chats VALUES ('old', 'Old chat', 0, "
            "'2026-10-01T10:00:00+00:00', '2026-10-01T10:00:00+00:00', NULL, 0);"
            "INSERT INTO messages (chat_id, role, content, created_at) VALUES "
            "('old', 'user', 'An old question', '2026-10-01T10:00:00+00:00');"
        )

    client = TestClient(build_app(tmp_path))

    chat = client.get("/api/chats/old").json()
    assert chat["messages"][0]["content"] == "An old question"
    assert chat["messages"][0]["documents"] == []
