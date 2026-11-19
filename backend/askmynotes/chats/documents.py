"""Documents attached to a message: checking them, reading their text, and
saving them.

Word, Excel, PowerPoint and PDF files are turned into Markdown text when the
message is sent, and that text is stored with the message and given to the model
with the question. A document belongs only to the chat it was sent in; nothing
here touches the notes database.

The text is made by the same converters as the lecture notes (see
`notes/convert.py`), plus MarkItDown's Word and Excel readers. Old `.doc`,
`.ppt` and `.xls` files go through LibreOffice first.
"""

import base64
import binascii
import logging
import re
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from askmynotes.chats.models import DocumentUpload
from askmynotes.notes.convert import (
    ConvertedFile,
    UnreadableFile,
    convert_pdf,
    convert_pptx,
    get_markitdown,
    require_text,
    tidy,
)
from askmynotes.notes.libreoffice import convert_with_libreoffice

logger = logging.getLogger(__name__)

# Old formats are converted to these before reading.
NEWER_FORMAT = {".doc": "docx", ".ppt": "pptx", ".xls": "xlsx"}
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx", *NEWER_FORMAT}

BYTES_PER_MEGABYTE = 1024 * 1024
# The same rough estimate as the long-chat budget (see `chats/history.py`).
CHARS_PER_TOKEN = 4

# MarkItDown writes each Excel sheet as "## Sheet name" followed by a table. A
# table row starts with "|", so only sheet names ever look like this.
SHEET_HEADING = re.compile(r"^## (.+)$", re.MULTILINE)
# Pictures in Word files become `![alt](data:...)`, which has nothing to read.
INLINE_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")

DocumentKind = Literal["page", "slide", "sheet", "document"]


class InvalidDocument(ValueError):
    """Raised when an attached document can't be accepted. The message says why."""


@dataclass(frozen=True)
class PreparedDocument:
    """A checked, converted document, ready to be saved with its message."""

    name: str
    extension: str
    data: bytes
    # What the count counts. A Word file has no fixed pages, so it has no count.
    kind: DocumentKind
    count: int | None
    text: str


class DocumentReader:
    """Checks and converts the documents attached to a message."""

    def __init__(
        self,
        max_count: int,
        max_megabytes: int,
        max_tokens: int,
        libreoffice_path: Path,
        data_dir: Path,
    ) -> None:
        self._max_count = max_count
        self._max_megabytes = max_megabytes
        self._max_tokens = max_tokens
        self._libreoffice_path = libreoffice_path
        self._data_dir = data_dir

    def read(self, uploads: list[DocumentUpload]) -> list[PreparedDocument]:
        """Check and convert every document. Raises `InvalidDocument` if any one
        is refused, so that nothing is saved for a message that can't be sent."""
        if len(uploads) > self._max_count:
            raise InvalidDocument(
                f"You can attach up to {self._max_count} documents to a message."
            )
        documents = [self._read_one(upload) for upload in uploads]
        total_tokens = sum(len(d.text) for d in documents) // CHARS_PER_TOKEN
        if total_tokens > self._max_tokens:
            raise InvalidDocument(
                f"These documents hold about {total_tokens:,} tokens of text, more "
                f"than the {self._max_tokens:,} allowed in one message. "
                "Attach fewer or smaller files."
            )
        return documents

    def _read_one(self, upload: DocumentUpload) -> PreparedDocument:
        # Only the file's name is kept, never a folder the browser might include.
        name = Path(upload.name).name
        extension = Path(name).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise InvalidDocument(
                f"{name} isn't a supported document type. "
                "Use PDF, Word, Excel or PowerPoint."
            )
        try:
            data = base64.b64decode(upload.data, validate=True)
        except binascii.Error:
            raise InvalidDocument(f"{name} isn't a valid file.") from None
        if len(data) > self._max_megabytes * BYTES_PER_MEGABYTE:
            raise InvalidDocument(f"{name} is larger than {self._max_megabytes} MB.")

        # The converters read from disk, so the file waits in a folder inside the
        # project (never the user's temp folder) while it is converted. A corrupt
        # PDF can leave its file open on Windows, so a failed cleanup must not
        # replace the clear message about the file.
        scratch_parent = self._data_dir / "upload_tmp"
        scratch_parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            dir=scratch_parent, ignore_cleanup_errors=True
        ) as scratch:
            path = Path(scratch) / f"document{extension}"
            path.write_bytes(data)
            try:
                kind, count, text = self._convert(path, extension, Path(scratch))
            except UnreadableFile as error:
                raise InvalidDocument(f"{name} can't be read: {error}.") from None
            except Exception as error:
                logger.exception("Couldn't convert the attached document %s", name)
                raise InvalidDocument(
                    f"{name} can't be read: {type(error).__name__}."
                ) from None
        return PreparedDocument(name, extension, data, kind, count, text)

    def _convert(
        self, path: Path, extension: str, scratch: Path
    ) -> tuple[DocumentKind, int | None, str]:
        """The file's kind, its page/slide/sheet count (if it has one), and text."""
        if extension in NEWER_FORMAT:
            converted = convert_with_libreoffice(
                self._libreoffice_path,
                path,
                NEWER_FORMAT[extension],
                output_dir=scratch / "converted",
                work_dir=scratch / "work",
                profile_dir=self._data_dir / "libreoffice_profile_uploads",
            )
            return self._convert(converted, converted.suffix.lower(), scratch)
        if extension == ".pdf":
            return numbered_text(require_text(convert_pdf(path)), "Page")
        if extension == ".pptx":
            return numbered_text(require_text(convert_pptx(path)), "Slide")
        markdown = get_markitdown().convert(str(path)).text_content
        if extension == ".xlsx":
            return sheet_text(markdown)
        return word_text(markdown)


def numbered_text(
    converted: ConvertedFile, label: str
) -> tuple[DocumentKind, int, str]:
    """Join a PDF's or deck's pages, each under a `--- Page 3 ---` marker."""
    parts = [
        f"--- {label} {page.number} ---\n{page.text}"
        for page in converted.pages
        if page.text
    ]
    return converted.kind, len(parts), "\n\n".join(parts)


def sheet_text(markdown: str) -> tuple[DocumentKind, int, str]:
    """An Excel file's sheets, each under a `--- Sheet: Name ---` marker."""
    count = len(SHEET_HEADING.findall(markdown))
    text = SHEET_HEADING.sub(r"--- Sheet: \1 ---", markdown).strip()
    if count == 0 or not text:
        raise UnreadableFile("it contains no data to read")
    return "sheet", count, text


def word_text(markdown: str) -> tuple[DocumentKind, None, str]:
    """A Word file's text. Pictures are removed, as they can't be read."""
    text = tidy(INLINE_IMAGE.sub("", markdown))
    if not text:
        raise UnreadableFile("it contains no text to read")
    return "document", None, text


def save_documents(
    uploads_dir: Path, chat_id: str, documents: list[PreparedDocument]
) -> list[str]:
    """Write the original files to disk and return where each one is, relative
    to the uploads folder (for example `<chat id>/<random name>.docx`)."""
    saved = []
    for document in documents:
        # A random name, so two files called "notes.pdf" never collide.
        relative = f"{chat_id}/{uuid.uuid4().hex}{document.extension}"
        path = uploads_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(document.data)
        saved.append(relative)
    return saved
