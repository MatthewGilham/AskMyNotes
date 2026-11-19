"""Sending a message and streaming the reply, with everything saved as it goes.

Sending happens in two steps so that mistakes are reported properly:

1. `start_message` / `start_regeneration` do the quick checks and save the
   student's message. If something is wrong (an unknown chat, say) they raise
   straight away, before any streaming has begun.
2. `stream` then talks to the model and yields events as the reply arrives.

The student's message is saved before the model is called, so it is never lost
if the model fails. A reply that searched the notes is saved with the sources it
used, and without the line that named them (see `notes/sources.py`). A reply
that searched the web is saved with the pages it cited.
"""

import asyncio
import logging
import threading
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from askmynotes.agent.agent import (
    Agent,
    CalculationStarted,
    NotesSearchStarted,
    PythonStarted,
    WebSearchStarted,
)
from askmynotes.calculator.tools import ToolRuns
from askmynotes.chats import repository
from askmynotes.chats.citation_markers import without_citation_markers
from askmynotes.chats.documents import DocumentReader, save_documents
from askmynotes.chats.errors import friendly_error
from askmynotes.chats.events import (
    DoneEvent,
    EditAcceptanceEvent,
    ErrorEvent,
    SearchingEvent,
    StartEvent,
    StreamEvent,
    TitleEvent,
    TokenEvent,
)
from askmynotes.chats.history import ModelHistory
from askmynotes.chats.images import (
    decode_images,
    message_content,
    save_images,
)
from askmynotes.chats.models import EditRequest, Message, SendRequest
from askmynotes.chats.repository import GeneratedFile
from askmynotes.client_config import ClientConfig
from askmynotes.database import Database
from askmynotes.interpreter.files import save_generated_files
from askmynotes.interpreter.reply import PythonReply, without_sandbox_links
from askmynotes.interpreter.sandbox import Sandbox
from askmynotes.notes.search import FoundNotes
from askmynotes.notes.sources import answer_and_sources
from askmynotes.usage.ledger import UsageLedger
from askmynotes.usage.log import (
    UsageEntry,
    UsageLog,
    entry_from_reply,
    message_characters,
    model_name_of,
)
from askmynotes.web.search import FoundWeb

logger = logging.getLogger(__name__)

TITLE_PROMPT_FILE = Path(__file__).parents[1] / "agent" / "title_prompt.md"
PLACEHOLDER_TITLE_LENGTH = 40
# Python is given at most this many of the chat's attached Excel files.
MAX_EXCEL_FILES = 5


@dataclass
class PreparedReply:
    """A reply that is ready to stream: the student's message is already saved."""

    chat_id: str
    opening_events: list[StreamEvent]
    # Set for the first message of a new chat, which needs a title written.
    title_request: HumanMessage | None
    release: Callable[[], None]
    # The answer gets Python (the button was on for the question).
    use_python: bool = False


