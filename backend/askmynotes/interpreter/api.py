"""The route that serves the files Python made."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from askmynotes.chats import repository
from askmynotes.database import Database

# Types a browser could open as a page and run scripts from. They are always
# served as plain downloads, never under their own type.
RUNNABLE_TYPES = {"text/html", "image/svg+xml", "application/xhtml+xml", "text/xml"}


def create_files_router(database: Database, uploads_dir: Path) -> APIRouter:
    """Build the route, bound to one database and uploads folder."""
    router = APIRouter(prefix="/api/files")

    @router.get("/{file_id}")
    def download_file(file_id: int) -> FileResponse:
        with database.connection() as connection:
            row = repository.get_file(connection, file_id)
        path = uploads_dir / row["path"] if row is not None else None
        if row is None or path is None or not path.is_file():
            raise HTTPException(404, "That file isn't available.")
        media_type = row["media_type"]
        if media_type in RUNNABLE_TYPES or media_type.startswith("text/html"):
            media_type = "application/octet-stream"
        return FileResponse(
            path,
            media_type=media_type,
            filename=row["name"],
            content_disposition_type="attachment",
            headers={"X-Content-Type-Options": "nosniff"},
        )

    return router
