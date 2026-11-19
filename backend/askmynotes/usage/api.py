"""The usage routes: one chat's cost and context, and the all-chats total."""

from fastapi import APIRouter

from askmynotes.chats import repository
from askmynotes.chats.history import ModelHistory
from askmynotes.database import Database
from askmynotes.usage.ledger import UsageLedger
from askmynotes.usage.models import ChatUsage, TotalUsage


def create_usage_router(
    database: Database, ledger: UsageLedger, history: ModelHistory
) -> APIRouter:
    """Build the routes, bound to one database."""
    router = APIRouter(prefix="/api")

    @router.get("/chats/{chat_id}/usage")
    def chat_usage(chat_id: str) -> ChatUsage:
        with database.connection() as connection:
            chat = repository.get_chat_summary(connection, chat_id)  # 404 if unknown
        return ledger.chat_usage(chat, history.context_usage(chat_id))

    @router.get("/usage")
    def total_usage() -> TotalUsage:
        return ledger.total_usage()

    return router
