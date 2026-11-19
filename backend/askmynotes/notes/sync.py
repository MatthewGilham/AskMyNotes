"""Keeping the notes database in step with the notes folders.

On every start, and whenever "Refresh notes" is pressed, the sync:

1. fingerprints every file in the notes folders (SHA-256 of its contents),
2. compares them with the record in app.db: a file is new if it isn't
   recorded, changed if its fingerprint differs, deleted if it's gone,
3. updates only those files: converting, chunking and embedding new and
   changed ones, and removing deleted ones.

It runs in a background thread so the browser can show progress, and chat is
paused until it finishes. A file that can't be read is recorded as unreadable
and listed; a file open in another app is skipped, keeping its notes, and
listed; if embedding fails (no internet, say), the sync stops and says so.
"""

import hashlib
import logging
import threading
from dataclasses import dataclass
from pathlib import Path

from askmynotes.chats.errors import friendly_error
from askmynotes.chats.models import ApiModel
from askmynotes.database import Database
from askmynotes.notes import records
from askmynotes.notes.chunking import chunk_file
from askmynotes.notes.pipeline import (
    check_folder_exists,
    convert_note,
    describe_failure,
    find_note_files,
    remove_converted,
    save_markdown,
)
from askmynotes.notes.store import NotesStore
from askmynotes.settings import Module
from askmynotes.usage.ledger import UsageLedger
from askmynotes.usage.log import UsageLog, logging_usage

logger = logging.getLogger(__name__)


class NotesUpdating(Exception):
    """Raised when chat is asked for while the notes are being updated."""

    def __init__(self) -> None:
        super().__init__(
            "Your notes are being updated. You can chat again once the update has "
            "finished."
        )


class UnreadableNote(ApiModel):
    """A note file that couldn't be read, shown in the notes status area."""

    module: str
    file_name: str
    reason: str


class NotesStatus(ApiModel):
    """What the sync is doing, for the notes status area in the sidebar."""

    updating: bool
    new: int = 0
    changed: int = 0
    deleted: int = 0
    # Progress through the files being updated. While the folders are still
    # being checked for changes, both are 0.
    done: int = 0
    total: int = 0
    file_count: int = 0
    unreadable: list[UnreadableNote] = []
    # Ids of files skipped because another app had them open, such as PowerPoint.
    in_use: list[str] = []
    # Set if the last update couldn't finish.
    error: str | None = None


@dataclass(frozen=True)
class NoteFile:
    """A file found in a notes folder, with its fingerprint."""

    file_id: str
    module: Module
    path: Path
    sha256: str


def fingerprint(path: Path) -> str:
    """A SHA-256 hash of the file's contents: different contents, different hash."""
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def file_id_for(module: Module, path: Path) -> str:
    """A file's id: its module and its path inside the module's folder."""
    return f"{module.short_name}/{path.relative_to(module.folder).as_posix()}"


def find_all_note_files(
    modules: list[Module],
) -> tuple[dict[str, NoteFile], list[str]]:
    """Every note file in every module's folder, by id, and the ids of files in use.

    On Windows, a file open in PowerPoint can't be read until it's closed, so it
    is listed as in use instead of stopping the whole update.
    """
    found = {}
    in_use = []
    for module in modules:
        check_folder_exists(module)
        for path in find_note_files(module.folder):
            file_id = file_id_for(module, path)
            try:
                found[file_id] = NoteFile(file_id, module, path, fingerprint(path))
            except PermissionError:
                logger.warning("Skipped %s: it's open in another app", path)
                in_use.append(file_id)
    return found, in_use


