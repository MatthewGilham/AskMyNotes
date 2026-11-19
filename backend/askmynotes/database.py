"""The app's SQLite database: one file, opened fresh for each unit of work.

Features keep their own tables (chats in `chats/schema.sql`, and so on) and
register them with `create_schema`. Plain `sqlite3` is used, with no ORM, so
you can see exactly what is stored and how it's queried.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class Database:
    """A handle on the SQLite file at `path`."""

    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Open a connection; commit if the block succeeds, roll back if not."""
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        # SQLite ignores foreign keys unless asked, and deleting a chat relies
        # on them to delete its messages.
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def create_schema(self, schema_file: Path) -> None:
        """Create the tables in a schema file, creating the database if new."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.executescript(schema_file.read_text(encoding="utf-8"))
