"""Saving the files Python made, and the rules for which ones are kept."""

import logging
import mimetypes
import re
import uuid
from pathlib import Path

from askmynotes.chats.repository import GeneratedFile
from askmynotes.interpreter.reply import CitedFile
from askmynotes.interpreter.sandbox import Sandbox

logger = logging.getLogger(__name__)

BYTES_PER_MEGABYTE = 1024 * 1024
# Under each chat's folder in the uploads folder, which git ignores.
GENERATED_FOLDER = "generated"
MAX_NAME_LENGTH = 100
UNSAFE_NAME_CHARACTERS = re.compile(r'[\x00-\x1f<>:"/\|?*]')


def safe_name(name: str) -> str:
    """A file name that is safe to show and to offer for download."""
    cleaned = UNSAFE_NAME_CHARACTERS.sub("_", Path(name).name).strip(" .")
    return cleaned[:MAX_NAME_LENGTH] or "file"


# The common ones are fixed here, because Windows and macOS give different
# answers for some (".csv" is an Excel type on a Windows PC).
KNOWN_TYPES = {
    ".csv": "text/csv",
    ".txt": "text/plain",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def media_type_of(name: str) -> str:
    extension = Path(name).suffix.lower()
    return (
        KNOWN_TYPES.get(extension)
        or mimetypes.guess_type(name)[0]
        or "application/octet-stream"
    )


def save_generated_files(
    sandbox: Sandbox,
    container_id: str,
    cited: list[CitedFile],
    uploads_dir: Path,
    chat_id: str,
    max_files: int,
    max_megabytes: int,
) -> tuple[list[GeneratedFile], list[str]]:
    """Download the files the answer pointed to and save them under the chat.

    Returns the saved files, and a plain-English note for each one that was left
    out (too many, too large, or it couldn't be downloaded).
    """
    saved: list[GeneratedFile] = []
    notes: list[str] = []
    for file in cited:
        name = safe_name(file.name)
        if len(saved) >= max_files:
            notes.append(
                f"{name} was left out: a reply can include at most {max_files} files."
            )
            continue
        try:
            data = sandbox.download(container_id, file.file_id)
        except Exception:
            logger.exception("Couldn't download %s from the Python sandbox", name)
            notes.append(f"{name} couldn't be downloaded.")
            continue
        if len(data) > max_megabytes * BYTES_PER_MEGABYTE:
            notes.append(f"{name} was left out: it is larger than {max_megabytes} MB.")
            continue
        # A random name on disk, so two files called "chart.png" never collide.
        relative = f"{chat_id}/{GENERATED_FOLDER}/{uuid.uuid4().hex}{Path(name).suffix}"
        path = uploads_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        saved.append(
            GeneratedFile(
                name=name,
                path=relative,
                size=len(data),
                media_type=media_type_of(name),
            )
        )
    return saved, notes