class NotesSync:
    """Runs the sync, one at a time, and reports its progress."""

    def __init__(
        self,
        database: Database,
        store: NotesStore,
        modules: list[Module],
        libreoffice_path: Path,
        data_dir: Path,
        max_chunk_characters: int,
        ledger: UsageLedger,
    ) -> None:
        self._database = database
        self._store = store
        self._modules = modules
        self._libreoffice_path = libreoffice_path
        self._data_dir = data_dir
        self._max_chunk_characters = max_chunk_characters
        self._ledger = ledger
        self._lock = threading.Lock()
        self.status = self._finished_status()

    @property
    def updating(self) -> bool:
        return self.status.updating

    def start_in_background(self) -> bool:
        """Start a sync in a background thread. False if one is already running."""
        with self._lock:
            if self.status.updating:
                return False
            # Marked as updating straight away, so chat pauses from this moment.
            self.status = NotesStatus(updating=True)
        # A daemon thread doesn't keep the app running after you stop it.
        threading.Thread(target=self.run, name="notes-sync", daemon=True).start()
        return True

    def run(self) -> None:
        """Bring the notes database up to date. Never raises: errors go in status."""
        self.status = NotesStatus(updating=True)
        try:
            self._sync()
        except Exception as error:  # reported in the notes area, not lost
            logger.exception("The notes update couldn't finish")
            self.status = self._finished_status(
                error="Couldn't finish updating your notes. "
                + friendly_error(error, doing="updating your notes")
            )
            return
        self.status = self._finished_status(
            new=self.status.new,
            changed=self.status.changed,
            deleted=self.status.deleted,
            in_use=self.status.in_use,
        )

    def _sync(self) -> None:
        found, in_use = find_all_note_files(self._modules)
        with self._database.connection() as connection:
            recorded = records.recorded_fingerprints(connection)
        new = [f for file_id, f in found.items() if file_id not in recorded]
        changed = [
            f
            for file_id, f in found.items()
            if file_id in recorded and recorded[file_id] != f.sha256
        ]
        # A file in use still exists, so it keeps its notes until the next update.
        deleted = [
            file_id
            for file_id in recorded
            if file_id not in found and file_id not in in_use
        ]
        self.status = NotesStatus(
            updating=True,
            new=len(new),
            changed=len(changed),
            deleted=len(deleted),
            total=len(new) + len(changed) + len(deleted),
            in_use=in_use,
        )

        for file_id in deleted:
            self._remove(file_id)
            self._step()
        for note in new + changed:
            self._index(note)
            self._step()

    def _step(self) -> None:
        self.status = self.status.model_copy(update={"done": self.status.done + 1})

    def _remove(self, file_id: str) -> None:
        self._store.delete_file(file_id)
        module_short_name, relative = file_id.split("/", 1)
        remove_converted(self._data_dir, module_short_name, Path(relative))
        with self._database.connection() as connection:
            records.forget(connection, file_id)

    def _index(self, note: NoteFile) -> None:
        # Clears anything left by an earlier run that stopped part-way, as well
        # as the old version of a changed file.
        self._store.delete_file(note.file_id)
        module = note.module
        try:
            converted = convert_note(
                note.path, module, self._libreoffice_path, self._data_dir
            )
        except Exception as error:  # one bad file mustn't stop the rest
            logger.exception("Couldn't read %s", note.path)
            remove_converted(
                self._data_dir, module.short_name, note.path.relative_to(module.folder)
            )
            with self._database.connection() as connection:
                records.save(
                    connection,
                    note.file_id,
                    module.short_name,
                    note.path.name,
                    note.sha256,
                    chunk_count=0,
                    unreadable_reason=describe_failure(error),
                )
            return

        save_markdown(self._data_dir, module, note.path, converted)
        chunks = chunk_file(
            note.file_id, module, note.path.name, converted, self._max_chunk_characters
        )
        # Embedding failures (no internet, say) are not about this file, so
        # they stop the whole update rather than marking the file unreadable.
        # Whatever was embedded is recorded, even if the request failed part-way.
        usage = UsageLog(embedding_kind="notes_update")
        try:
            with logging_usage(usage):
                self._store.add(chunks)
        finally:
            self._ledger.record(usage.entries, None)
        # Recorded only now that its chunks are safely stored.
        with self._database.connection() as connection:
            records.save(
                connection,
                note.file_id,
                module.short_name,
                note.path.name,
                note.sha256,
                chunk_count=len(chunks),
            )

    def _finished_status(self, **counts: object) -> NotesStatus:
        with self._database.connection() as connection:
            file_count = records.indexed_file_count(connection)
            unreadable = [
                UnreadableNote(module=r.module, file_name=r.file_name, reason=r.reason)
                for r in records.unreadable_files(connection)
            ]
        return NotesStatus(
            updating=False,
            file_count=file_count,
            unreadable=unreadable,
            **counts,  # type: ignore[arg-type]
        )
