"""All reading and writing of chats and messages in SQLite.

Every function takes an open connection (see `Database.connection`), so the
caller decides what counts as one unit of work.
"""

import json
import re
import shutil
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, TypeAdapter

from askmynotes.chats.citation_markers import without_citation_markers
from askmynotes.chats.documents import PreparedDocument
from askmynotes.chats.images import to_url
from askmynotes.chats.models import (
    ChatDetail,
    ChatSummary,
    EditRequest,
    Message,
    MessageDocument,
    MessageFile,
    QuotedContext,
    SearchResult,
    Source,
    ToolRun,
    WebSource,
)
from askmynotes.database import Database

SCHEMA_FILE = Path(__file__).with_name("schema.sql")

_sources_adapter = TypeAdapter(list[Source])
_web_sources_adapter = TypeAdapter(list[WebSource])
_tool_runs_adapter = TypeAdapter(list[ToolRun])


def create_tables(database: Database) -> None:
    """Create the chat tables, and add any columns an older database lacks."""
    database.create_schema(SCHEMA_FILE)
    with database.connection() as connection:
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(chats)")
        }
        # Databases made before long-chat handling don't have these two columns.
        if "summary" not in columns:
            connection.execute("ALTER TABLE chats ADD COLUMN summary TEXT")
        if "summarised_up_to" not in columns:
            connection.execute(
                "ALTER TABLE chats "
                "ADD COLUMN summarised_up_to INTEGER NOT NULL DEFAULT 0"
            )

        message_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(messages)")
        }
        if "quoted_context" not in message_columns:
            connection.execute("ALTER TABLE messages ADD COLUMN quoted_context TEXT")
        if "web_sources" not in message_columns:
            connection.execute("ALTER TABLE messages ADD COLUMN web_sources TEXT")
        if "web_searches" not in message_columns:
            connection.execute("ALTER TABLE messages ADD COLUMN web_searches TEXT")
        if "tool_runs" not in message_columns:
            connection.execute("ALTER TABLE messages ADD COLUMN tool_runs TEXT")
        if "python_requested" not in message_columns:
            connection.execute(
                "ALTER TABLE messages "
                "ADD COLUMN python_requested INTEGER NOT NULL DEFAULT 0"
            )


# Pictures the browser may show under an answer. Anything else, SVG and HTML
# included, is only ever offered as a download, so it can't run scripts here.
SHOWN_IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif"}


class GeneratedFile(BaseModel):
    """A file Python made, saved on disk and ready to be recorded."""

    name: str
    # Relative to the uploads folder.
    path: str
    size: int
    media_type: str


class ChatNotFound(Exception):
    """Raised when a chat id doesn't exist."""

    def __init__(self, chat_id: str) -> None:
        super().__init__(f"No chat with id {chat_id!r}")


def create_chat(
    connection: sqlite3.Connection, title: str, at: datetime | None = None
) -> ChatSummary:
    """Save a new, empty chat."""
    now = (at or datetime.now(UTC)).isoformat()
    chat_id = uuid.uuid4().hex
    connection.execute(
        "INSERT INTO chats (id, title, pinned, created_at, last_used_at) "
        "VALUES (?, ?, 0, ?, ?)",
        (chat_id, title, now, now),
    )
    return get_chat_summary(connection, chat_id)