class Conversation:
    """Sends messages to the agent and saves what comes back."""

    def __init__(
        self,
        database: Database,
        agent: Agent,
        chat_model: BaseChatModel,
        uploads_dir: Path,
        config: ClientConfig,
        history: ModelHistory,
        documents: DocumentReader,
        ledger: UsageLedger,
        sandbox: Sandbox | None = None,
        max_generated_files: int = 10,
        max_generated_file_mb: int = 25,
    ) -> None:
        self._database = database
        self._agent = agent
        self._chat_model = chat_model
        self._uploads_dir = uploads_dir
        self._config = config
        self._history = history
        self._documents = documents
        self._ledger = ledger
        self._sandbox = sandbox
        self._max_generated_files = max_generated_files
        self._max_generated_file_mb = max_generated_file_mb
        self._active_chats: set[str] = set()
        self._active_lock = threading.Lock()

    def reserve(self, chat_id: str) -> Callable[[], None]:
        """Reserve one chat for a send/edit/regenerate/delete operation."""
        with self._active_lock:
            if chat_id in self._active_chats:
                raise HTTPException(
                    409, "Another operation is already active in this chat."
                )
            self._active_chats.add(chat_id)

        def release() -> None:
            with self._active_lock:
                self._active_chats.discard(chat_id)

        return release

    # Step 1: quick, and raises before streaming starts if something is wrong.

    def start_message(self, request: SendRequest) -> PreparedReply:
        """Save the student's message, creating the chat if it's a new one."""
        if request.use_python and self._sandbox is None:
            raise HTTPException(422, "Python isn't available in this app.")
        release = self.reserve(request.chat_id) if request.chat_id else lambda: None
        try:
            # Validate before writing anything to storage.
            decoded = decode_images(
                request.images,
                self._config.max_images_per_message,
                self._config.max_image_size_mb,
            )
            # Reading a document can take a while, so it happens before the
            # chat is touched; a refused file leaves nothing behind.
            documents = self._documents.read(request.documents)
            with self._database.connection() as connection:
                if request.quoted_context is not None:
                    source = connection.execute(
                        "SELECT role, content, status FROM messages "
                        "WHERE id = ? AND chat_id = ?",
                        (request.quoted_context.source_message_id, request.chat_id),
                    ).fetchone()
                    if (
                        source is None
                        or source["role"] != "assistant"
                        or source["status"] == "error"
                        or not source["content"].strip()
                    ):
                        raise HTTPException(
                            422, "Select text from a saved answer in this chat."
                        )
                is_new_chat = request.chat_id is None
                if request.chat_id is None:
                    chat = repository.create_chat(
                        connection,
                        placeholder_title(request.text, [d.name for d in documents]),
                    )
                else:
                    chat = repository.get_chat_summary(connection, request.chat_id)
                message_id = repository.add_message(
                    connection,
                    chat.id,
                    "user",
                    request.text,
                    quoted_context=request.quoted_context,
                    python_requested=request.use_python,
                )
                paths = save_images(self._uploads_dir, chat.id, request.images, decoded)
                repository.add_images(connection, message_id, paths)
                repository.add_documents(
                    connection,
                    message_id,
                    documents,
                    save_documents(self._uploads_dir, chat.id, documents),
                )
                if is_new_chat:
                    release = self.reserve(chat.id)
                message = repository.get_message(connection, message_id)
                chat = repository.get_chat_summary(connection, chat.id)
            title_request = None
            if is_new_chat:
                # Only the files' names go to the title writer, not their text.
                names = ", ".join(d.name for d in message.documents)
                text = message.content
                if names:
                    text = f"{text}\n(Attached files: {names})".strip()
                content = message_content(self._uploads_dir, text, message.images)
                title_request = HumanMessage(content=content)
        except BaseException:
            release()
            raise
        return PreparedReply(
            chat_id=chat.id,
            opening_events=[StartEvent(chat=chat, user_message=message)],
            title_request=title_request,
            release=release,
            use_python=request.use_python,
        )

    def start_regeneration(self, chat_id: str) -> PreparedReply:
        """Remove the latest reply, so the one that follows replaces it."""
        release = self.reserve(chat_id)
        try:
            with self._database.connection() as connection:
                repository.remove_latest_reply(connection, chat_id, self._uploads_dir)
                use_python = repository.latest_python_requested(connection, chat_id)
        except BaseException:
            release()
            raise
        return PreparedReply(
            chat_id=chat_id,
            opening_events=[],
            title_request=None,
            release=release,
            use_python=use_python,
        )

    def start_edit(
        self, chat_id: str, message_id: int, request: EditRequest
    ) -> PreparedReply:
        """Commit a guarded edit and return an acceptance event before generation."""
        release = self.reserve(chat_id)
        try:
            with self._database.connection() as connection:
                chat, message = repository.edit_latest_message(
                    connection, chat_id, message_id, request, self._uploads_dir
                )
        except BaseException:
            release()
            raise
        return PreparedReply(
            chat_id=chat_id,
            opening_events=[EditAcceptanceEvent(chat=chat, user_message=message)],
            title_request=None,
            release=release,
            use_python=message.python_requested,
        )

    # Step 2: talk to the model.

    async def stream(self, prepared: PreparedReply) -> AsyncIterator[StreamEvent]:
        """Yield the reply as it is written, saving it however it ends."""
        title_task = None
        title_sent = False
        parts: list[str] = []
        found = FoundNotes()
        web = FoundWeb()
        runs = ToolRuns()
        usage = UsageLog(model_name_of(self._chat_model))
        failed = False
        saved = False
        python: PythonReply | None = None
        # Files already written to disk for a reply that then didn't get saved.
        kept_files: list[GeneratedFile] = []
        try:
            # Keep the first acceptance event inside this try/finally too. A
            # browser can disconnect while that first chunk is being sent.
            for event in prepared.opening_events:
                yield event
            if prepared.title_request is not None:
                title_task = asyncio.create_task(
                    self._write_title(prepared.chat_id, prepared.title_request)
                )
            try:
                if prepared.use_python and self._sandbox is not None:
                    yield SearchingEvent(kind="python")
                    python = await self._start_python(prepared.chat_id, runs, usage)
                history = await self._history.for_model(prepared.chat_id)
                async for token in self._agent.stream_reply(
                    history, found, usage, web, runs, python
                ):
                    if isinstance(token, PythonStarted):
                        yield SearchingEvent(kind="python")
                        continue
                    if isinstance(token, NotesSearchStarted):
                        yield SearchingEvent(kind="notes")
                        continue
                    if isinstance(token, WebSearchStarted):
                        yield SearchingEvent(kind="web")
                        continue
                    if isinstance(token, CalculationStarted):
                        yield SearchingEvent(kind="calculator")
                        continue
                    parts.append(token)
                    yield TokenEvent(text=token)
                    # The title usually arrives while the reply is still streaming.
                    if title_task is not None and title_task.done() and not title_sent:
                        title_sent = True
                        title_event = self._save_title(
                            prepared.chat_id, title_task.result()
                        )
                        if title_event is not None:
                            yield title_event
            except Exception as error:
                logger.exception("The model failed while writing a reply")
                failed = True
                message = self._save_reply(
                    prepared.chat_id,
                    "".join(parts),
                    found,
                    web,
                    runs,
                    "error",
                    friendly_error(error),
                    python=python,
                )
                saved = True
                yield ErrorEvent(message=message)
                return

            notes: list[str] = []
            if python is not None and python.cited:
                assert self._sandbox is not None
                kept_files, notes = await asyncio.to_thread(
                    save_generated_files,
                    self._sandbox,
                    python.container_id,
                    python.cited,
                    self._uploads_dir,
                    prepared.chat_id,
                    self._max_generated_files,
                    self._max_generated_file_mb,
                )
            message = self._save_reply(
                prepared.chat_id,
                "".join(parts),
                found,
                web,
                runs,
                "complete",
                python=python,
                files=kept_files,
                notes=notes,
            )
            saved = True
            if title_task is not None and not title_sent:
                title_event = self._save_title(prepared.chat_id, await title_task)
                if title_event is not None:
                    yield title_event
            yield DoneEvent(message=message)
        finally:
            # Reached when the browser stops the reply (Stop, or the page closes):
            # whatever was written so far is kept and marked as stopped.
            try:
                if title_task is not None:
                    title_task.cancel()
                if not saved:
                    # Files saved for a reply that never got saved are removed.
                    for file in kept_files:
                        (self._uploads_dir / file.path).unlink(missing_ok=True)
                    self._save_reply(
                        prepared.chat_id,
                        "".join(parts),
                        found,
                        web,
                        runs,
                        "stopped",
                        python=python,
                    )
                # However the reply ended, what it cost is recorded.
                usage.finish(failed)
                self._ledger.record(usage.entries, prepared.chat_id)
            finally:
                try:
                    # However the reply ended, its sandbox is removed. This is
                    # not awaited, so being stopped can't skip it.
                    if python is not None and self._sandbox is not None:
                        self._sandbox.delete(python.container_id)
                finally:
                    prepared.release()

    # Helpers.

    def _save_reply(
        self,
        chat_id: str,
        reply: str,
        found: FoundNotes,
        web: FoundWeb,
        runs: ToolRuns,
        status: Literal["complete", "stopped", "error"],
        error: str | None = None,
        python: PythonReply | None = None,
        files: list[GeneratedFile] | None = None,
        notes: list[str] | None = None,
    ) -> Message:
        if python is not None:
            reply = without_sandbox_links(reply)
        reply = without_citation_markers(reply)
        content, sources = answer_and_sources(reply, found, status == "complete")
        web.cite_links_in(content)
        if notes:
            content += "\n\n" + "\n".join(f"*{note}*" for note in notes)
        with self._database.connection() as connection:
            message_id = repository.add_message(
                connection,
                chat_id,
                "assistant",
                content,
                status=status,
                error=error,
                sources=sources,
                web_sources=web.pages() or None,
                web_searches=web.queries if web.search_count else None,
                tool_runs=runs.runs or None,
            )
            repository.add_files(connection, message_id, files or [])
            return repository.get_message(connection, message_id)

    async def _start_python(
        self, chat_id: str, runs: ToolRuns, usage: UsageLog
    ) -> PythonReply:
        """Make this reply's sandbox, holding the chat's recent Excel files."""
        assert self._sandbox is not None
        sandbox = self._sandbox
        with self._database.connection() as connection:
            attached = repository.recent_excel_files(
                connection, chat_id, MAX_EXCEL_FILES
            )
        files = [
            (name, (self._uploads_dir / path).read_bytes()) for name, path in attached
        ]
        creating = asyncio.ensure_future(asyncio.to_thread(sandbox.create, files))
        try:
            container_id = await asyncio.shield(creating)
        except asyncio.CancelledError:
            # Stopped while the sandbox was still being made. It will exist in a
            # moment, so it is charged for and removed as soon as it does.
            creating.add_done_callback(lambda task: self._discard(task, chat_id))
            raise
        usage.add_python_session()
        return PythonReply(container_id, [name for name, _ in files], runs)

    def _discard(self, creating: "asyncio.Future[str]", chat_id: str) -> None:
        if creating.cancelled() or creating.exception() is not None:
            return
        assert self._sandbox is not None
        self._sandbox.delete(creating.result())
        self._ledger.record(
            [UsageEntry("python", model_name_of(self._chat_model), 0, 0, 0)], chat_id
        )

    def _save_title(self, chat_id: str, title: str | None) -> TitleEvent | None:
        if not title:
            return None
        with self._database.connection() as connection:
            repository.rename_chat(connection, chat_id, title)
        return TitleEvent(title=title)

    async def _write_title(
        self, chat_id: str, first_message: HumanMessage
    ) -> str | None:
        """Ask the model for a title. A failure here only costs the title.

        The chat keeps its placeholder title (the start of the first message),
        and the reply itself is unaffected, so this is logged, not raised.
        """
        try:
            prompt = TITLE_PROMPT_FILE.read_text(encoding="utf-8")
            reply = await self._chat_model.ainvoke(
                [SystemMessage(content=prompt), first_message]
            )
        except Exception:
            logger.exception("Couldn't write a title for the chat")
            return None
        self._ledger.record(
            [
                entry_from_reply(
                    "title",
                    model_name_of(self._chat_model),
                    reply,
                    len(prompt) + message_characters(first_message),
                )
            ],
            chat_id,
        )
        return clean_title(str(reply.text))


def placeholder_title(text: str, document_names: list[str]) -> str:
    """A temporary title: the start of the first message, or its file's name."""
    words = " ".join(text.split()) or (document_names or ["Image"])[0]
    if len(words) <= PLACEHOLDER_TITLE_LENGTH:
        return words
    return words[:PLACEHOLDER_TITLE_LENGTH].rstrip() + "..."


def clean_title(title: str) -> str:
    """Tidy a model-written title: one line, no quotes or final full stop."""
    one_line = " ".join(title.split())
    return one_line.strip("\"'“”‘’").rstrip(".").strip()
