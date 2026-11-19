"""Converting one slide file or PDF into pages of Markdown text.

Each slide or PDF page becomes one `Page` with its number, so an answer can
cite the exact slide or page. The conversion itself is done by libraries
(MarkItDown for PowerPoint, pymupdf4llm for PDF), not hand-written parsing.
Only text is extracted; pictures are not read.
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import pymupdf4llm
from markitdown import MarkItDown

# MarkItDown writes this line in front of every slide's text.
SLIDE_MARKER = re.compile(r"<!-- Slide number: (\d+) -->")
# A picture appears as `![alt text](Picture3.jpg)`: a placeholder with no
# readable content, so it is removed.
IMAGE_PLACEHOLDER = re.compile(r"^[ \t]*!\[[^\]]*\]\([^)]*\)[ \t]*$", re.MULTILINE)
BLANK_LINES = re.compile(r"\n{3,}")
# pymupdf4llm wraps text that sits inside a picture in these comment lines, and
# uses <br> for line breaks. The text is real, so it is kept; the wrapping isn't.
PICTURE_TEXT_COMMENT = re.compile(r"<!-- (?:Start|End) of picture text -->")
LINE_BREAK = re.compile(r"<br\s*/?>")


class UnreadableFile(Exception):
    """Raised when a file can't be turned into text. The message says why."""


@dataclass(frozen=True)
class Page:
    """One slide or PDF page. `number` is as shown in PowerPoint or the PDF."""

    number: int
    text: str


@dataclass(frozen=True)
class ConvertedFile:
    """A converted file: its pages, and whether they are slides or PDF pages."""

    kind: Literal["slide", "page"]
    pages: list[Page]


@lru_cache(maxsize=1)
def get_markitdown() -> MarkItDown:
    # Created once: starting it up loads a file-type detector.
    return MarkItDown()


def tidy(text: str) -> str:
    """Remove picture placeholders and runs of blank lines."""
    without_images = IMAGE_PLACEHOLDER.sub("", text)
    return BLANK_LINES.sub("\n\n", without_images).strip()


def convert_pptx(path: Path) -> ConvertedFile:
    """Convert a PowerPoint (.pptx) file, keeping each slide's number.

    Speaker notes and the data tables behind native charts are kept, because
    they are text stored in the file. Pictures are not.
    """
    markdown = get_markitdown().convert(str(path)).text_content
    # Splitting on the marker gives: [text before, number, text, number, text, ...]
    parts = SLIDE_MARKER.split(markdown)
    pages = [
        Page(number=int(number), text=tidy(text))
        for number, text in zip(parts[1::2], parts[2::2], strict=True)
    ]
    return ConvertedFile(kind="slide", pages=pages)


def tidy_pdf_text(text: str) -> str:
    """`tidy`, plus removing pymupdf4llm's picture-text wrapping."""
    text = PICTURE_TEXT_COMMENT.sub("", text)
    return tidy(LINE_BREAK.sub("\n", text))


def convert_pdf(path: Path) -> ConvertedFile:
    """Convert a PDF, keeping each page's number."""
    chunks = pymupdf4llm.to_markdown(str(path), page_chunks=True)
    pages = [
        Page(
            number=chunk["metadata"]["page_number"],
            text=tidy_pdf_text(chunk["text"]),
        )
        for chunk in chunks
    ]
    return ConvertedFile(kind="page", pages=pages)


def require_text(converted: ConvertedFile) -> ConvertedFile:
    """Refuse a file with no text at all (such as a scanned PDF of images)."""
    if not any(page.text for page in converted.pages):
        raise UnreadableFile("it contains no text to read")
    return converted
