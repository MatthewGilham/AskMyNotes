"""Tests for the notes database and folder sync.

The notes are small PDFs generated here from made-up text, and the embeddings
are fake, so nothing is paid for and no lecture content is needed.
"""

import os
import time
from pathlib import Path

import httpx
import openai
import pytest
from fastapi.testclient import TestClient
from helpers import build_app, make_pdf, usage_ledger, wait_until_updated

from askmynotes.database import Database
from askmynotes.fake_model import FakeEmbeddings
from askmynotes.notes import records
from askmynotes.notes import sync as sync_module
from askmynotes.notes.chunking import chunk_file
from askmynotes.notes.convert import ConvertedFile, Page
from askmynotes.notes.libreoffice import default_soffice_path
from askmynotes.notes.store import EmbeddingModelChanged, NotesStore
from askmynotes.notes.sync import NotesSync
from askmynotes.settings import Module


class Setup:
    """A notes folder, a data folder, fake embeddings, and a way to sync."""

    def __init__(self, tmp_path: Path) -> None:
        self.notes = tmp_path / "notes"
        self.notes.mkdir()
        self.data = tmp_path / "data"
        self.data.mkdir()
        self.module = Module(name="Testing Module", short_name="TM", folder=self.notes)
        self.embeddings = FakeEmbeddings()
        self.database = Database(self.data / "app.db")
        records.create_tables(self.database)
        self.store = NotesStore(self.data / "chroma", self.embeddings, "fake")

    def sync(self, modules: list[Module] | None = None) -> NotesSync:
        sync = NotesSync(
            self.database,
            self.store,
            [self.module] if modules is None else modules,
            default_soffice_path(),
            self.data,
            max_chunk_characters=3000,
            ledger=usage_ledger(self.database),
        )
        sync.run()
        return sync

    def recorded(self) -> dict[str, str]:
        with self.database.connection() as connection:
            return records.recorded_fingerprints(connection)


@pytest.fixture
def setup(tmp_path: Path) -> Setup:
    return Setup(tmp_path)


def counts(sync: NotesSync) -> tuple[int, int, int]:
    return sync.status.new, sync.status.changed, sync.status.deleted


def test_new_file_is_added(setup: Setup) -> None:
    make_pdf(setup.notes / "a.pdf", ["Depreciation basics", "Straight-line method"])

    sync = setup.sync()

    assert counts(sync) == (1, 0, 0)
    assert sync.status.updating is False
    assert sync.status.file_count == 1
    assert sync.status.error is None
    assert len(setup.store.chunks_of("TM/a.pdf")) == 2
    assert list(setup.recorded()) == ["TM/a.pdf"]
    assert (setup.data / "notes_markdown" / "TM" / "a.pdf.md").exists()


def test_each_chunk_names_its_module_file_and_page(setup: Setup) -> None:
    make_pdf(setup.notes / "a.pdf", ["First", "Second"])

    setup.sync()

    chunks = sorted(setup.store.chunks_of("TM/a.pdf"), key=lambda c: c["number"])
    assert [
        (c["module"], c["file_name"], c["location"], c["number"]) for c in chunks
    ] == [
        ("TM", "a.pdf", "page", 1),
        ("TM", "a.pdf", "page", 2),
    ]


def test_changed_file_is_reindexed_and_others_are_untouched(setup: Setup) -> None:
    make_pdf(setup.notes / "a.pdf", ["Old text"])
    make_pdf(setup.notes / "b.pdf", ["Other file", "Two pages"])
    setup.sync()
    embedded_before = setup.embeddings.texts_embedded
    b_before = setup.store.chunks_of("TM/b.pdf")

    make_pdf(setup.notes / "a.pdf", ["New text", "and a new page"])
    sync = setup.sync()

    assert counts(sync) == (0, 1, 0)
    # Only the changed file's two pages were embedded again.
    assert setup.embeddings.texts_embedded - embedded_before == 2
    assert len(setup.store.chunks_of("TM/a.pdf")) == 2
    assert setup.store.chunks_of("TM/b.pdf") == b_before
    markdown = (setup.data / "notes_markdown" / "TM" / "a.pdf.md").read_text("utf-8")
    assert "New text" in markdown


def test_deleted_file_is_removed_from_the_database(setup: Setup) -> None:
    make_pdf(setup.notes / "a.pdf", ["Going away"])
    make_pdf(setup.notes / "b.pdf", ["Staying"])
    setup.sync()

    (setup.notes / "a.pdf").unlink()
    sync = setup.sync()

    assert counts(sync) == (0, 0, 1)
    assert setup.store.chunks_of("TM/a.pdf") == []
    assert list(setup.recorded()) == ["TM/b.pdf"]
    assert not (setup.data / "notes_markdown" / "TM" / "a.pdf.md").exists()
    assert sync.status.file_count == 1