def add_message(
    connection: sqlite3.Connection,
    chat_id: str,
    role: Literal["user", "assistant"],
    content: str,
    status: Literal["complete", "stopped", "error"] = "complete",
    error: str | None = None,
    sources: list[Source] | None = None,
    at: datetime | None = None,
    quoted_context: QuotedContext | None = None,
    web_sources: list[WebSource] | None = None,
    web_searches: list[str] | None = None,
    tool_runs: list[ToolRun] | None = None,
    python_requested: bool = False,
) -> int:
    """Save a message, mark the chat as just used, and return the message id."""
    get_chat_summary(connection, chat_id)  # raises ChatNotFound for a bad id
    now = (at or datetime.now(UTC)).isoformat()
    sources_json = (
        None if sources is None else _sources_adapter.dump_json(sources).decode()
    )
    web_sources_json = (
        None
        if web_sources is None
        else _web_sources_adapter.dump_json(web_sources).decode()
    )
    tool_runs_json = (
        None if tool_runs is None else _tool_runs_adapter.dump_json(tool_runs).decode()
    )
    cursor = connection.execute(
        "INSERT INTO messages (chat_id, role, content, status, error, sources, "
        "created_at, quoted_context, web_sources, web_searches, tool_runs, "
        "python_requested) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            chat_id,
            role,
            content,
            status,
            error,
            sources_json,
            now,
            quoted_context.model_dump_json() if quoted_context else None,
            web_sources_json,
            None if web_searches is None else json.dumps(web_searches),
            tool_runs_json,
            int(python_requested),
        ),
    )
    connection.execute("UPDATE chats SET last_used_at = ? WHERE id = ?", (now, chat_id))
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def list_chats(connection: sqlite3.Connection) -> list[ChatSummary]:
    """All chats: pinned first, then the most recently used."""
    rows = connection.execute(
        "SELECT * FROM chats ORDER BY pinned DESC, last_used_at DESC"
    ).fetchall()
    return [ChatSummary.model_validate(dict(row)) for row in rows]


def get_chat_summary(connection: sqlite3.Connection, chat_id: str) -> ChatSummary:
    """One chat without its messages."""
    row = connection.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
    if row is None:
        raise ChatNotFound(chat_id)
    return ChatSummary.model_validate(dict(row))


def get_chat(connection: sqlite3.Connection, chat_id: str) -> ChatDetail:
    """One chat with all its messages, oldest first."""
    summary = get_chat_summary(connection, chat_id)
    rows = connection.execute(
        "SELECT * FROM messages WHERE chat_id = ? ORDER BY id", (chat_id,)
    ).fetchall()
    image_rows = connection.execute(
        "SELECT message_id, path FROM message_images "
        "WHERE message_id IN (SELECT id FROM messages WHERE chat_id = ?) ORDER BY id",
        (chat_id,),
    ).fetchall()
    images: dict[int, list[str]] = {}
    for image in image_rows:
        images.setdefault(image["message_id"], []).append(to_url(image["path"]))
    document_rows = connection.execute(
        "SELECT * FROM message_documents "
        "WHERE message_id IN (SELECT id FROM messages WHERE chat_id = ?) ORDER BY id",
        (chat_id,),
    ).fetchall()
    documents: dict[int, list[sqlite3.Row]] = {}
    for document in document_rows:
        documents.setdefault(document["message_id"], []).append(document)
    file_rows = connection.execute(
        "SELECT * FROM message_files "
        "WHERE message_id IN (SELECT id FROM messages WHERE chat_id = ?) ORDER BY id",
        (chat_id,),
    ).fetchall()
    files: dict[int, list[sqlite3.Row]] = {}
    for file in file_rows:
        files.setdefault(file["message_id"], []).append(file)
    messages = [
        _message_from_row(
            row,
            images.get(row["id"], []),
            documents.get(row["id"], []),
            files.get(row["id"], []),
        )
        for row in rows
    ]
    return ChatDetail(**summary.model_dump(), messages=messages)


def _message_file(row: sqlite3.Row) -> MessageFile:
    return MessageFile(
        id=row["id"],
        name=row["name"],
        size=row["size"],
        media_type=row["media_type"],
        is_image=row["media_type"] in SHOWN_IMAGE_TYPES,
        url=f"/api/files/{row['id']}",
    )


