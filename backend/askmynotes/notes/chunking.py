"""Turning a converted file into chunks: the pieces the notes database stores.

Each slide or PDF page is one chunk, so every chunk maps to exactly one slide
or page. Only an unusually long page is split further, and each part keeps
that page's number. Slides with no text are skipped.
"""

from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from askmynotes.notes.convert import ConvertedFile
from askmynotes.settings import Module

# How much neighbouring parts of a split page share, so a sentence cut in two
# still appears whole in one of them.
SPLIT_OVERLAP_CHARACTERS = 200


@dataclass(frozen=True)
class Chunk:
    """One piece of a note file, ready to store."""

    id: str
    # The text stored and shown to the model.
    text: str
    # What is embedded: the text with a short header naming where it came
    # from, so a question naming a module or lecture finds the right file.
    text_to_embed: str
    metadata: dict[str, str | int]


def chunk_file(
    file_id: str,
    module: Module,
    file_name: str,
    converted: ConvertedFile,
    max_characters: int,
) -> list[Chunk]:
    """Split a converted file into chunks, one per slide or page (or part)."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_characters, chunk_overlap=SPLIT_OVERLAP_CHARACTERS
    )
    location = "Slide" if converted.kind == "slide" else "Page"
    chunks = []
    for page in converted.pages:
        if not page.text:
            continue
        parts = (
            [page.text]
            if len(page.text) <= max_characters
            else splitter.split_text(page.text)
        )
        header = (
            f"{module.name} ({module.short_name}) | {file_name} | "
            f"{location} {page.number}"
        )
        for part_number, text in enumerate(parts, start=1):
            chunks.append(
                Chunk(
                    id=f"{file_id}#{page.number}#{part_number}",
                    text=text,
                    text_to_embed=f"{header}\n\n{text}",
                    metadata={
                        "file_id": file_id,
                        "module": module.short_name,
                        "file_name": file_name,
                        "location": converted.kind,
                        "number": page.number,
                        "part": part_number,
                    },
                )
            )
    return chunks
