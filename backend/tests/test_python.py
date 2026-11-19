"""Tests for Python (Code Interpreter): when a sandbox is made and removed, what
it is given, the code and files that come back, and what it costs.

Everything is free. A `FakeSandbox` stands in for OpenAI's, and the fake model
reports runs of Python and file citations the way the real stream does (the real
shapes were recorded in phase 25's real check; see `docs/PLAN.md`).
"""

import asyncio
import base64
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from helpers import (
    BIG_BUDGET,
    TEST_CONFIG,
    TEST_PRICES,
    TEST_SETTINGS,
    build_app,
    document_reader,
    usage_ledger,
    wait_until_updated,
)
from langchain_core.messages import AIMessageChunk, SystemMessage

from askmynotes.agent.agent import Agent
from askmynotes.calculator.tools import ToolRuns
from askmynotes.chats import repository
from askmynotes.chats.conversation import Conversation
from askmynotes.chats.history import ModelHistory
from askmynotes.chats.models import SendRequest
from askmynotes.database import Database
from askmynotes.e2e_setup import make_xlsx
from askmynotes.fake_model import (
    FakeChatModel,
    FakeEmbeddings,
    FakeReply,
    FakeSandbox,
    text_of,
)
from askmynotes.interpreter.reply import (
    MAX_OUTPUT_LINES,
    PythonReply,
    without_sandbox_links,
)
from askmynotes.notes.search import NotesSearch
from askmynotes.notes.store import NotesStore

FAKE_CALL = 0.00182


def chat_id_of(events: list[dict]) -> str:
    return next(e["chat"]["id"] for e in events if e["type"] == "start")


def spreadsheet(tmp_path: Path, name: str = "figures.xlsx") -> dict:
    """An Excel file as the browser sends it."""
    path = tmp_path / name
    make_xlsx(path)
    return {"name": name, "data": base64.b64encode(path.read_bytes()).decode()}


def send_python(
    client: TestClient,
    text: str,
    chat_id: str | None = None,
    documents: list[dict] | None = None,
    use_python: bool = True,
):
    response = client.post(
        "/api/chats/send",
        json={
            "chatId": chat_id,
            "text": text,
            "documents": documents or [],
            "usePython": use_python,
        },
    )
    assert response.status_code == 200, response.text
    return [
        __import__("json").loads(line) for line in response.text.splitlines() if line
    ]


def reply_of(events: list[dict]) -> dict:
    return next(e["message"] for e in events if e["type"] in ("done", "error"))


def generated_files(data_dir: Path) -> list[Path]:
    return [
        f
        for f in (data_dir / "uploads").rglob("*")
        if f.is_file() and "generated" in f.parts
    ]


# When a sandbox exists


def test_with_python_on_one_sandbox_is_made_and_removed(tmp_path: Path) -> None:
    sandbox = FakeSandbox()
    model = FakeChatModel()
    with TestClient(build_app(tmp_path / "data", model, sandbox=sandbox)) as client:
        wait_until_updated(client)
        events = send_python(client, "Use python on this")

    assert reply_of(events)["status"] == "complete"
    assert sandbox.created == ["cntr_fake_1"]
    assert sandbox.deleted == ["cntr_fake_1"]
    offered = [tool for tools in model.offered_tools for tool in tools]
    assert {"type": "code_interpreter", "container": "cntr_fake_1"} in offered


def test_with_python_off_there_is_no_sandbox_and_no_tool(tmp_path: Path) -> None:
    sandbox = FakeSandbox()
    model = FakeChatModel()
    with TestClient(build_app(tmp_path / "data", model, sandbox=sandbox)) as client:
        wait_until_updated(client)
        # The word "python" in the question changes nothing: only the button does.
        events = send_python(client, "Use python on this", use_python=False)
        total = client.get("/api/usage").json()

    assert reply_of(events)["status"] == "complete"
    assert sandbox.created == []
    offered = [tool for tools in model.offered_tools for tool in tools]
    assert not any(
        isinstance(tool, dict) and tool.get("type") == "code_interpreter"
        for tool in offered
    )
    # Just the reply and the title: no sandbox fee.
    assert total["cost"] == pytest.approx(2 * FAKE_CALL)


