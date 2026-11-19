"""Tests for searching the notes from the chat: the `search_notes` tool, the
module filter, and the sources saved with each notes answer.

The notes are small made-up PDFs, the embeddings are fake, and the model is a
fake that follows a script, so nothing is paid for.
"""

import asyncio
import re
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from helpers import build_app, make_pdf, send, wait_until_updated
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage
from pydantic import ValidationError

from askmynotes.fake_model import FakeChatModel, FakeEmbeddings, FakeReply, text_of
from askmynotes.notes.chunking import Chunk
from askmynotes.notes.search import FoundNotes, NotesSearch
from askmynotes.notes.sources import answer_and_sources, split_sources_line
from askmynotes.notes.store import SEARCH_EFFORT, NoteResult, NotesStore
from askmynotes.settings import Module

# Helpers


def module(short_name: str, folder: Path = Path("unused")) -> Module:
    return Module(name=f"Module {short_name}", short_name=short_name, folder=folder)


def slide(module_short_name: str, file_name: str, number: int) -> Chunk:
    file_id = f"{module_short_name}/{file_name}"
    return Chunk(
        id=f"{file_id}#{number}#1",
        text=f"{module_short_name} {file_name} slide {number}",
        text_to_embed=f"{module_short_name} {file_name} slide {number}",
        metadata={
            "file_id": file_id,
            "module": module_short_name,
            "file_name": file_name,
            "location": "slide",
            "number": number,
            "part": 1,
        },
    )


def result(file_name: str, number: int, part: int = 1) -> NoteResult:
    return NoteResult(
        chunk_id=f"TM/{file_name}#{number}#{part}",
        module="TM",
        file_name=file_name,
        location="page",
        number=number,
        text="text",
    )


def search_then_answer(
    answer: Callable[[str], str], args: dict | None = None
) -> Callable[[list[BaseMessage]], str | FakeReply]:
    """A responder that searches the notes, then answers with `answer(results)`,
    where `results` is the text the search gave the model."""

    def responder(messages: list[BaseMessage]) -> str | FakeReply:
        if "short title" in text_of(messages[0]):
            return "A Fake Title"
        if isinstance(messages[-1], ToolMessage):
            return answer(text_of(messages[-1]))
        return FakeReply(
            tool_call={"name": "search_notes", "args": args or {"query": "lease"}}
        )

    return responder


def short_id_of(results: str, file_name: str) -> str:
    """The id the search gave a file's page, e.g. "S2"."""
    found = re.search(rf"\[(S\d+)\] TM \| {re.escape(file_name)} \|", results)
    assert found is not None, results
    return found.group(1)


@pytest.fixture
def notes_module(tmp_path: Path) -> Module:
    """A module of three one-page lectures."""
    folder = tmp_path / "notes"
    folder.mkdir()
    make_pdf(folder / "a.pdf", ["Depreciation spreads the cost of an asset."])
    make_pdf(folder / "b.pdf", ["Goodwill is tested for impairment every year."])
    make_pdf(folder / "c.pdf", ["Leases are shown on the balance sheet."])
    return Module(name="Testing Module", short_name="TM", folder=folder)


def chat_with_notes(
    data_dir: Path, notes_module: Module, model: FakeChatModel, question: str
) -> list[dict]:
    """Start the app, wait for the notes to be indexed, and ask a question."""
    with TestClient(build_app(data_dir, model, modules=[notes_module])) as client:
        wait_until_updated(client)
        return send(client, question)


# The search tool and the module filter


def test_module_filter_searches_only_those_modules(tmp_path: Path) -> None:
    store = NotesStore(tmp_path / "chroma", FakeEmbeddings(), "fake")
    store.add([slide(m, "lecture.pdf", n) for m in ("AFA", "FR", "BL") for n in (1, 2)])
    search = NotesSearch(store, [module("AFA"), module("FR"), module("BL")], 10)

    only_two = FoundNotes()
    asyncio.run(search.tool(only_two).ainvoke({"query": "x", "modules": ["AFA", "FR"]}))
    every_module = FoundNotes()
    asyncio.run(search.tool(every_module).ainvoke({"query": "x"}))

    assert {r.module for r in only_two.by_short_id.values()} == {"AFA", "FR"}
    assert len(only_two.by_short_id) == 4
    assert {r.module for r in every_module.by_short_id.values()} == {"AFA", "FR", "BL"}