def _message_from_row(
    row: sqlite3.Row,
    images: list[str],
    document_rows: list[sqlite3.Row],
    file_rows: list[sqlite3.Row],
) -> Message:
    data = dict(row)
    if data["role"] == "assistant":
        data["content"] = without_citation_markers(data["content"])
    if data["sources"] is not None:
        data["sources"] = json.loads(data["sources"])
    if data["quoted_context"] is not None:
        data["quoted_context"] = json.loads(data["quoted_context"])
    if data["web_sources"] is not None:
        data["web_sources"] = json.loads(data["web_sources"])
    if data["web_searches"] is not None:
        data["web_searches"] = json.loads(data["web_searches"])
    if data["tool_runs"] is not None:
        data["tool_runs"] = json.loads(data["tool_runs"])
    documents = [MessageDocument.model_validate(dict(d)) for d in document_rows]
    return Message.model_validate(
        {
            **data,
            "images": images,
            "documents": documents,
            "files": [_message_file(f) for f in file_rows],
        }
    )


def add_images(
    connection: sqlite3.Connection, message_id: int, relative_paths: list[str]
) -> None:
    """Record where a message's saved images are (relative to the uploads folder)."""
    connection.executemany(
        "INSERT INTO message_images (message_id, path) VALUES (?, ?)",
        [(message_id, path) for path in relative_paths],
    )


def add_documents(
    connection: sqlite3.Connection,
    message_id: int,
    documents: list[PreparedDocument],
    relative_paths: list[str],
) -> None:
    """Record a message's documents: their text and where the originals are
    saved (relative to the uploads folder)."""
    connection.executemany(
        "INSERT INTO message_documents (message_id, name, path, kind, count, text) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            (message_id, d.name, path, d.kind, d.count, d.text)
            for d, path in zip(documents, relative_paths, strict=True)
        ],
    )


def add_files(
    connection: sqlite3.Connection, message_id: int, files: list[GeneratedFile]
) -> None:
    """Record the files Python made for an answer."""
    connection.executemany(
        "INSERT INTO message_files (message_id, name, path, size, media_type) "
        "VALUES (?, ?, ?, ?, ?)",
        [(message_id, f.name, f.path, f.size, f.media_type) for f in files],
    )


def get_file(connection: sqlite3.Connection, file_id: int) -> sqlite3.Row | None:
    """One generated file's record, or None if there is no such file."""
    return connection.execute(
        "SELECT * FROM message_files WHERE id = ?", (file_id,)
    ).fetchone()


def delete_generated_files(
    connection: sqlite3.Connection, uploads_dir: Path, message_id: int
) -> None:
    """Delete a message's generated files from the disk. Their records go with
    the message itself (the database does that)."""
    for row in connection.execute(
        "SELECT path FROM message_files WHERE message_id = ?", (message_id,)
    ):
        (uploads_dir / row["path"]).unlink(missing_ok=True)


def rename_chat(
    connection: sqlite3.Connection, chat_id: str, title: str
) -> ChatSummary:
    """Change a chat's title."""
    get_chat_summary(connection, chat_id)
    connection.execute("UPDATE chats SET title = ? WHERE id = ?", (title, chat_id))
    return get_chat_summary(connection, chat_id)


def set_pinned(
    connection: sqlite3.Connection, chat_id: str, pinned: bool
) -> ChatSummary:
    """Pin or unpin a chat."""
    get_chat_summary(connection, chat_id)
    connection.execute("UPDATE chats SET pinned = ? WHERE id = ?", (pinned, chat_id))
    return get_chat_summary(connection, chat_id)


def delete_chat(
    connection: sqlite3.Connection, chat_id: str, uploads_dir: Path
) -> None:
    """Delete a chat for good: its messages, search entries and image files."""
    get_chat_summary(connection, chat_id)
    # The database deletes the messages, image records and search entries by
    # itself (foreign keys and triggers); the image files on disk are ours.
    connection.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
    shutil.rmtree(uploads_dir / chat_id, ignore_errors=True)