def test_the_instructions_tell_the_model_about_python_only_when_it_is_on(
    tmp_path: Path,
) -> None:
    model = FakeChatModel(responder=lambda m: "Hello")
    with TestClient(build_app(tmp_path / "data", model)) as client:
        wait_until_updated(client)
        send_python(client, "Hi", use_python=False)
        send_python(client, "Hi again", use_python=True)

    answers = [m for m in model.received if "short title" not in text_of(m[0])]
    off, on = (
        " ".join(text_of(next(x for x in call if isinstance(x, SystemMessage))).split())
        for call in answers
    )
    # Without the button the model is told it has no Python; with it, how to use it.
    assert "only run Python when the student has switched it on" in off
    assert "Python for this reply" not in off
    assert "Python for this reply" in on
    assert "`/mnt/data`" in on
    assert "No files are attached." in on


def test_python_without_a_sandbox_is_refused(tmp_path: Path) -> None:
    from askmynotes.app import create_app

    app = create_app(
        TEST_SETTINGS, tmp_path / "data", FakeChatModel(), FakeEmbeddings(), "fake"
    )
    with TestClient(app) as client:
        wait_until_updated(client)
        response = client.post(
            "/api/chats/send", json={"text": "Hi", "usePython": True}
        )
        chats = client.get("/api/chats").json()

    assert response.status_code == 422
    assert "Python isn't available" in response.json()["detail"]
    assert chats == []


# What the sandbox is given


def test_the_chats_recent_excel_files_go_into_the_sandbox(tmp_path: Path) -> None:
    sandbox = FakeSandbox()
    with TestClient(build_app(tmp_path / "data", sandbox=sandbox)) as client:
        wait_until_updated(client)
        chat_id = None
        # Three messages with two spreadsheets each, then Python on a fourth.
        for number in (1, 2, 3):
            files = [
                spreadsheet(tmp_path, f"a{number}.xlsx"),
                spreadsheet(tmp_path, f"b{number}.xlsx"),
            ]
            events = send_python(
                client, "Here", chat_id, documents=files, use_python=False
            )
            chat_id = chat_id_of(events)
        send_python(client, "Now use python", chat_id)

    # The 5 most recent, oldest first.
    assert sandbox.uploaded["cntr_fake_1"] == [
        "b1.xlsx",
        "a2.xlsx",
        "b2.xlsx",
        "a3.xlsx",
        "b3.xlsx",
    ]


def test_only_excel_files_are_sent_and_the_model_is_told_their_names(
    tmp_path: Path,
) -> None:
    sandbox = FakeSandbox()
    model = FakeChatModel(responder=lambda m: "Hello")
    pdf = tmp_path / "x.pdf"
    from helpers import make_pdf

    make_pdf(pdf, ["Depreciation spreads the cost."])
    documents = [
        spreadsheet(tmp_path),
        {"name": "x.pdf", "data": base64.b64encode(pdf.read_bytes()).decode()},
    ]
    with TestClient(build_app(tmp_path / "data", model, sandbox=sandbox)) as client:
        wait_until_updated(client)
        send_python(client, "Analyse it", documents=documents)

    assert sandbox.uploaded["cntr_fake_1"] == ["figures.xlsx"]
    call = next(m for m in model.received if "short title" not in text_of(m[0]))
    system = " ".join(
        text_of(next(x for x in call if isinstance(x, SystemMessage))).split()
    )
    assert "The files in it are: `figures.xlsx`." in system


def test_the_original_file_is_sent_not_the_text_the_model_reads(
    tmp_path: Path,
) -> None:
    uploads: dict[str, bytes] = {}

    class Recording(FakeSandbox):
        def create(self, files: list[tuple[str, bytes]]) -> str:
            uploads.update(dict(files))
            return super().create(files)

    sandbox = Recording()
    sent = spreadsheet(tmp_path)
    with TestClient(build_app(tmp_path / "data", sandbox=sandbox)) as client:
        wait_until_updated(client)
        send_python(client, "Analyse", documents=[sent])

    assert base64.b64encode(uploads["figures.xlsx"]).decode() == sent["data"]


# However the reply ends, the sandbox is removed


def test_a_failed_reply_still_removes_its_sandbox(tmp_path: Path) -> None:
    sandbox = FakeSandbox()
    with TestClient(build_app(tmp_path / "data", sandbox=sandbox)) as client:
        wait_until_updated(client)
        events = send_python(client, "python pyfail")

    assert reply_of(events)["status"] == "error"
    assert sandbox.created == ["cntr_fake_1"]
    assert sandbox.open_containers == []