def test_unknown_module_short_name_is_rejected(tmp_path: Path) -> None:
    store = NotesStore(tmp_path / "chroma", FakeEmbeddings(), "fake")
    found = FoundNotes()
    tool = NotesSearch(store, [module("AFA")], 10).tool(found)

    with pytest.raises(ValidationError, match="AFA"):
        asyncio.run(tool.ainvoke({"query": "x", "modules": ["XYZ"]}))
    assert found.by_short_id == {}


def test_a_rejected_module_is_explained_to_the_agent_and_the_reply_carries_on(
    tmp_path: Path, notes_module: Module
) -> None:
    model = FakeChatModel(
        responder=search_then_answer(
            lambda results: "No such module.", {"query": "x", "modules": ["XYZ"]}
        )
    )

    events = chat_with_notes(tmp_path / "data", notes_module, model, "Only XYZ")

    tool_message = model.received[-1][-1]
    assert isinstance(tool_message, ToolMessage)
    assert tool_message.status == "error"
    assert "'TM'" in text_of(tool_message)  # it's told which modules exist
    assert events[-1]["type"] == "done"
    assert events[-1]["message"]["sources"] is None


def test_results_are_numbered_across_searches_and_repeats_keep_their_id() -> None:
    found = FoundNotes()

    first = [found.add(result("a.pdf", 1)), found.add(result("b.pdf", 1))]
    second = [found.add(result("b.pdf", 1)), found.add(result("c.pdf", 1))]

    assert first == ["S1", "S2"]
    assert second == ["S2", "S3"]


# The sources saved with each answer


def test_only_the_sources_the_answer_used_are_saved(
    tmp_path: Path, notes_module: Module
) -> None:
    model = FakeChatModel(
        responder=search_then_answer(
            lambda results: (
                "Goodwill is tested every year.\n\n"
                f"Sources used: {short_id_of(results, 'b.pdf')}"
            )
        )
    )

    events = chat_with_notes(tmp_path / "data", notes_module, model, "Goodwill?")

    saved = events[-1]["message"]
    assert saved["sources"] == [
        {"fileName": "b.pdf", "module": "TM", "location": "page", "number": 1}
    ]
    # The line naming the sources is taken off the saved answer.
    assert saved["content"] == "Goodwill is tested every year."


def test_missing_sources_line_lists_all_results(
    tmp_path: Path, notes_module: Module
) -> None:
    model = FakeChatModel(responder=search_then_answer(lambda results: "An answer."))

    events = chat_with_notes(tmp_path / "data", notes_module, model, "Leases?")

    sources = events[-1]["message"]["sources"]
    assert [s["fileName"] for s in sources] == ["a.pdf", "b.pdf", "c.pdf"]


def test_an_answer_that_used_none_of_the_results_has_no_sources(
    tmp_path: Path, notes_module: Module
) -> None:
    model = FakeChatModel(
        responder=search_then_answer(
            lambda results: (
                "Your notes don't cover this.\n\n"
                ":::beyond\nA general answer.\n:::\n\nSources used: none"
            )
        )
    )

    events = chat_with_notes(tmp_path / "data", notes_module, model, "Crypto?")

    saved = events[-1]["message"]
    assert saved["sources"] is None
    assert saved["content"].endswith(":::")


def test_sources_are_shown_after_reopening_the_chat(
    tmp_path: Path, notes_module: Module
) -> None:
    data_dir = tmp_path / "data"
    model = FakeChatModel(
        responder=search_then_answer(
            lambda results: f"Answer.\n\nSources used: {short_id_of(results, 'a.pdf')}"
        )
    )
    chat_id = chat_with_notes(data_dir, notes_module, model, "Depreciation?")[0][
        "chat"
    ]["id"]

    # A new app on the same data folder, as after a restart.
    reopened = TestClient(build_app(data_dir, modules=[notes_module]))
    reply = reopened.get(f"/api/chats/{chat_id}").json()["messages"][-1]

    assert reply["sources"] == [
        {"fileName": "a.pdf", "module": "TM", "location": "page", "number": 1}
    ]


def test_a_search_is_announced_before_the_answer_streams(
    tmp_path: Path, notes_module: Module
) -> None:
    model = FakeChatModel(responder=search_then_answer(lambda results: "An answer."))

    events = chat_with_notes(tmp_path / "data", notes_module, model, "Leases?")

    kinds = [e["type"] for e in events]
    assert "searching" in kinds
    assert kinds.index("searching") < kinds.index("token")