def search_chats(connection: sqlite3.Connection, query: str) -> list[SearchResult]:
    """Find chats whose title or messages contain every word of `query`.

    Each word matches as a prefix, so "depre" finds "depreciation".
    """
    words = re.findall(r"\w+", query)
    if not words:
        return []
    # Quoting each word stops anything typed being read as search syntax.
    match = " ".join(f'"{word}"*' for word in words)
    rows = connection.execute(
        "SELECT chat_id, message_id, "
        "snippet(chat_search, 2, '', '', '...', 12) AS snippet "
        "FROM chat_search WHERE chat_search MATCH ? ORDER BY rank, chat_id, message_id",
        (match,),
    ).fetchall()

    results: list[SearchResult] = []
    seen: set[str] = set()
    for row in rows:  # best match first, so keep each chat's first appearance
        if row["chat_id"] in seen:
            continue
        seen.add(row["chat_id"])
        title = get_chat_summary(connection, row["chat_id"]).title
        results.append(
            SearchResult(
                chat_id=row["chat_id"],
                title=title,
                snippet=row["snippet"],
                message_id=row["message_id"],
            )
        )
    return results


class NothingToReplyTo(Exception):
    """Raised when a chat has no message from the student to answer."""

    def __init__(self, chat_id: str) -> None:
        super().__init__(f"Chat {chat_id!r} has no message to reply to")


def get_message(connection: sqlite3.Connection, message_id: int) -> Message:
    """One saved message."""
    row = connection.execute(
        "SELECT * FROM messages WHERE id = ?", (message_id,)
    ).fetchone()
    image_rows = connection.execute(
        "SELECT path FROM message_images WHERE message_id = ? ORDER BY id",
        (message_id,),
    ).fetchall()
    document_rows = connection.execute(
        "SELECT * FROM message_documents WHERE message_id = ? ORDER BY id",
        (message_id,),
    ).fetchall()
    file_rows = connection.execute(
        "SELECT * FROM message_files WHERE message_id = ? ORDER BY id", (message_id,)
    ).fetchall()
    return _message_from_row(
        row,
        [to_url(image["path"]) for image in image_rows],
        document_rows,
        file_rows,
    )


def remove_latest_reply(
    connection: sqlite3.Connection, chat_id: str, uploads_dir: Path
) -> None:
    """Delete the chat's latest reply, so a new one can take its place.

    Used by Regenerate and Retry. Whatever kind of reply it was (complete,
    stopped or an error), it is replaced, and the old one is not kept.
    """
    get_chat_summary(connection, chat_id)
    last = connection.execute(
        "SELECT id, role FROM messages WHERE chat_id = ? ORDER BY id DESC LIMIT 1",
        (chat_id,),
    ).fetchone()
    if last is not None and last["role"] == "assistant":
        delete_generated_files(connection, uploads_dir, last["id"])
        connection.execute("DELETE FROM messages WHERE id = ?", (last["id"],))
        last = connection.execute(
            "SELECT id, role FROM messages WHERE chat_id = ? ORDER BY id DESC LIMIT 1",
            (chat_id,),
        ).fetchone()
    if last is None or last["role"] != "user":
        raise NothingToReplyTo(chat_id)