def test_a_sandbox_that_cant_be_made_fails_the_reply_without_a_charge(
    tmp_path: Path,
) -> None:
    sandbox = FakeSandbox()
    sandbox.fail_to_create = True
    with TestClient(build_app(tmp_path / "data", sandbox=sandbox)) as client:
        wait_until_updated(client)
        events = send_python(client, "Use python")
        total = client.get("/api/usage").json()

    reply = reply_of(events)
    assert reply["status"] == "error"
    assert sandbox.created == []
    # Only the title was paid for.
    assert total["cost"] == pytest.approx(FAKE_CALL)


@pytest.fixture
def conversation_parts(tmp_path: Path):
    """A Conversation wired to a fake model and sandbox."""

    def build(responder, sandbox: FakeSandbox):
        model = FakeChatModel(responder=responder)
        database = Database(tmp_path / "app.db")
        repository.create_tables(database)
        ledger = usage_ledger(database)
        history = ModelHistory(
            database, model, tmp_path / "uploads", BIG_BUDGET, ledger
        )
        store = NotesStore(tmp_path / "chroma", FakeEmbeddings(), "fake")
        agent = Agent(model, NotesSearch(store, [], results_per_search=8))
        conversation = Conversation(
            database,
            agent,
            model,
            tmp_path / "uploads",
            TEST_CONFIG,
            history,
            document_reader(tmp_path),
            ledger,
            sandbox,
            TEST_SETTINGS.max_generated_files_per_reply,
            TEST_SETTINGS.max_generated_file_mb,
        )
        return conversation, database

    return build


def test_a_stopped_reply_still_removes_its_sandbox_and_pays_for_it(
    conversation_parts,
) -> None:
    sandbox = FakeSandbox()
    conversation, database = conversation_parts(
        lambda m: FakeReply(
            "one two three four five six",
            delay_seconds=0.01,
            python_runs=({"code": "print(1)", "output": "1\n"},),
        ),
        sandbox,
    )
    prepared = conversation.start_message(SendRequest(text="Go", use_python=True))

    async def stop_after_two_pieces() -> None:
        stream = conversation.stream(prepared)
        tokens = 0
        async for event in stream:
            tokens += event.type == "token"
            if tokens == 2:
                break
        await stream.aclose()  # what happens when the browser disconnects

    asyncio.run(stop_after_two_pieces())

    with database.connection() as connection:
        saved = repository.get_chat(connection, prepared.chat_id).messages[-1]
        sessions = connection.execute(
            "SELECT cost FROM api_usage WHERE kind = 'python'"
        ).fetchall()
    assert saved.status == "stopped"
    # The code it had already run is kept.
    assert saved.tool_runs is not None and saved.tool_runs[0].tool == "python"
    assert sandbox.open_containers == []
    assert [row["cost"] for row in sessions] == [TEST_PRICES.python_session]


def test_stopping_while_the_sandbox_is_being_made_removes_it_when_it_exists(
    conversation_parts,
) -> None:
    sandbox = FakeSandbox(create_seconds=0.3)
    conversation, database = conversation_parts(lambda m: "Hello", sandbox)
    prepared = conversation.start_message(SendRequest(text="Go", use_python=True))

    async def stop_during_creation() -> None:
        async def consume() -> None:
            async for _ in conversation.stream(prepared):
                pass

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.1)  # the sandbox is still being made
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await asyncio.sleep(0.5)  # it now exists, and is cleaned up

    asyncio.run(stop_during_creation())

    assert sandbox.created == ["cntr_fake_1"]
    assert sandbox.open_containers == []
    with database.connection() as connection:
        sessions = connection.execute(
            "SELECT COUNT(*) FROM api_usage WHERE kind = 'python'"
        ).fetchone()[0]
    assert sessions == 1


# Saved with the question, and repeated


def test_the_button_is_saved_with_the_question_and_repeated_by_retry_and_edit(
    tmp_path: Path,
) -> None:
    sandbox = FakeSandbox()
    with TestClient(build_app(tmp_path / "data", sandbox=sandbox)) as client:
        wait_until_updated(client)
        events = send_python(client, "Use python")
        chat_id = chat_id_of(events)
        question = next(e for e in events if e["type"] == "start")["userMessage"]
        assert question["pythonRequested"] is True

        regenerated = client.post(f"/api/chats/{chat_id}/regenerate")
        edited = client.post(
            f"/api/chats/{chat_id}/messages/{question['id']}/edit",
            json={
                "text": "Use python again",
                "expectedLatestMessageId": question["id"],
                "expectedOriginalText": "Use python",
            },
        )
        chat = client.get(f"/api/chats/{chat_id}").json()

    assert regenerated.status_code == 200 and edited.status_code == 200
    assert len(sandbox.created) == 3
    assert sandbox.open_containers == []
    assert chat["messages"][0]["pythonRequested"] is True


