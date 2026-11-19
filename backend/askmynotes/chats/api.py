"""The chat routes: send, regenerate, list, open, rename, pin, delete, search."""

from collections.abc import AsyncIterator, Callable
from pathlib import Path

from fastapi import APIRouter, Response
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from askmynotes.chats import repository
from askmynotes.chats.conversation import Conversation, PreparedReply
from askmynotes.chats.events import StreamEvent
from askmynotes.chats.models import (
    ChatDetail,
    ChatSummary,
    ChatUpdate,
    EditRequest,
    SearchResult,
    SendRequest,
)
from askmynotes.database import Database
from askmynotes.notes.sync import NotesUpdating


async def as_json_lines(events: AsyncIterator[StreamEvent]) -> AsyncIterator[str]:
    """Write each event as one line of JSON, closing the source when done."""
    try:
        async for event in events:
            yield event.model_dump_json(by_alias=True) + "\n"
    finally:
        # If the browser disconnects, closing the source is what lets the
        # conversation save the partly written reply as "stopped".
        await events.aclose()  # type: ignore[attr-defined]


def json_lines_response(
    conversation: Conversation, prepared: PreparedReply
) -> StreamingResponse:
    """Stream a prepared reply to the browser."""
    return StreamingResponse(
        as_json_lines(conversation.stream(prepared)),
        media_type="application/x-ndjson",
        background=BackgroundTask(prepared.release),
    )


def create_chats_router(
    database: Database,
    conversation: Conversation,
    uploads_dir: Path,
    notes_updating: Callable[[], bool],
) -> APIRouter:
    """Build the routes, bound to one database and conversation.

    `notes_updating` says whether the notes are being updated, when chat waits.
    """
    router = APIRouter(prefix="/api/chats")

    @router.post("/send")
    def send_message(request: SendRequest) -> StreamingResponse:
        if notes_updating():
            raise NotesUpdating()
        return json_lines_response(conversation, conversation.start_message(request))

    @router.post("/{chat_id}/regenerate")
    def regenerate_reply(chat_id: str) -> StreamingResponse:
        if notes_updating():
            raise NotesUpdating()
        return json_lines_response(
            conversation, conversation.start_regeneration(chat_id)
        )

    @router.post("/{chat_id}/messages/{message_id}/edit")
    def edit_latest_message(
        chat_id: str, message_id: int, request: EditRequest
    ) -> StreamingResponse:
        if notes_updating():
            raise NotesUpdating()
        return json_lines_response(
            conversation, conversation.start_edit(chat_id, message_id, request)
        )

    @router.get("")
    def list_chats() -> list[ChatSummary]:
        with database.connection() as connection:
            return repository.list_chats(connection)

    # Declared before "/{chat_id}", or "search" would be read as a chat id.
    @router.get("/search")
    def search_chats(q: str) -> list[SearchResult]:
        with database.connection() as connection:
            return repository.search_chats(connection, q)

    @router.get("/{chat_id}")
    def open_chat(chat_id: str) -> ChatDetail:
        with database.connection() as connection:
            return repository.get_chat(connection, chat_id)

    @router.patch("/{chat_id}")
    def update_chat(chat_id: str, update: ChatUpdate) -> ChatSummary:
        with database.connection() as connection:
            if update.title is not None:
                repository.rename_chat(connection, chat_id, update.title)
            if update.pinned is not None:
                repository.set_pinned(connection, chat_id, update.pinned)
            return repository.get_chat_summary(connection, chat_id)

    @router.delete("/{chat_id}", status_code=204)
    def delete_chat(chat_id: str) -> Response:
        release = conversation.reserve(chat_id)
        try:
            with database.connection() as connection:
                repository.delete_chat(connection, chat_id, uploads_dir)
        finally:
            release()
        return Response(status_code=204)

    return router
