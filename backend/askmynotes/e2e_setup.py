"""Prepares a throwaway setup for the end-to-end (Playwright) tests.

Run as `uv run python -m askmynotes.e2e_setup <folder>` before the test server
starts. It writes, inside that folder:

- a small made-up module of notes (one PDF), so the tests never read your
  real notes or put lecture content anywhere, and
- a settings file pointing at it, with small limits that the tests rely on, and
- a few made-up documents to attach in the browser tests.
"""

import sys
import zipfile
from pathlib import Path

import openpyxl
import pymupdf

from askmynotes.notes.libreoffice import default_soffice_path

LECTURE_PAGES = [
    "Depreciation spreads the cost of an asset over its useful life.",
    "The straight-line method charges the same amount every year.",
]


def write_notes(folder: Path) -> None:
    """A made-up two-page lecture PDF."""
    folder.mkdir(parents=True, exist_ok=True)
    document = pymupdf.open()
    for text in LECTURE_PAGES:
        document.new_page().insert_text((72, 72), text)
    document.save(folder / "Lecture 1.pdf")
    document.close()


CONTENT_TYPES = (
    '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/'
    '2006/content-types"><Default Extension="rels" ContentType="application/'
    'vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" '
    'ContentType="application/xml"/><Override PartName="/word/document.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.'
    'document.main+xml"/></Types>'
)
RELATIONSHIPS = (
    '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/'
    'package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.'
    'openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="word/document.xml"/></Relationships>'
)


def make_docx(path: Path, paragraphs: list[str]) -> None:
    """A made-up Word file, written from its XML parts (no Word library needed)."""
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
    document = (
        '<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.'
        f'openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}</w:body>'
        "</w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr("_rels/.rels", RELATIONSHIPS)
        archive.writestr("word/document.xml", document)


def make_xlsx(path: Path) -> None:
    """Two sheets of made-up figures."""
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Cash flow"
    sheet.append(["Year", "Amount"])
    sheet.append([2024, 100.5])
    workbook.create_sheet("Notes").append(["Prepared by the finance team"])
    workbook.save(path)


def write_documents(folder: Path) -> None:
    """Made-up documents for the browser tests to attach."""
    folder.mkdir(parents=True, exist_ok=True)
    make_docx(folder / "essay.docx", ["Goodwill is an intangible asset."])
    make_xlsx(folder / "figures.xlsx")
    # Over the e2e limit of 100 tokens (about 400 characters) of text.
    make_docx(folder / "long.docx", ["word " * 120])
    pdf = pymupdf.open()
    pdf.new_page().insert_text((72, 72), "Depreciation spreads the cost.")
    pdf.save(folder / "lecture.pdf")
    pdf.close()


def write_settings(path: Path, notes_folder: Path) -> None:
    """Settings for the tests. Single quotes keep Windows paths as they are."""
    path.write_text(
        f"""user_name = "Matt"
port = 8765
libreoffice_path = '{default_soffice_path()}'
max_images_per_message = 5
max_image_size_mb = 10
max_documents_per_message = 5
max_document_size_mb = 25
max_document_tokens = 100
max_generated_files_per_reply = 2
max_generated_file_mb = 1
# Small, so a few long messages make a chat "long".
context_budget_tokens = 300
max_chunk_characters = 3000
notes_search_results = 8
example_prompts = ["Explain depreciation", "Give me a recipe"]

# High prices, so the fake model's made-up usage (1,000 input tokens, 200 of them
# cached, and 500 output) costs a visible $0.033 a call.
[prices]
chat_input = 10.0
chat_cached_input = 1.0
chat_output = 50.0
embedding_input = 130.0
web_search_call = 10.0
python_session = 20.0

[web_search]
country = "GB"
timezone = "Europe/London"

[[modules]]
name = "Testing Module"
short_name = "TM"
folder = '{notes_folder}'
""",
        encoding="utf-8",
    )


def main() -> None:
    folder = Path(sys.argv[1]).resolve()
    notes_folder = folder / "notes" / "Testing Module"
    write_notes(notes_folder)
    write_settings(folder / "settings.toml", notes_folder)
    write_documents(folder / "documents")


if __name__ == "__main__":
    main()