def edit_latest_message(
    connection: sqlite3.Connection,
    chat_id: str,
    message_id: int,
    request: EditRequest,
    uploads_dir: Path,
) -> tuple[ChatSummary, Message]:
    """Atomically replace the latest question and its answer after stale checks."""
    get_chat_summary(connection, chat_id)
    last = connection.execute(
        "SELECT * FROM messages WHERE chat_id = ? ORDER BY id DESC LIMIT 1",
        (chat_id,),
    ).fetchone()
    if last is not None and last["role"] == "assistant":
        answer_id = last["id"]
        last = connection.execute(
            "SELECT * FROM messages WHERE chat_id = ? AND id < ? "
            "ORDER BY id DESC LIMIT 1",
            (chat_id, answer_id),
        ).fetchone()
    else:
        answer_id = None
    if last is None or last["role"] != "user":
        raise NothingToReplyTo(chat_id)
    if (
        last["id"] != message_id
        or message_id != request.expected_latest_message_id
        or last["content"] != request.expected_original_text
    ):
        from fastapi import HTTPException

        raise HTTPException(
            409, "This question has changed. Reload the chat and try again."
        )
    has_attachments = any(
        connection.execute(
            f"SELECT 1 FROM {table} WHERE message_id = ? LIMIT 1", (message_id,)
        ).fetchone()
        is not None
        for table in ("message_images", "message_documents")
    )
    if not request.text and not has_attachments:
        from fastapi import HTTPException

        raise HTTPException(
            422, "Write a message or keep an attached image or document."
        )

    summary = connection.execute(
        "SELECT summarised_up_to FROM chats WHERE id = ?", (chat_id,)
    ).fetchone()["summarised_up_to"]
    # A summary containing either replaced row cannot be safely reused.
    if summary >= message_id or (answer_id is not None and summary >= answer_id):
        connection.execute(
            "UPDATE chats SET summary = NULL, summarised_up_to = 0 WHERE id = ?",
            (chat_id,),
        )
    connection.execute(
        "UPDATE messages SET content = ?, status = 'complete', error = NULL, "
        "sources = NULL, web_sources = NULL, web_searches = NULL, tool_runs = NULL "
        "WHERE id = ?",
        (request.text, message_id),
    )
    if answer_id is not None:
        delete_generated_files(connection, uploads_dir, answer_id)
        connection.execute("DELETE FROM messages WHERE id = ?", (answer_id,))
    now = datetime.now(UTC).isoformat()
    connection.execute("UPDATE chats SET last_used_at = ? WHERE id = ?", (now, chat_id))
    return get_chat_summary(connection, chat_id), get_message(connection, message_id)


def latest_python_requested(connection: sqlite3.Connection, chat_id: str) -> bool:
    """Did the student switch Python on for the chat's latest question? Retry,
    Regenerate and Edit all answer that question again, so they repeat it."""
    row = connection.execute(
        "SELECT python_requested FROM messages "
        "WHERE chat_id = ? AND role = 'user' ORDER BY id DESC LIMIT 1",
        (chat_id,),
    ).fetchone()
    return bool(row and row["python_requested"])


def recent_excel_files(
    connection: sqlite3.Connection, chat_id: str, limit: int
) -> list[tuple[str, str]]:
    """The chat's most recent attached Excel files, oldest first, as (name,
    path relative to the uploads folder). Python is given the originals."""
    rows = connection.execute(
        "SELECT name, path FROM message_documents "
        "WHERE message_id IN (SELECT id FROM messages WHERE chat_id = ?) "
        "AND (lower(name) LIKE '%.xlsx' OR lower(name) LIKE '%.xls') "
        "ORDER BY id DESC LIMIT ?",
        (chat_id, limit),
    ).fetchall()
    return [(row["name"], row["path"]) for row in reversed(rows)]


def get_summary(connection: sqlite3.Connection, chat_id: str) -> tuple[str | None, int]:
    """A long chat's saved summary, and the id of the last message it covers."""
    row = connection.execute(
        "SELECT summary, summarised_up_to FROM chats WHERE id = ?", (chat_id,)
    ).fetchone()
    if row is None:
        raise ChatNotFound(chat_id)
    return row["summary"], row["summarised_up_to"]


def save_summary(
    connection: sqlite3.Connection, chat_id: str, summary: str, up_to_message_id: int
) -> None:
    """Save a long chat's summary and which messages it now covers."""
    connection.execute(
        "UPDATE chats SET summary = ?, summarised_up_to = ? WHERE id = ?",
        (summary, up_to_message_id, chat_id),
    )