def test_a_question_without_the_button_stays_without_it_on_retry(
    tmp_path: Path,
) -> None:
    sandbox = FakeSandbox()
    with TestClient(build_app(tmp_path / "data", sandbox=sandbox)) as client:
        wait_until_updated(client)
        events = send_python(client, "Use python", use_python=False)
        client.post(f"/api/chats/{chat_id_of(events)}/regenerate")

    assert sandbox.created == []


# The code and what it printed


def test_each_run_is_saved_with_its_code_and_output(tmp_path: Path) -> None:
    with TestClient(build_app(tmp_path / "data")) as client:
        wait_until_updated(client)
        events = send_python(client, "Use python")
        chat_id = chat_id_of(events)
        saved = client.get(f"/api/chats/{chat_id}").json()["messages"][-1]

    [run] = saved["toolRuns"]
    assert run["tool"] == "python"
    assert 'pd.read_excel("/mnt/data/figures.xlsx")' in run["input"]
    assert run["result"] == "100.5"
    assert run["ok"] is True and run["truncated"] is False


def test_long_output_is_cut_to_200_lines_with_a_note(tmp_path: Path) -> None:
    with TestClient(build_app(tmp_path / "data")) as client:
        wait_until_updated(client)
        events = send_python(client, "python longoutput")

    [run] = reply_of(events)["toolRuns"]
    lines = run["result"].splitlines()
    assert len(lines) == MAX_OUTPUT_LINES == 200
    assert lines[-1] == "line 200"
    assert run["truncated"] is True


def test_the_runs_repeat_in_order_and_sit_beside_calculator_runs(
    tmp_path: Path,
) -> None:
    reply = PythonReply("c", [], runs := ToolRuns())
    for number in (1, 2):
        block = {
            "type": "code_interpreter_call",
            "id": f"ci_{number}",
            "code": f"print({number})",
            "outputs": [{"type": "logs", "logs": f"{number}\n"}],
            "status": "completed",
        }
        assert reply.read(AIMessageChunk(content=[block])) == 1
        # The same run reported again isn't counted twice.
        assert reply.read(AIMessageChunk(content=[block])) == 0

    assert [r.input for r in runs.runs] == ["print(1)", "print(2)"]


def test_a_run_without_its_output_is_still_listed() -> None:
    reply = PythonReply("c", [], runs := ToolRuns())
    block = {"type": "code_interpreter_call", "id": "x", "code": "1", "outputs": None}

    reply.read(AIMessageChunk(content=[block]))

    assert runs.runs[0].result == ""


def test_links_to_files_in_the_sandbox_are_taken_out_of_the_answer(
    tmp_path: Path,
) -> None:
    assert (
        without_sandbox_links(
            "Chart:\n![Chart](sandbox:/mnt/data/a.png)\n"
            "[Download a.csv](sandbox:/mnt/data/a.csv) and [docs](https://x.test)"
        )
        == "Chart:\nDownload a.csv and [docs](https://x.test)"
    )
    with TestClient(build_app(tmp_path / "data")) as client:
        wait_until_updated(client)
        events = send_python(client, "Use python")

    content = reply_of(events)["content"]
    assert "sandbox:" not in content
    assert "Download summary.csv" in content


# The files it made


