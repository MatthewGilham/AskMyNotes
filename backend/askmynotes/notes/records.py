"""The record, in app.db, of every note file the sync has dealt with.

A file is only recorded once its chunks are safely in the notes database, so
an interrupted sync is simply redone for that file next time.
"""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from askmynotes.database import Database

SCHEMA_FILE = Path(__file__).with_name("schema.sql")


@dataclass(frozen=True)
class UnreadableRecord:
    """A note file that couldn't be read, and why."""

    module: str
    file_name: str
    reason: str


def create_tables(database: Database) -> None:
    """Create the note_files table if it doesn't exist yet."""
    database.create_schema(SCHEMA_FILE)


def recorded_fingerprints(connection: sqlite3.Connection) -> dict[str, str]:
    """Every recorded file id, with the fingerprint it had when it was synced."""
    rows = connection.execute("SELECT file_id, sha256 FROM note_files").fetchall()
    return {row["file_id"]: row["sha256"] for row in rows}


def save(
    connection: sqlite3.Connection,
    file_id: str,
    module: str,
    file_name: str,
    sha256: str,
    chunk_count: int,
    unreadable_reason: str | None = None,
) -> None:
    """Record a file as synced: indexed, or unreadable with a reason."""
    status = "indexed" if unreadable_reason is None else "unreadable"
    connection.execute(
        "INSERT OR REPLACE INTO note_files "
        "(file_id, module, file_name, sha256, status, reason, chunk_count, synced_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            file_id,
            module,
            file_name,
            sha256,
            status,
            unreadable_reason,
            chunk_count,
            datetime.now(UTC).isoformat(),
        ),
    )


def forget(connection: sqlite3.Connection, file_id: str) -> None:
    """Remove a deleted file's record."""
    connection.execute("DELETE FROM note_files WHERE file_id = ?", (file_id,))


def indexed_file_count(connection: sqlite3.Connection) -> int:
    """How many files are in the notes database."""
    row = connection.execute(
        "SELECT COUNT(*) FROM note_files WHERE status = 'indexed'"
    ).fetchone()
    return row[0]


def unreadable_files(connection: sqlite3.Connection) -> list[UnreadableRecord]:
    """Every file that couldn't be read, by module and name."""
    rows = connection.execute(
        "SELECT module, file_name, reason FROM note_files "
        "WHERE status = 'unreadable' ORDER BY module, file_name"
    ).fetchall()
    return [
        UnreadableRecord(row["module"], row["file_name"], row["reason"]) for row in rows
    ]