def test_file_with_same_size_but_new_contents_is_detected(setup: Setup) -> None:
    path = setup.notes / "a.pdf"
    make_pdf(path, ["Alpha version of the slide"])
    original_size = path.stat().st_size
    original_times = (path.stat().st_atime_ns, path.stat().st_mtime_ns)
    setup.sync()

    # New contents, padded to exactly the same size, with the old modified
    # time put back: only the contents tell it apart.
    replacement = setup.notes / "replacement.pdf"
    make_pdf(replacement, ["Bravo version of the slide"])
    data = replacement.read_bytes()
    replacement.unlink()
    assert len(data) <= original_size
    path.write_bytes(data + b" " * (original_size - len(data)))
    os.utime(path, ns=original_times)
    assert path.stat().st_size == original_size

    sync = setup.sync()

    assert counts(sync) == (0, 1, 0)
    markdown = (setup.data / "notes_markdown" / "TM" / "a.pdf.md").read_text("utf-8")
    assert "Bravo" in markdown


def test_interrupted_sync_is_redone_cleanly(setup: Setup) -> None:
    make_pdf(setup.notes / "a.pdf", ["Page one", "Page two"])
    # As if an earlier run stopped after storing some chunks but before
    # recording the file as synced: a stray, out-of-date chunk is left behind.
    stray = chunk_file(
        "TM/a.pdf",
        setup.module,
        "a.pdf",
        ConvertedFile(kind="page", pages=[Page(9, "Out-of-date text")]),
        3000,
    )
    setup.store.add(stray)

    sync = setup.sync()

    assert counts(sync) == (1, 0, 0)
    numbers = sorted(c["number"] for c in setup.store.chunks_of("TM/a.pdf"))
    assert numbers == [1, 2]  # the stray chunk is gone, nothing doubled up


class FailingEmbeddings(FakeEmbeddings):
    """Embeddings that fail like a lost internet connection."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        request = httpx.Request("POST", "https://api.openai.com/v1/embeddings")
        raise openai.APIConnectionError(request=request)


def test_an_embedding_failure_stops_the_update_and_says_why(setup: Setup) -> None:
    make_pdf(setup.notes / "a.pdf", ["Page one"])
    setup.store = NotesStore(setup.data / "chroma", FailingEmbeddings(), "fake")

    sync = setup.sync()

    assert sync.status.updating is False
    assert sync.status.error is not None
    assert "Couldn't reach OpenAI" in sync.status.error
    # Not recorded, so the next update tries it again.
    assert setup.recorded() == {}


def test_unreadable_file_is_listed_and_not_retried_until_it_changes(
    setup: Setup,
) -> None:
    (setup.notes / "broken.pdf").write_bytes(b"not really a pdf")
    make_pdf(setup.notes / "good.pdf", ["Fine"])

    first = setup.sync()
    second = setup.sync()

    assert [(u.module, u.file_name) for u in first.status.unreadable] == [
        ("TM", "broken.pdf")
    ]
    assert first.status.unreadable[0].reason
    assert first.status.file_count == 1
    assert counts(second) == (0, 0, 0)
    assert [u.file_name for u in second.status.unreadable] == ["broken.pdf"]
    assert setup.store.chunks_of("TM/broken.pdf") == []


def test_a_file_open_in_another_app_is_skipped_and_keeps_its_notes(
    setup: Setup, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_pdf(setup.notes / "open.pdf", ["Leases"])
    make_pdf(setup.notes / "b.pdf", ["Provisions"])
    setup.sync()
    open_chunks = setup.store.chunks_of("TM/open.pdf")
    make_pdf(setup.notes / "new.pdf", ["Grants"])
    real_fingerprint = sync_module.fingerprint

    # On Windows, a file PowerPoint has open can't be read: Python raises
    # PermissionError. Simulated here, because macOS has no such locks.
    def fingerprint_refusing_open_pdf(path: Path) -> str:
        if path.name == "open.pdf":
            raise PermissionError(13, "Permission denied")
        return real_fingerprint(path)

    monkeypatch.setattr(sync_module, "fingerprint", fingerprint_refusing_open_pdf)
    sync = setup.sync()

    assert sync.status.error is None
    assert sync.status.in_use == ["TM/open.pdf"]
    # Not counted as deleted: its notes stay. The other files still update.
    assert counts(sync) == (1, 0, 0)
    assert setup.store.chunks_of("TM/open.pdf") == open_chunks
    assert sorted(setup.recorded()) == ["TM/b.pdf", "TM/new.pdf", "TM/open.pdf"]
    assert sync.status.file_count == 3


def test_starting_twice_with_no_changes_makes_no_embedding_calls(setup: Setup) -> None:
    make_pdf(setup.notes / "a.pdf", ["Page one"])
    setup.sync()
    embedded = setup.embeddings.texts_embedded

    sync = setup.sync()

    assert counts(sync) == (0, 0, 0)
    assert setup.embeddings.texts_embedded == embedded


def test_a_removed_module_counts_as_deleted_files(setup: Setup) -> None:
    make_pdf(setup.notes / "a.pdf", ["Page one"])
    setup.sync()

    sync = setup.sync(modules=[])

    assert counts(sync) == (0, 0, 1)
    assert setup.store.count() == 0


def test_changing_the_embedding_model_is_refused(tmp_path: Path) -> None:
    NotesStore(tmp_path / "chroma", FakeEmbeddings(), "model-one")

    with pytest.raises(EmbeddingModelChanged, match="model-one"):
        NotesStore(tmp_path / "chroma", FakeEmbeddings(), "model-two")


def test_a_long_page_is_split_and_each_part_keeps_the_page_number() -> None:
    module = Module(name="Testing Module", short_name="TM", folder=Path("x"))
    long_text = " ".join(f"sentence {n} about depreciation." for n in range(200))
    converted = ConvertedFile(kind="page", pages=[Page(7, long_text)])

    chunks = chunk_file("TM/a.pdf", module, "a.pdf", converted, max_characters=1000)

    assert len(chunks) > 1
    assert {c.metadata["number"] for c in chunks} == {7}
    assert [c.metadata["part"] for c in chunks] == list(range(1, len(chunks) + 1))
    assert all(len(c.text) <= 1000 for c in chunks)


def test_empty_slides_are_skipped_and_chunks_carry_a_header() -> None:
    module = Module(name="Testing Module", short_name="TM", folder=Path("x"))
    converted = ConvertedFile(
        kind="slide", pages=[Page(1, "Title slide"), Page(2, ""), Page(3, "Content")]
    )

    chunks = chunk_file("TM/deck.pptx", module, "deck.pptx", converted, 3000)

    assert [c.metadata["number"] for c in chunks] == [1, 3]
    assert chunks[0].text == "Title slide"
    assert chunks[0].text_to_embed.startswith(
        "Testing Module (TM) | deck.pptx | Slide 1"
    )


# The app: syncing on start, the status route, Refresh, and pausing chat.


class SlowEmbeddings(FakeEmbeddings):
    """Embeddings that take a while, so the update is still running."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        time.sleep(1.5)
        return super().embed_documents(texts)


