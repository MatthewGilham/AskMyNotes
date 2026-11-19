"""The notes routes: the sync's status, and the "Refresh notes" button."""

from fastapi import APIRouter, HTTPException

from askmynotes.notes.sync import NotesStatus, NotesSync


def create_notes_router(sync: NotesSync) -> APIRouter:
    """Build the routes for one notes sync."""
    router = APIRouter(prefix="/api/notes")

    @router.get("/status")
    def get_status() -> NotesStatus:
        return sync.status

    @router.post("/refresh", status_code=202)
    def refresh() -> NotesStatus:
        if not sync.start_in_background():
            raise HTTPException(409, "Your notes are already being updated.")
        return sync.status

    return router
