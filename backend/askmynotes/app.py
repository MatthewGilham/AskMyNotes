"""Builds the FastAPI app: the API routes plus the built frontend."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.types import Scope

from askmynotes.agent.agent import Agent
from askmynotes.chats.api import create_chats_router
from askmynotes.chats.conversation import Conversation
from askmynotes.chats.documents import DocumentReader, InvalidDocument
from askmynotes.chats.history import ModelHistory
from askmynotes.chats.images import InvalidImage
from askmynotes.chats.repository import ChatNotFound, NothingToReplyTo, create_tables
from askmynotes.client_config import ClientConfig, client_config_from
from askmynotes.database import Database
from askmynotes.interpreter.api import create_files_router
from askmynotes.interpreter.files import GENERATED_FOLDER
from askmynotes.interpreter.sandbox import Sandbox
from askmynotes.notes import records
from askmynotes.notes.api import create_notes_router
from askmynotes.notes.search import NotesSearch
from askmynotes.notes.store import NotesStore
from askmynotes.notes.sync import NotesSync, NotesUpdating
from askmynotes.settings import AppSettings
from askmynotes.usage.api import create_usage_router
from askmynotes.usage.ledger import UsageLedger


class Health(BaseModel):
    """Response of `GET /api/health`."""

    status: str


class UploadFiles(StaticFiles):
    """Serves the saved images. The files Python made are kept in the same
    folder, but are only ever served by `/api/files`, as downloads."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        if GENERATED_FOLDER in path.replace("\\", "/").split("/"):
            raise HTTPException(404)
        return await super().get_response(path, scope)


class FrontendFiles(StaticFiles):
    """Serves the built frontend. Unknown pages get the app itself.

    The browser's address for a chat is /chat/<id>. If the page is refreshed
    there, no such file exists, so the app (index.html) is sent and the
    frontend works out which chat to show.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as error:
            # Windows hands the path over with backslashes, so normalise it first.
            if error.status_code != 404 or path.replace("\\", "/").startswith("api/"):
                raise
            return await super().get_response("index.html", scope)


def create_app(
    settings: AppSettings,
    data_dir: Path,
    chat_model: BaseChatModel,
    embeddings: Embeddings,
    embedding_model: str,
    frontend_dist: Path | None = None,
    sandbox: Sandbox | None = None,
) -> FastAPI:
    """Create the app, storing everything it generates in `data_dir`.

    The notes are synced in the background as soon as the server starts. If
    `frontend_dist` is given, the built frontend is served at `/`.
    """
    config = client_config_from(settings)
    database = Database(data_dir / "app.db")
    create_tables(database)
    records.create_tables(database)
    ledger = UsageLedger(database, settings.prices)
    ledger.create_tables()
    uploads_dir = data_dir / "uploads"
    notes_store = NotesStore(data_dir / "chroma", embeddings, embedding_model)
    agent = Agent(
        chat_model,
        NotesSearch(notes_store, settings.modules, settings.notes_search_results),
        web_search=settings.web_search,
    )
    history = ModelHistory(
        database, chat_model, uploads_dir, settings.context_budget_tokens, ledger
    )
    documents = DocumentReader(
        settings.max_documents_per_message,
        settings.max_document_size_mb,
        settings.max_document_tokens,
        settings.libreoffice_path,
        data_dir,
    )
    conversation = Conversation(
        database,
        agent,
        chat_model,
        uploads_dir,
        config,
        history,
        documents,
        ledger,
        sandbox,
        settings.max_generated_files_per_reply,
        settings.max_generated_file_mb,
    )
    notes_sync = NotesSync(
        database,
        notes_store,
        settings.modules,
        settings.libreoffice_path,
        data_dir,
        settings.max_chunk_characters,
        ledger,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Runs once the server is up, so the browser can watch the progress.
        notes_sync.start_in_background()
        yield

    app = FastAPI(title="AskMyNotes", lifespan=lifespan)

    @app.exception_handler(ChatNotFound)
    def chat_not_found(request: Request, error: ChatNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @app.exception_handler(NothingToReplyTo)
    def nothing_to_reply_to(request: Request, error: NothingToReplyTo) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @app.exception_handler(NotesUpdating)
    def notes_updating(request: Request, error: NotesUpdating) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @app.exception_handler(InvalidImage)
    def invalid_image(request: Request, error: InvalidImage) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(error)})

    @app.exception_handler(InvalidDocument)
    def invalid_document(request: Request, error: InvalidDocument) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(error)})

    @app.get("/api/health")
    def health() -> Health:
        return Health(status="ok")

    @app.get("/api/config")
    def get_config() -> ClientConfig:
        return config

    app.include_router(
        create_chats_router(
            database, conversation, uploads_dir, lambda: notes_sync.updating
        )
    )
    app.include_router(create_usage_router(database, ledger, history))
    app.include_router(create_files_router(database, uploads_dir))
    app.include_router(create_notes_router(notes_sync))
    # Saved images are shown in the browser from here.
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/api/uploads", UploadFiles(directory=uploads_dir), name="uploads")

    # Mounted last so the API routes above take priority over the static files.
    if frontend_dist is not None:
        app.mount(
            "/", FrontendFiles(directory=frontend_dist, html=True), name="frontend"
        )
    return app