def notes_module(tmp_path: Path) -> Module:
    folder = tmp_path / "notes"
    folder.mkdir()
    make_pdf(folder / "a.pdf", ["Depreciation"])
    return Module(name="Testing Module", short_name="TM", folder=folder)


def test_the_app_updates_the_notes_when_it_starts(tmp_path: Path) -> None:
    app = build_app(tmp_path / "data", modules=[notes_module(tmp_path)])

    with TestClient(app) as client:
        status = wait_until_updated(client)

    assert status["new"] == 1
    assert status["fileCount"] == 1
    assert status["inUse"] == []


def test_chat_is_refused_while_notes_update(tmp_path: Path) -> None:
    app = build_app(
        tmp_path / "data",
        modules=[notes_module(tmp_path)],
        embeddings=SlowEmbeddings(),
    )

    with TestClient(app) as client:
        assert client.get("/api/notes/status").json()["updating"] is True
        refused = client.post("/api/chats/send", json={"text": "Hello"})
        wait_until_updated(client)
        allowed = client.post("/api/chats/send", json={"text": "Hello"})

    assert refused.status_code == 409
    assert "notes are being updated" in refused.json()["detail"]
    assert client.get("/api/chats").json() != []  # the later message went through
    assert allowed.status_code == 200


def test_refresh_runs_the_same_check_without_a_restart(tmp_path: Path) -> None:
    module = notes_module(tmp_path)
    app = build_app(tmp_path / "data", modules=[module])

    with TestClient(app) as client:
        wait_until_updated(client)
        make_pdf(module.folder / "b.pdf", ["A new lecture"])

        response = client.post("/api/notes/refresh")
        status = wait_until_updated(client)

    assert response.status_code == 202
    assert (status["new"], status["changed"], status["deleted"]) == (1, 0, 0)
    assert status["fileCount"] == 2


def test_refresh_while_already_updating_is_refused(tmp_path: Path) -> None:
    app = build_app(
        tmp_path / "data",
        modules=[notes_module(tmp_path)],
        embeddings=SlowEmbeddings(),
    )

    with TestClient(app) as client:
        response = client.post("/api/notes/refresh")
        wait_until_updated(client)

    assert response.status_code == 409
    assert "already being updated" in response.json()["detail"]
