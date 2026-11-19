"""The ledger: every model call's cost, saved in SQLite, and the totals.

A call's cost is worked out from the prices in `settings.toml` when the call is
recorded and saved with it, so changing a price later only affects new calls.
"""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from askmynotes.chats.models import ChatSummary
from askmynotes.database import Database
from askmynotes.settings import Prices
from askmynotes.usage.log import EMBEDDING_KINDS, UsageEntry
from askmynotes.usage.models import (
    ChatCostBreakdown,
    ChatUsage,
    ContextUsage,
    TotalUsage,
)

SCHEMA_FILE = Path(__file__).with_name("schema.sql")
TOKENS_PER_PRICE_UNIT = 1_000_000


def cost_of(entry: UsageEntry, prices: Prices) -> float:
    """What a call cost, in dollars: tokens times the price per million."""
    if entry.kind == "web_search":
        return prices.web_search_call
    if entry.kind == "python":
        return prices.python_session
    if entry.kind in EMBEDDING_KINDS:
        return entry.input_tokens * prices.embedding_input / TOKENS_PER_PRICE_UNIT
    # Cached tokens are billed at their own, lower price instead of the full one.
    uncached = entry.input_tokens - entry.cached_tokens
    return (
        uncached * prices.chat_input
        + entry.cached_tokens * prices.chat_cached_input
        + entry.output_tokens * prices.chat_output
    ) / TOKENS_PER_PRICE_UNIT


class UsageLedger:
    """Records what the models cost and adds it up."""

    def __init__(self, database: Database, prices: Prices) -> None:
        self._database = database
        self._prices = prices

    def create_tables(self) -> None:
        """Create the tables, and note when recording began (only the first time)."""
        self._allow_every_kind_of_row()
        self._database.create_schema(SCHEMA_FILE)
        self._restore_renamed_rows()
        with self._database.connection() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO usage_tracking (id, started_at) VALUES (1, ?)",
                (datetime.now(UTC).isoformat(),),
            )

    def _allow_every_kind_of_row(self) -> None:
        """Move an older `api_usage` table aside if its kind check doesn't allow
        web searches or Python. SQLite can't change a check in place, so the
        table is rebuilt from its rows (see `_restore_renamed_rows`)."""
        with self._database.connection() as connection:
            table = connection.execute(
                "SELECT sql FROM sqlite_master WHERE name = 'api_usage'"
            ).fetchone()
            if table is None or "'python'" in table["sql"]:
                return
            connection.execute("DROP INDEX IF EXISTS api_usage_by_chat")
            connection.execute("ALTER TABLE api_usage RENAME TO api_usage_old")

    def _restore_renamed_rows(self) -> None:
        """Copy the rows of a table moved aside into the new one, and drop it."""
        with self._database.connection() as connection:
            if not connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name = 'api_usage_old'"
            ).fetchone():
                return
            connection.execute(
                "INSERT INTO api_usage (id, chat_id, kind, model, input_tokens, "
                "cached_tokens, output_tokens, cost, estimated, created_at) "
                "SELECT id, chat_id, kind, model, input_tokens, cached_tokens, "
                "output_tokens, cost, estimated, created_at FROM api_usage_old"
            )
            connection.execute("DROP TABLE api_usage_old")

    def record(self, entries: list[UsageEntry], chat_id: str | None) -> None:
        """Save calls against a chat, or against no chat (a notes update)."""
        if not entries:
            return
        now = datetime.now(UTC).isoformat()
        with self._database.connection() as connection:
            connection.executemany(
                "INSERT INTO api_usage (chat_id, kind, model, input_tokens, "
                "cached_tokens, output_tokens, cost, estimated, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        chat_id,
                        e.kind,
                        e.model,
                        e.input_tokens,
                        e.cached_tokens,
                        e.output_tokens,
                        cost_of(e, self._prices),
                        int(e.estimated),
                        now,
                    )
                    for e in entries
                ],
            )

    def chat_usage(self, chat: ChatSummary, context: ContextUsage) -> ChatUsage:
        """One chat's cost, split by what it was spent on, with its context."""
        with self._database.connection() as connection:
            rows = connection.execute(
                "SELECT kind, SUM(cost) AS cost, MAX(estimated) AS estimated "
                "FROM api_usage WHERE chat_id = ? GROUP BY kind",
                (chat.id,),
            ).fetchall()
            started_at = self._started_at(connection)
        by_kind = {row["kind"]: row["cost"] for row in rows}
        return ChatUsage(
            cost=sum(by_kind.values()),
            breakdown=ChatCostBreakdown(
                replies=by_kind.get("reply", 0.0),
                titles=by_kind.get("title", 0.0),
                summaries=by_kind.get("summary", 0.0),
                searches=by_kind.get("search", 0.0),
                web_searches=by_kind.get("web_search", 0.0),
                python=by_kind.get("python", 0.0),
            ),
            includes_estimate=any(row["estimated"] for row in rows),
            earlier_costs_unrecorded=chat.created_at
            < datetime.fromisoformat(started_at),
            tracking_started_at=started_at,
            context=context,
        )

    def total_usage(self) -> TotalUsage:
        """Everything spent: chats that exist, chats since deleted, and notes
        updates (which belong to no chat)."""
        with self._database.connection() as connection:
            row = connection.execute(
                "SELECT "
                " COALESCE(SUM(cost) FILTER (WHERE chat_id IN (SELECT id FROM chats)),"
                " 0) AS chats, "
                " COALESCE(SUM(cost) FILTER (WHERE chat_id IS NOT NULL AND chat_id "
                " NOT IN (SELECT id FROM chats)), 0) AS deleted_chats, "
                " COALESCE(SUM(cost) FILTER (WHERE chat_id IS NULL), 0) AS "
                " notes_updates, "
                " COALESCE(MAX(estimated), 0) AS estimated "
                "FROM api_usage"
            ).fetchone()
            started_at = self._started_at(connection)
        return TotalUsage(
            cost=row["chats"] + row["deleted_chats"] + row["notes_updates"],
            chats=row["chats"],
            deleted_chats=row["deleted_chats"],
            notes_updates=row["notes_updates"],
            includes_estimate=bool(row["estimated"]),
            tracking_started_at=started_at,
        )

    @staticmethod
    def _started_at(connection: sqlite3.Connection) -> str:
        return connection.execute(
            "SELECT started_at FROM usage_tracking WHERE id = 1"
        ).fetchone()["started_at"]