def test_generated_files_are_saved_listed_and_served_as_downloads(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    with TestClient(build_app(data)) as client:
        wait_until_updated(client)
        events = send_python(client, "Use python")
        chat_id = chat_id_of(events)
        chat = client.get(f"/api/chats/{chat_id}").json()
        files = chat["messages"][-1]["files"]
        images = client.get(files[0]["url"])
        csv = client.get(files[1]["url"])

    assert [f["name"] for f in files] == ["amounts.png", "summary.csv"]
    assert [f["isImage"] for f in files] == [True, False]
    assert files[1]["mediaType"] == "text/csv"
    assert reply_of(events)["files"] == files
    # Under the chat's own folder, which git ignores.
    saved = generated_files(data)
    assert len(saved) == 2
    assert all(chat_id in f.parts for f in saved)
    assert images.status_code == 200 and images.content[1:4] == b"PNG"
    assert images.headers["content-type"] == "image/png"
    assert csv.content == b"Year,Amount\n2024,100.5\n"
    for response, name in ((images, "amounts.png"), (csv, "summary.csv")):
        assert response.headers["content-disposition"].startswith("attachment")
        assert name in response.headers["content-disposition"]
        assert response.headers["x-content-type-options"] == "nosniff"


def test_svg_files_are_never_served_as_pages(tmp_path: Path) -> None:
    with TestClient(build_app(tmp_path / "data")) as client:
        wait_until_updated(client)
        events = send_python(client, "python svgfile")
        [file] = reply_of(events)["files"]
        response = client.get(file["url"])

    assert file["isImage"] is False
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-disposition"].startswith("attachment")


def test_generated_files_are_not_served_from_the_uploads_folder(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    with TestClient(build_app(data)) as client:
        wait_until_updated(client)
        events = send_python(client, "Use python")
        chat_id = chat_id_of(events)
        name = generated_files(data)[0].name
        direct = client.get(f"/api/uploads/{chat_id}/generated/{name}")

    assert direct.status_code == 404


def test_an_unknown_file_is_not_found(tmp_path: Path) -> None:
    with TestClient(build_app(tmp_path / "data")) as client:
        assert client.get("/api/files/999").status_code == 404


def test_files_are_deleted_with_their_message_when_it_is_replaced(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    with TestClient(build_app(data)) as client:
        wait_until_updated(client)
        events = send_python(client, "Use python")
        chat_id = chat_id_of(events)
        before = {f.name for f in generated_files(data)}
        client.post(f"/api/chats/{chat_id}/regenerate")
        after = {f.name for f in generated_files(data)}
    with sqlite3.connect(data / "app.db") as connection:
        records = connection.execute("SELECT COUNT(*) FROM message_files").fetchone()[0]

    # Two files before, and two new ones (not the old ones) after.
    assert len(before) == len(after) == 2
    assert before.isdisjoint(after)
    assert records == 2


def test_files_are_deleted_with_their_chat(tmp_path: Path) -> None:
    data = tmp_path / "data"
    with TestClient(build_app(data)) as client:
        wait_until_updated(client)
        events = send_python(client, "Use python")
        chat_id = chat_id_of(events)
        assert len(generated_files(data)) == 2
        client.delete(f"/api/chats/{chat_id}")
    with sqlite3.connect(data / "app.db") as connection:
        records = connection.execute("SELECT COUNT(*) FROM message_files").fetchone()[0]

    assert generated_files(data) == []
    assert records == 0


def test_a_file_over_the_size_limit_is_left_out_with_a_note(tmp_path: Path) -> None:
    data = tmp_path / "data"
    with TestClient(build_app(data)) as client:
        wait_until_updated(client)
        events = send_python(client, "python bigfile")

    reply = reply_of(events)
    assert [f["name"] for f in reply["files"]] == ["summary.csv"]
    assert "big.csv was left out: it is larger than 1 MB." in reply["content"]
    assert len(generated_files(data)) == 1


def test_files_over_the_number_limit_are_left_out_with_a_note(tmp_path: Path) -> None:
    with TestClient(build_app(tmp_path / "data")) as client:
        wait_until_updated(client)
        events = send_python(client, "python manyfiles")

    reply = reply_of(events)
    assert [f["name"] for f in reply["files"]] == ["one.csv", "two.csv"]
    assert (
        "three.csv was left out: a reply can include at most 2 files."
        in (reply["content"])
    )


def test_a_file_that_cant_be_downloaded_is_left_out_with_a_note(
    tmp_path: Path,
) -> None:
    class Broken(FakeSandbox):
        def download(self, container_id: str, file_id: str) -> bytes:
            if file_id.endswith("summary.csv"):
                raise RuntimeError("gone")
            return super().download(container_id, file_id)

    with TestClient(build_app(tmp_path / "data", sandbox=Broken())) as client:
        wait_until_updated(client)
        events = send_python(client, "Use python")

    reply = reply_of(events)
    assert [f["name"] for f in reply["files"]] == ["amounts.png"]
    assert "summary.csv couldn't be downloaded." in reply["content"]
    assert reply["status"] == "complete"


def test_later_turns_see_the_answers_text_but_not_its_files(tmp_path: Path) -> None:
    model = FakeChatModel()
    with TestClient(build_app(tmp_path / "data", model)) as client:
        wait_until_updated(client)
        events = send_python(client, "Use python")
        send_python(client, "Thanks, and now?", chat_id_of(events), use_python=False)

    last = [m for m in model.received if "short title" not in text_of(m[0])][-1]
    earlier_answer = next(m for m in last if m.type == "ai")
    assert isinstance(earlier_answer.content, str)
    assert "The average amount was 100.5." in earlier_answer.content
    assert not any(
        isinstance(m.content, list) and m.content for m in last[:-1] if m.type == "ai"
    )


# What it costs


def test_each_sandbox_is_one_ledger_row_at_the_settings_price(
    tmp_path: Path,
) -> None:
    with TestClient(build_app(tmp_path / "data")) as client:
        wait_until_updated(client)
        events = send_python(client, "Use python")
        chat_id = chat_id_of(events)
        usage = client.get(f"/api/chats/{chat_id}/usage").json()
        total = client.get("/api/usage").json()
    with sqlite3.connect(tmp_path / "data" / "app.db") as connection:
        rows = connection.execute(
            "SELECT cost FROM api_usage WHERE kind = 'python'"
        ).fetchall()

    assert [cost for (cost,) in rows] == [TEST_PRICES.python_session]
    assert usage["breakdown"]["python"] == pytest.approx(TEST_PRICES.python_session)
    # The reply, the title and the sandbox.
    assert usage["cost"] == pytest.approx(2 * FAKE_CALL + TEST_PRICES.python_session)
    assert total["cost"] == pytest.approx(usage["cost"])


def test_a_retry_pays_for_a_second_sandbox(tmp_path: Path) -> None:
    with TestClient(build_app(tmp_path / "data")) as client:
        wait_until_updated(client)
        events = send_python(client, "Use python")
        chat_id = chat_id_of(events)
        client.post(f"/api/chats/{chat_id}/regenerate")
        usage = client.get(f"/api/chats/{chat_id}/usage").json()

    assert usage["breakdown"]["python"] == pytest.approx(2 * TEST_PRICES.python_session)


def test_an_older_ledger_is_rebuilt_to_allow_python_rows(tmp_path: Path) -> None:
    path = tmp_path / "app.db"
    old = sqlite3.connect(path)
    old.executescript(
        """
        CREATE TABLE api_usage (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT,
            kind TEXT NOT NULL CHECK (kind IN ('reply', 'title', 'summary',
                'search', 'notes_update', 'web_search')),
            model TEXT NOT NULL, input_tokens INTEGER NOT NULL,
            cached_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL,
            cost REAL NOT NULL, estimated INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL);
        CREATE INDEX api_usage_by_chat ON api_usage(chat_id);
        INSERT INTO api_usage (chat_id, kind, model, input_tokens, cached_tokens,
            output_tokens, cost, created_at)
            VALUES ('c', 'web_search', 'm', 0, 0, 0, 0.5, 'x');
        """
    )
    old.commit()
    old.close()
    database = Database(path)

    ledger = usage_ledger(database)
    from askmynotes.usage.log import UsageEntry

    ledger.record([UsageEntry("python", "m", 0, 0, 0)], "c")

    with database.connection() as connection:
        rows = connection.execute(
            "SELECT kind, cost FROM api_usage ORDER BY id"
        ).fetchall()
    assert [(r["kind"], r["cost"]) for r in rows] == [
        ("web_search", 0.5),
        ("python", TEST_PRICES.python_session),
    ]


def test_an_older_database_gets_the_new_columns_and_keeps_its_messages(
    tmp_path: Path,
) -> None:
    path = tmp_path / "app.db"
    old = sqlite3.connect(path)
    old.executescript(
        """
        CREATE TABLE chats (id TEXT PRIMARY KEY, title TEXT NOT NULL,
            pinned INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
            last_used_at TEXT NOT NULL, summary TEXT,
            summarised_up_to INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'complete', error TEXT, sources TEXT,
            created_at TEXT NOT NULL, quoted_context TEXT, web_sources TEXT,
            tool_runs TEXT);
        INSERT INTO chats
            VALUES ('c', 'Old chat', 0, '2026-01-01', '2026-01-01', NULL, 0);
        INSERT INTO messages (chat_id, role, content, created_at)
            VALUES ('c', 'user', 'An old question', '2026-01-01');
        """
    )
    old.commit()
    old.close()
    database = Database(path)

    repository.create_tables(database)

    with database.connection() as connection:
        message = repository.get_chat(connection, "c").messages[0]
    assert message.content == "An old question"
    assert message.python_requested is False
    assert message.files == []