def test_a_reply_without_a_search_has_no_sources(
    tmp_path: Path, notes_module: Module
) -> None:
    model = FakeChatModel(responder=lambda messages: "Pasta, garlic and oil.")

    events = chat_with_notes(tmp_path / "data", notes_module, model, "A recipe?")

    assert "searching" not in [e["type"] for e in events]
    assert events[-1]["message"]["sources"] is None


def test_the_instructions_list_the_modules(
    tmp_path: Path, notes_module: Module
) -> None:
    model = FakeChatModel(responder=lambda messages: "Hello.")

    chat_with_notes(tmp_path / "data", notes_module, model, "Hi")

    answer_call = [m for m in model.received if "short title" not in text_of(m[0])][0]
    instructions = answer_call[0]
    assert isinstance(instructions, SystemMessage)
    assert "- Testing Module (TM)" in text_of(instructions)
    assert "{modules}" not in text_of(instructions)


# Reading the sources line


@pytest.mark.parametrize(
    ("reply", "complete", "expected"),
    [
        ("Answer.\n\nSources used: S1, S3", True, ("Answer.", ["S1", "S3"])),
        ("Answer.\n\n**Sources used:** S2", True, ("Answer.", ["S2"])),
        ("Answer.\n\nSources used: none", True, ("Answer.", [])),
        ("Answer with no line.", True, ("Answer with no line.", None)),
        # The line straight after the last sentence, with or without bold.
        ("It is 2 years. Sources used: S1", True, ("It is 2 years.", ["S1"])),
        (
            "It is 2 years. **Sources used: S1, S2**",
            True,
            ("It is 2 years.", ["S1", "S2"]),
        ),
        ("Answer.\n\n**Sources used:** S3.", True, ("Answer.", ["S3"])),
        ("Answer. Sources used: S1 and S4", True, ("Answer.", ["S1", "S4"])),
        # Words after the label mean it isn't the closing line.
        ("The sources used: S1 matter.", True, ("The sources used: S1 matter.", None)),
        # A stopped reply may end part-way through the line.
        ("Answer.\n\nSources us", False, ("Answer.", None)),
        ("Answer. **Sources used: S1,", False, ("Answer.", None)),
        # A reply that failed before writing anything.
        ("", False, ("", None)),
        # ...but ordinary words that start the same way are kept.
        ("Answer.\nSo", False, ("Answer.\nSo", None)),
        ("Answer.\nSo", True, ("Answer.\nSo", None)),
    ],
)
def test_the_sources_line_is_separated_from_the_answer(
    reply: str, complete: bool, expected: tuple[str, list[str] | None]
) -> None:
    assert split_sources_line(reply, complete) == expected


def test_each_page_is_listed_once_even_if_several_of_its_parts_were_used() -> None:
    found = FoundNotes()
    found.add(result("a.pdf", 4, part=1))
    found.add(result("a.pdf", 4, part=2))

    _, sources = answer_and_sources("Answer.\n\nSources used: S1, S2", found, True)

    assert sources is not None
    assert [(s.file_name, s.number) for s in sources] == [("a.pdf", 4)]


# Searching: repeated slides and search effort


def test_a_slide_that_exists_twice_is_returned_once(tmp_path: Path) -> None:
    store = NotesStore(tmp_path / "chroma", FakeEmbeddings(), "fake")
    original = slide("TM", "lecture.pdf", 1)
    # The same text in a copied file, with its own id and file name.
    copy = Chunk(**{**vars(slide("TM", "lecture (1).pdf", 1)), "text": original.text})
    store.add([original, copy])
    store.add([slide("TM", "other.pdf", n) for n in range(2, 5)])

    results = store.search("x", [], 4)

    assert len(results) == 4
    assert len({r.text for r in results}) == 4


def test_a_search_still_returns_the_requested_number_after_dropping_repeats(
    tmp_path: Path,
) -> None:
    store = NotesStore(tmp_path / "chroma", FakeEmbeddings(), "fake")
    chunks = [slide("TM", "lecture.pdf", n) for n in range(1, 7)]
    copies = [Chunk(**{**vars(c), "id": c.id + "-copy"}) for c in chunks]
    store.add(chunks + copies)

    results = store.search("x", [], 6)

    assert len(results) == 6
    assert len({r.text for r in results}) == 6


def test_the_search_effort_is_raised_on_an_existing_database(tmp_path: Path) -> None:
    folder = tmp_path / "chroma"
    NotesStore(folder, FakeEmbeddings(), "fake")

    reopened = NotesStore(folder, FakeEmbeddings(), "fake")

    assert reopened._collection.configuration["hnsw"]["ef_search"] == SEARCH_EFFORT
